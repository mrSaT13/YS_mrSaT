import asyncio
import ipaddress
import json
import logging
import time
import uuid
from asyncio import Future
from typing import Callable, Dict, Optional

from aiohttp import ClientConnectorError, ClientWebSocketResponse, ServerTimeoutError
from urllib.parse import urlparse
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)


class YandexGlagol:
    """Класс для работы с колонкой по локальному протоколу."""

    device_token = None
    url: Optional[str] = None
    ws: Optional[ClientWebSocketResponse] = None

    # next_ping_ts = 0
    # keep_task: Task = None
    update_handler: Callable = None

    waiters: Dict[str, Future] = {}

    def __init__(self, session: YandexSession, device: dict):
        self.session = session
        self.device = device
        self.loop = asyncio.get_event_loop()

    def debug(self, text: str):
        _LOGGER.debug(f"{self.device['name']} | {text}")

    def is_device(self, device: str):
        return (
            self.device["quasar_info"]["device_id"] == device
            or self.device["name"] == device
        )

    @property
    def name(self):
        return self.device["name"]

    async def get_device_token(self):
        self.debug("Обновление токена устройства")

        payload = {
            "device_id": self.device["quasar_info"]["device_id"],
            "platform": self.device["quasar_info"]["platform"],
        }
        # Передаём Authorization с music_token если он есть (glagol требует music token)
        headers = {}
        music = getattr(self.session, "music_token", None)
        x_token = getattr(self.session, "x_token", None)
        
        _LOGGER.debug(f"[{self.name}] glagol token request: music_token={bool(music)}, x_token={bool(x_token)}")
        
        if music:
            headers["Authorization"] = f"OAuth {music}"
            _LOGGER.debug(f"[{self.name}] Using music_token for glagol")
        elif x_token:
            headers["Authorization"] = f"OAuth {x_token}"
            _LOGGER.debug(f"[{self.name}] Using x_token for glagol (music_token not available)")
        else:
            _LOGGER.error(f"[{self.name}] No tokens available for glagol!")
            raise Exception("No tokens for glagol/token")

        # Минимальные заголовки — избегаем сжатия/фингерпринтинга
        # Use mobile UA and explicit Accept to match what Yandex expects
        headers.setdefault("User-Agent", "com.yandex.mobile.auth.sdk/7.42.0 (Xiaomi Redmi; Android 10) Yandex")
        headers.setdefault("Accept", "application/json")
        headers.setdefault("Connection", "keep-alive")

        # Log masked Authorization preview to debug which token is sent
        auth_preview = None
        if "Authorization" in headers:
            a = headers["Authorization"]
            try:
                preview = a[:12]
            except Exception:
                preview = str(type(a))
            auth_preview = f"{preview}... (len={len(a)})"
        _LOGGER.debug(f"[{self.name}] Glagol request headers: {list(headers.keys())} Authorization={auth_preview}")
        
        # Check for cooldown set by YandexSession on recent 403s
        host = urlparse("https://quasar.yandex.net").netloc
        cooldowns = getattr(self.session, "_forbidden_cooldowns", {})
        until = cooldowns.get(host)
        if until and time.time() < until:
            _LOGGER.warning(f"[{self.name}] Glagol token host {host} in 403 cooldown until {until}")
            return None

        try:
            r = await self.session.get(
                "https://quasar.yandex.net/glagol/token", params=payload, headers=headers
            )
        except Exception as e:
            _LOGGER.error(f"[{self.name}] Glagol token request failed: {e}")
            return None

        _LOGGER.debug(f"[{self.name}] Glagol response status: {getattr(r, 'status', 'no-response')}")

        # If we get explicit 403, set cooldown on session to avoid spamming
        try:
            status = getattr(r, 'status', None)
            if status == 403:
                try:
                    if hasattr(self.session, '_forbidden_cooldowns'):
                        self.session._forbidden_cooldowns[host] = time.time() + 300
                        _LOGGER.warning(f"[{self.name}] Set 403 cooldown for {host} (300s)")
                except Exception:
                    pass
                _LOGGER.warning(f"[{self.name}] Glagol token returned 403; returning None and respecting cooldown")
                return None

        # @dext0r: fix bug with wrong content-type — читаем текст и парсим вручную
        resp_text = await r.text()
        try:
            resp = json.loads(resp_text)
        except Exception as e:
            _LOGGER.error(f"[{self.name}] Failed to parse glagol token response: {resp_text[:400]}")
            raise

        _LOGGER.debug(f"[{self.name}] Glagol response status: {resp.get('status')}")
        assert resp["status"] == "ok", resp

        return resp["token"]

    async def start_or_restart(self):
        # first time
        if not self.url:
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            _ = asyncio.create_task(self._connect(0))

        # check IP change
        elif self.device["host"] not in self.url:
            self.debug("Обновление IP-адреса устройства")
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            # force close session
            if self.ws:
                await self.ws.close()

    async def stop(self):
        self.debug("Останавливаем локальное подключение")
        self.url = None
        if self.ws:
            await self.ws.close()

    async def _connect(self, fails: int):
        self.debug("Локальное подключение")

        fails += 1  # will be reset with first msg from station

        try:
            if not self.device_token:
                self.device_token = await self.get_device_token()

            # If token is not available (e.g. 403 cooldown), postpone local connect
            if not self.device_token:
                self.debug("Device token not available — postponing local connect")
                # return to cloud mode and schedule retry
                self.update_handler(None)
                delay = 30
                self.debug(f"Таймаут до следующей попытки получения токена {delay}s")
                await asyncio.sleep(delay)
                _ = asyncio.create_task(self._connect(fails))
                return

            self.ws = await self.session.ws_connect(self.url, heartbeat=55, ssl=False)
            await self.ping(command="softwareVersion")

            # if not self.keep_task or self.keep_task.done():
            #     self.keep_task = self.loop.create_task(self._keep_connection())

            async for msg in self.ws:
                # Большая станция в режиме idle шлёт статус раз в 5 секунд,
                # в режиме playing шлёт чаще раза в 1 секунду
                # self.next_ping_ts = time.time() + 6

                if isinstance(msg.data, ServerTimeoutError):
                    raise msg.data

                data = json.loads(msg.data)
                fails = 0  # any message - reset fails

                # debug(msg.data)

                request_id = data.get("requestId")
                if request_id in self.waiters:
                    result = {"status": data["status"]}

                    if vinsResponse := data.get("vinsResponse"):
                        try:
                            # payload only in yandex module
                            if payload := vinsResponse.get("payload"):
                                response = payload["response"]
                            else:
                                response = vinsResponse["response"]

                            if card := response.get("card"):
                                result.update(card)
                            elif cards := response.get("cards"):
                                result.update(cards[0])
                            elif is_streaming := response.get("is_streaming"):
                                result["is_streaming"] = is_streaming
                            elif output_speech := response.get("output_speech"):
                                result.update(output_speech)

                        except Exception as e:
                            _LOGGER.debug(f"Response error: {e}")

                    self.waiters[request_id].set_result(result)

                self.update_handler(data)

            # TODO: find better place
            self.device_token = None

        except (ClientConnectorError, ConnectionResetError, ServerTimeoutError) as e:
            self.debug(f"Ошибка подключения: {repr(e)}")

        except (asyncio.CancelledError, RuntimeError) as e:
            # сюда попадаем при остановке HA
            if isinstance(e, RuntimeError):
                assert e.args[0] == "Session is closed", repr(e)

            self.debug(f"Останавливаем подключение: {repr(e)}")
            if self.ws and not self.ws.closed:
                await self.ws.close()
            return

        except Exception as e:
            _LOGGER.error(f"{self.name} => local | {repr(e)}")

        # возвращаемся в облачный режим
        self.update_handler(None)

        # останавливаем попытки
        if not self.url:
            return

        if fails:
            # 0s, 30s, 60s, ... 5 min
            delay = 30 * min(fails - 1, 10)
            self.debug(f"Таймаут до следующего подключения {delay}")
            await asyncio.sleep(delay)

        _ = asyncio.create_task(self._connect(fails))

    # async def _keep_connection(self):
    #     _LOGGER.debug("Start keep connection task")
    #     while not self.ws.closed:
    #         await asyncio.sleep(1)
    #         if time.time() > self.next_ping_ts:
    #             await self.ping()

    async def ping(self, command="ping"):
        # _LOGGER.debug("ping")
        try:
            await self.ws.send_json(
                {
                    "conversationToken": self.device_token,
                    "id": str(uuid.uuid4()),
                    "payload": {"command": command},
                    "sentTime": int(round(time.time() * 1000)),
                }
            )
        except:
            pass

    async def send(self, payload: dict) -> Optional[dict]:
        _LOGGER.debug(f"{self.name} => local | {payload}")

        request_id = str(uuid.uuid4())

        try:
            await self.ws.send_json(
                {
                    "conversationToken": self.device_token,
                    "id": request_id,
                    "payload": payload,
                    "sentTime": int(round(time.time() * 1000)),
                }
            )

            self.waiters[request_id] = self.loop.create_future()

            # limit future wait time
            await asyncio.wait_for(self.waiters[request_id], 5)

            # self.next_ping_ts = time.time() + 0.5

            return self.waiters.pop(request_id).result()

        except asyncio.TimeoutError as e:
            _ = self.waiters.pop(request_id, None)
            return {"error": repr(e)}

        except Exception as e:
            _LOGGER.error(f"{self.name} => local | {repr(e)}")
            return {"error": repr(e)}

    async def reset_session(self):
        payload = {
            "command": "serverAction",
            "serverActionEventPayload": {
                "type": "server_action",
                "name": "on_reset_session",
            },
        }
        await self.send(payload)

    prev_msg = None

    def debug_msg(self, data: dict):
        data.pop("id")
        data.pop("sentTime")
        data["state"].pop("timeSinceLastVoiceActivity")
        if player := data["state"].get("playerState"):
            player.pop("progress")

        if data == self.prev_msg:
            return

        for k in sorted(data.keys()):
            if self.prev_msg and k in self.prev_msg and data[k] == self.prev_msg[k]:
                continue
            self.debug(f"{k}: {data[k]}")

        if vins := data.get("vinsResponse"):
            with open(f"{time.time()}.json", "w") as f:
                json.dump(vins, f, ensure_ascii=False, indent=2)

        self.prev_msg = data


class YandexIOListener:
    add_handler = None
    browser = None

    def __init__(self, add_handler: Callable):
        self.add_handler = add_handler

    def start(self, zeroconf: Zeroconf):
        self.browser = ServiceBrowser(
            zeroconf, "_yandexio._tcp.local.", handlers=[self._zeroconf_handler]
        )

    def stop(self, *args):
        self.browser.cancel()
        self.browser.zc.close()

    def _zeroconf_handler(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ):
        try:
            info = zeroconf.get_service_info(service_type, name)
            if not info:
                return

            properties = {
                k.decode(): v.decode() if isinstance(v, bytes) else v
                for k, v in info.properties.items()
            }

            self.add_handler(
                {
                    "device_id": properties["deviceId"],
                    "platform": properties["platform"],
                    "host": str(ipaddress.ip_address(info.addresses[0])),
                    "port": info.port,
                }
            )

        except Exception as e:
            _LOGGER.debug("Can't get zeroconf info", exc_info=e)


def debug(data: bytes):
    data: dict = json.loads(data)
    if experiments := data.get("experiments"):
        data["experiments"] = len(experiments)
    if extra := data.get("extra"):
        data["extra"] = {k: len(v) for k, v in extra.items()}
    if features := data.get("supported_features"):
        data["supported_features"] = len(features)
    _LOGGER.debug(json.dumps(data, ensure_ascii=False))
