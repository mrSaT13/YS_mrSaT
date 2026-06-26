import asyncio
import ipaddress
import json
import logging
import time
import uuid
from asyncio import Future
from typing import Callable, Dict, Optional

from aiohttp import ClientConnectorError, ClientWebSocketResponse, ServerTimeoutError
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
    last_send_text: str = None

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

        music = getattr(self.session, "music_token", None)
        x_token = getattr(self.session, "x_token", None)

        # Attempt 1: Request without Authorization (cookies only)
        try:
            self.debug("Попытка 1: glagol/token без Authorization (только cookies)")
            r = await self.session.get(
                "https://quasar.yandex.net/glagol/token", params=payload
            )
            resp = json.loads(await r.text())
            if resp.get("status") == "ok":
                self.debug("Успешно с cookies")
                return resp["token"]
            else:
                self.debug(f"Cookies не сработали: {resp.get('status')}")
        except Exception as e:
            self.debug(f"Ошибка попытки 1: {e}")

        # Attempt 2: Request with music_token
        if music:
            try:
                self.debug("Попытка 2: glagol/token с music_token")
                r = await self.session._get(
                    "https://quasar.yandex.net/glagol/token",
                    params=payload,
                    headers={"Authorization": f"OAuth {music}"},
                )
                resp = json.loads(await r.text())
                if resp.get("status") == "ok":
                    self.debug("Успешно с music_token")
                    return resp["token"]
                else:
                    _LOGGER.warning(f"music_token не сработал: {resp.get('status')}")
            except Exception as e:
                self.debug(f"Ошибка попытки 2: {e}")

        # Attempt 3: Request with x_token
        if x_token:
            try:
                self.debug("Попытка 3: glagol/token с x_token")
                r = await self.session._get(
                    "https://quasar.yandex.net/glagol/token",
                    params=payload,
                    headers={"Authorization": f"OAuth {x_token}"},
                )
                resp = json.loads(await r.text())
                if resp.get("status") == "ok":
                    self.debug("Успешно с x_token")
                    return resp["token"]
                else:
                    _LOGGER.warning(f"x_token не сработал: {resp.get('status')}")
            except Exception as e:
                self.debug(f"Ошибка попытки 3: {e}")

        _LOGGER.error(f"Не удалось получить токен устройства для {self.name}")
        return None

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

            self.ws = await self.session.ws_connect(self.url, heartbeat=55, ssl=False)
            await self.ping(command="softwareVersion")

            _LOGGER.info(f"{self.name} | WebSocket connected, entering message loop")

            async for msg in self.ws:
                # Большая станция в режиме idle шлёт статус раз в 5 секунд,
                # в режиме playing шлёт чаще раза в 1 секунду

                if isinstance(msg.data, ServerTimeoutError):
                    raise msg.data

                data = json.loads(msg.data)
                fails = 0  # any message - reset fails

                _LOGGER.debug(f"{self.name} <= ws received: state={'state' in data}, vins={'vinsResponse' in data}, player={'playerState' in data.get('state', {})}")

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
                                _LOGGER.debug(f"Card: {json.dumps(card, ensure_ascii=False, indent=2)[:500]}")
                                result.update(card)
                            elif cards := response.get("cards"):
                                _LOGGER.debug(f"Cards: {json.dumps(cards[0], ensure_ascii=False, indent=2)[:500]}")
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
            _LOGGER.warning(f"{self.name} | WebSocket message loop ended (disconnected)")

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
        except Exception:
            pass

    def _trigger_ma_search(self, text: str):
        """Trigger MA search if text looks like a music request.

        Also handles "найди X", "Алиса X" and similar non-standard forms.
        """
        text_lower = text.lower()

        music_keywords = [
            "включи", "включай", "играй", "проиграй", "запусти",
            "поставь", "воспроизведи", "музык", "трек", "песню",
            "песня", "артист", "исполнител", "альбом", "плейлист",
            "радио", "radio", "найди", "найти",
        ]

        if not any(kw in text_lower for kw in music_keywords):
            return

        query = text_lower
        for kw in ["включи", "включай", "играй", "проиграй", "запусти",
                     "поставь", "воспроизведи", "музыку", "трек", "песню",
                     "песня", "артиста", "исполнителя", "альбом", "плейлист",
                     "радио", "найди", "найти"]:
            query = query.replace(kw, "")
        query = query.strip().strip(",.!?")

        if not query or len(query) < 2:
            return

        _LOGGER.info(f"MA: music request '{query}' — will play via MA, stopping Yandex")

        # Immediately stop Yandex to prevent "subscription needed" TTS
        try:
            entity = self.device.get("entity")
            if entity and entity.glagol:
                import asyncio
                asyncio.create_task(self._stop_and_play(entity, query))
        except Exception as e:
            _LOGGER.debug(f"MA stop_and_play failed: {e}")

    async def _stop_and_play(self, entity, query: str):
        """Wait for server to resolve names via playerState, then stop and play via MA.

        Hack: after sendText, Yandex server resolves speech → playerState has
        correct title/subtitle. We wait briefly for that, extract the names,
        then stop Yandex and hand off to MA.

        Also checks entity.last_voice_text for ASR result from microphone.
        """
        resolved_artist = None
        resolved_track = None
        server_resolved = False

        # First: check if entity captured ASR text from voice input
        voice_text = getattr(entity, 'last_voice_text', None)
        if voice_text:
            _LOGGER.info(f"MA: ASR voice text available: '{voice_text}'")

        try:
            # Wait for the server to process sendText and update playerState
            # The server needs time to: receive text → resolve via Alice → start playing
            for _ in range(6):
                await asyncio.sleep(0.25)

                ps = getattr(entity, 'local_state', None)
                if ps:
                    player = ps.get("playerState")
                    if player and player.get("title"):
                        title = player.get("title", "")
                        subtitle = player.get("subtitle", "")
                        playlist_type = player.get("playlistType", "")

                        # Only use if it looks like music (not TTS/alarm/etc)
                        if title and subtitle and playlist_type in ("Track", "Artist", "Album", "Playlist"):
                            resolved_artist = subtitle
                            resolved_track = title if playlist_type == "Track" else None
                            server_resolved = True
                            _LOGGER.info(
                                f"MA: server resolved '{query}' → artist='{resolved_artist}', "
                                f"track='{resolved_track}', type={playlist_type}"
                            )
                            break
                        elif title and player.get("playerType", "") != "dialog":
                            resolved_artist = subtitle or title
                            resolved_track = title if playlist_type == "Track" else None
                            server_resolved = True
                            _LOGGER.info(
                                f"MA: server partial resolve → '{resolved_artist}' / '{resolved_track}'"
                            )
                            break

                # Also check for voice text that arrived via VINS during the wait
                voice_now = getattr(entity, 'last_voice_text', None)
                if voice_now and voice_now != voice_text:
                    voice_text = voice_now
                    _LOGGER.info(f"MA: new ASR text during wait: '{voice_text}'")
        except Exception as e:
            _LOGGER.debug(f"MA: playerState wait failed: {e}")

        # Now stop Yandex to prevent "subscription needed" TTS
        try:
            if entity.glagol:
                await entity.glagol.send({"command": "stop"})
                await asyncio.sleep(0.3)
        except Exception:
            pass

        # Priority: server-resolved > API search > raw query
        if server_resolved and resolved_artist:
            await self._play_via_ma(entity, artist=resolved_artist, track=resolved_track)
        else:
            _LOGGER.info(f"MA: no server resolution for '{query}', falling back to API search")
            await self._resolve_and_search(entity, query)

    async def _play_via_ma(self, entity, artist: str, track: str = None):
        """Play via Music Assistant with known artist/track names."""
        try:
            from ..hass.music_assistant_bridge import get_bridge
            bridge = get_bridge(entity.hass)
            if not bridge.is_enabled():
                return

            request_type = "track" if track else "artist"
            _LOGGER.info(f"MA: playing via MA — artist='{artist}', track='{track}', type={request_type}")

            ok = await bridge.search_and_play(
                entity.entity_id,
                artist=artist,
                track=track,
                request_type=request_type,
                announce=True,
            )

            if not ok:
                display_name = f"{artist} - {track}" if track else artist
                tts_msg = f"Не удалось воспроизвести {display_name}. Возможно, нужна подписка Яндекс Плюс."
                _LOGGER.info(f"MA playback failed, sending TTS: {tts_msg}")
                try:
                    from ..core.utils import external_command
                    await entity.glagol.send(external_command("tts", {"text": tts_msg}))
                except Exception as e2:
                    _LOGGER.debug(f"MA fallback TTS failed: {e2}")

        except Exception as e:
            _LOGGER.debug(f"MA _play_via_ma failed: {e}")

    async def _resolve_and_search(self, entity, raw_query: str):
        """Fallback: resolve query via Yandex Music API search, then play via MA."""
        try:
            from ..hass.music_assistant_bridge import get_bridge
            bridge = get_bridge(entity.hass)
            if not bridge.is_enabled():
                return

            # Strip command words from raw query before searching
            cleaned = raw_query.lower()
            for kw in ["включи", "включай", "играй", "проиграй", "запусти",
                         "поставь", "воспроизведи", "музыку", "трек", "песню",
                         "песня", "артиста", "исполнителя", "альбом", "плейлист",
                         "радио", "найди", "найти"]:
                cleaned = cleaned.replace(kw, "")
            cleaned = cleaned.strip().strip(",.!?")
            if not cleaned or len(cleaned) < 2:
                cleaned = raw_query

            _LOGGER.info(f"MA: resolve query: raw='{raw_query}', cleaned='{cleaned}'")

            resolved_artist = cleaned
            resolved_track = None

            try:
                r = await self.session.get(
                    "https://api.music.yandex.net/search",
                    params={"text": cleaned, "type": "artist", "page": 0},
                    timeout=10,
                )
                resp = await r.json()
                artists = resp.get("result", {}).get("artists", {}).get("results", [])
                if artists:
                    resolved_artist = artists[0].get("name", cleaned)
                    _LOGGER.info(f"MA: fallback resolved artist '{cleaned}' → '{resolved_artist}'")
            except Exception as e:
                _LOGGER.debug(f"Yandex artist search failed: {e}, using cleaned: '{cleaned}'")

            try:
                r = await self.session.get(
                    "https://api.music.yandex.net/search",
                    params={"text": cleaned, "type": "track", "page": 0},
                    timeout=10,
                )
                resp = await r.json()
                tracks = resp.get("result", {}).get("tracks", {}).get("results", [])
                if tracks:
                    track = tracks[0]
                    track_artist = track["artists"][0]["name"] if track.get("artists") else ""
                    track_title = track.get("title", "")
                    if track_artist.lower() == resolved_artist.lower():
                        resolved_track = track_title
                        _LOGGER.info(f"MA: fallback resolved track → '{track_artist} - {track_title}'")
            except Exception as e:
                _LOGGER.debug(f"Yandex track search failed: {e}")

            await self._play_via_ma(entity, artist=resolved_artist, track=resolved_track)

        except Exception as e:
            _LOGGER.debug(f"MA resolve_and_search failed: {e}")

    async def send(self, payload: dict) -> Optional[dict]:
        _LOGGER.debug(f"{self.name} => local | {payload}")

        # Store last sendText for MA fallback (never block the command)
        try:
            if payload.get("command") == "sendText":
                self.last_send_text = payload.get("text", "")
                self._trigger_ma_search(payload.get("text", ""))
            # Skip MA for external commands (existing hack)
            self._ma_skip_next = payload.get("command") == "externalCommandBypass"
        except Exception:
            pass

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

            result = self.waiters.pop(request_id).result()
            if result and result.get("status") == "ok":
                _LOGGER.debug(f"{self.name} <= local | Полный ответ: {json.dumps(result, ensure_ascii=False, indent=2)[:1000]}")
            return result

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
