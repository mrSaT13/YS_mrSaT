import asyncio
import json
import logging
import ssl
from datetime import datetime

import aiohttp
from aiohttp import WSMsgType

from .quasar_info import has_quasar
from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)

IOT_TYPES = {
    "on": "devices.capabilities.on_off",
    "temperature": "devices.capabilities.range",
    "fan_speed": "devices.capabilities.mode",
    "thermostat": "devices.capabilities.mode",
    "program": "devices.capabilities.mode",
    "heat": "devices.capabilities.mode",
    "volume": "devices.capabilities.range",
    "pause": "devices.capabilities.toggle",
    "mute": "devices.capabilities.toggle",
    "channel": "devices.capabilities.range",
    "input_source": "devices.capabilities.mode",
    "brightness": "devices.capabilities.range",
    "color": "devices.capabilities.color_setting",
    "work_speed": "devices.capabilities.mode",
    "humidity": "devices.capabilities.range",
    "ionization": "devices.capabilities.toggle",
    "backlight": "devices.capabilities.toggle",
    "swing": "devices.capabilities.mode",
    "keep_warm": "devices.capabilities.toggle",
    "tea_mode": "devices.capabilities.mode",
    "open": "devices.capabilities.range",
    "camera_pan": "devices.capabilities.range",
    "camera_tilt": "devices.capabilities.range",
    "get_stream": "devices.capabilities.video_stream",
    "heating_mode": "devices.capabilities.range",
    "led_array": "devices.capabilities.led_mask",
    "hsv": "devices.capabilities.color_setting",
    "rgb": "devices.capabilities.color_setting",
    "scene": "devices.capabilities.color_setting",
    "temperature_k": "devices.capabilities.color_setting",
}

MASK_EN = "0123456789abcdef-"
MASK_RU = "оеаинтсрвлкмдпуяы"


def encode(uid: str) -> str:
    """Кодируем UID в рус. буквы."""
    return "".join([MASK_RU[MASK_EN.index(s)] for s in uid])


def parse_scenario(data: dict) -> dict:
    result = {
        k: v
        for k, v in data.items()
        if k in ("name", "icon", "steps", "effective_time", "settings")
    }
    result["triggers"] = [parse_trigger(i) for i in data["triggers"]]
    return result


def parse_trigger(data: dict) -> dict:
    result = {k: v for k, v in data.items() if k == "filters"}

    value = data["trigger"]["value"]
    if isinstance(value, dict):
        value = {
            k: v
            for k, v in value.items()
            if k in ("instance", "property_type", "condition")
        }
        value["device_id"] = data["trigger"]["value"]["device"]["id"]

    result["trigger"] = {"type": data["trigger"]["type"], "value": value}
    return result


def parse_device(data: dict) -> dict:
    return {
        "id": data["id"],
        "capabilities": [
            {"type": i["type"], "state": i["state"]} for i in data["capabilities"]
        ],
        "directives": data["directives"],
    }


def scenario_speaker_tts(name: str, trigger: str, device_id: str, text: str) -> dict:
    return {
        "name": name,
        "icon": "home",
        "triggers": [
            {
                "trigger": {"type": "scenario.trigger.voice", "value": trigger},
            }
        ],
        "steps": [
            {
                "type": "scenarios.steps.actions.v2",
                "parameters": {
                    "items": [
                        {
                            "id": device_id,
                            "type": "step.action.item.device",
                            "value": {
                                "id": device_id,
                                "item_type": "device",
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.quasar",
                                        "state": {
                                            "instance": "tts",
                                            "value": {"text": text},
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            }
        ],
    }


def scenario_speaker_action(
    name: str, trigger: str, device_id: str, action: str
) -> dict:
    return {
        "name": name,
        "icon": "home",
        "triggers": [
            {
                "trigger": {"type": "scenario.trigger.voice", "value": trigger},
            }
        ],
        "steps": [
            {
                "type": "scenarios.steps.actions.v2",
                "parameters": {
                    "items": [
                        {
                            "id": device_id,
                            "type": "step.action.item.device",
                            "value": {
                                "id": device_id,
                                "item_type": "device",
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.quasar.server_action",
                                        "state": {
                                            "instance": "text_action",
                                            "value": action,
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            }
        ],
    }


class Dispatcher:
    dispatcher: dict[str, list] = None

    def __init__(self):
        self.dispatcher = {}

    def subscribe_update(self, signal: str, target):
        targets = self.dispatcher.setdefault(signal, [])
        if target not in targets:
            targets.append(target)
        return lambda: targets.remove(target)

    def dispatch_update(self, signal: str, message: dict):
        if signal not in self.dispatcher:
            return
        for target in self.dispatcher[signal]:
            target(message)


class YandexQuasar(Dispatcher):
    devices: list[dict] = None
    scenarios: list[dict] = None
    online_updated: asyncio.Event = None
    updates_task: asyncio.Task = None
    
    # SSL контекст для обхода проблем с соединением
    ssl_context: ssl.SSLContext = None
    _ssl_context_created: bool = False

    def __init__(self, session: YandexSession):
        super().__init__()
        self.session = session
        self.online_updated = asyncio.Event()
        self.online_updated.set()
        # SSL контекст создаётся лениво при первом использовании
        _LOGGER.debug("YandexQuasar initialized (SSL context will be created on first use)")
    
    def _get_ssl_context(self) -> ssl.SSLContext:
        """Ленивая инициализация SSL контекста для IoT Quasar."""
        if self._ssl_context_created:
            return self.ssl_context
        
        # Создаем SSL контекст без проверки сертификата
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Явно указываем поддерживаемые версии TLS
        try:
            self.ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            _LOGGER.debug(f"SSL context created: TLSv1.2+, verify_mode=CERT_NONE")
        except AttributeError:
            _LOGGER.debug(f"SSL TLS version attributes not available (older Python)")
            
        # Отключаем проверку сертификата и сжатие
        self.ssl_context.options |= ssl.OP_NO_COMPRESSION
        self._ssl_context_created = True
        return self.ssl_context

    async def init(self):
        """Основная функция - минималистичный запрос без "фингерпринтинга"."""
        _LOGGER.info("=" * 70)
        _LOGGER.info("🚀 QUASAR INITIALIZATION STARTED")
        _LOGGER.debug(f"x_token present: {bool(self.session.x_token)}")
        _LOGGER.debug(f"x_token length: {len(self.session.x_token or '')}")

        try:
            _LOGGER.info("📡 Sending minimal request to iot.quasar.yandex.ru...")
            
            # Минимальные заголовки как у обычного браузера - избегаем "фингерпринтинга"
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept-Encoding": "identity",  # Отключаем сжатие!
                "Connection": "close",  # Закрываем соединение после запроса
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
            
            if self.session.x_token:
                headers["Authorization"] = f"OAuth {self.session.x_token}"
                _LOGGER.debug(f"Authorization header added (token length: {len(self.session.x_token)})")
            else:
                _LOGGER.error("❌ x_token is empty!")
                raise Exception("x_token required")
            
            # Прямой запрос через внутреннюю сессию с минимальными параметрами
            async with self.session._session.get(
                "https://iot.quasar.yandex.ru/m/v3/user/devices",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
                ssl=self._get_ssl_context(),
                auto_decompress=False,  # Отключаем автоматическую декомпрессию
            ) as r:
                _LOGGER.info(f"✅ Response received: HTTP {r.status}")
                _LOGGER.debug(f"Response headers: Content-Type={r.content_type}, Length={r.content_length}")
                
                if r.status != 200:
                    try:
                        raw_text = await asyncio.wait_for(r.text(), timeout=5)
                        _LOGGER.error(f"HTTP {r.status} error: {raw_text[:300]}")
                    except:
                        _LOGGER.error(f"HTTP {r.status} (could not read error body)")
                    raise Exception(f"IoT Quasar returned {r.status}")
                
                _LOGGER.info("📖 Reading response body via r.read()...")
                try:
                    # Читаем сырые байты вместо r.text() - избегаем потенциальных проблем с декодированием
                    raw_bytes = await asyncio.wait_for(r.read(), timeout=20)
                    _LOGGER.debug(f"📄 Raw bytes received: {len(raw_bytes)} bytes")
                    
                    # Декодируем вручную
                    body_text = raw_bytes.decode('utf-8', errors='replace')
                    _LOGGER.debug(f"Decoded text preview: {body_text[:200]}")
                    
                    _LOGGER.info("📖 Parsing JSON from body...")
                    resp = json.loads(body_text)
                    status = resp.get('status', 'unknown')
                    _LOGGER.info(f"✅ JSON parsed. API status: '{status}'")
                    
                except asyncio.TimeoutError:
                    _LOGGER.error("⏱️ TIMEOUT reading response body (>20s)")
                    raise Exception("Timeout reading response body")
                except json.JSONDecodeError as je:
                    _LOGGER.error(f"❌ JSON decode error: {je}")
                    raise
                except Exception as e:
                    _LOGGER.error(f"❌ Body read error: {type(e).__name__}: {e}")
                    raise
                
                if resp.get("status") != "ok":
                    _LOGGER.error(f"API returned status '{status}' instead of 'ok'")
                    raise Exception(f"Invalid API status: {status}")

                self.devices = []
                household_count = len(resp.get("households", []))
                _LOGGER.info(f"📦 Processing {household_count} households...")

                for house in resp["households"]:
                    device_list = house.get("all", [])
                    _LOGGER.debug(f"  {house.get('name')}: {len(device_list)} devices")
                    self.devices.extend(
                        {**device, "house_name": house["name"]} for device in device_list
                    )
                
                _LOGGER.info(f"✅ Total devices loaded: {len(self.devices)}")

            await self.load_scenarios()
            await self.load_speakers()
            
            _LOGGER.info(f"🎉 Initialization complete: {len(self.speakers)} speakers")
            _LOGGER.info("=" * 70)
            
        except Exception as e:
            _LOGGER.error(f"❌ INITIALIZATION FAILED: {type(e).__name__}: {e}", exc_info=True)
            _LOGGER.info("=" * 70)
            raise

    @property
    def speakers(self):
        return [i for i in self.devices if has_quasar(i) and i.get("capabilities")]

    @property
    def modules(self):
        return [i for i in self.devices if has_quasar(i) and not i.get("capabilities")]

    async def load_speakers(self):
        hashes = {}
        for scenario in self.scenarios:
            try:
                hash = scenario["triggers"][0]["value"]
                hashes[hash] = scenario["id"]
            except Exception:
                pass

        for speaker in self.speakers:
            device_id: str = speaker["id"]
            hash = encode(device_id)
            speaker["scenario_id"] = (
                hashes[hash]
                if hash in hashes
                else await self.add_scenario(device_id, hash)
            )

    async def load_speaker_config(self, device: dict):
        """Загружаем device_id и platform для колонок."""
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/user/devices/{device['id']}/configuration"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        device.update(resp["quasar_info"])

    async def load_scenarios(self):
        """Получает список сценариев."""
        # Делает минималистичный запрос и читает сырые байты, затем парсит JSON
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        if self.session.x_token:
            headers["Authorization"] = f"OAuth {self.session.x_token}"

        async with self.session._session.get(
            f"https://iot.quasar.yandex.ru/m/user/scenarios",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
            ssl=self._get_ssl_context(),
            auto_decompress=False,
        ) as r:
            _LOGGER.info(f"← GET /m/user/scenarios -> {r.status}")
            if r.status != 200:
                text = await r.text()
                raise Exception(f"Scenarios fetch failed: {r.status} {text[:200]}")

            try:
                raw = await asyncio.wait_for(r.read(), timeout=20)
            except asyncio.TimeoutError:
                raise Exception("Timeout reading scenarios body")
            except Exception as e:
                raise

            body = raw.decode("utf-8", errors="replace")
            try:
                resp = json.loads(body)
            except json.JSONDecodeError as e:
                _LOGGER.error(f"Failed to decode scenarios JSON: {e}; body start: {body[:300]}")
                raise

        assert resp.get("status") == "ok", resp
        self.scenarios = resp["scenarios"]
        _LOGGER.debug(f"Загружено сценариев: {len(self.scenarios)}")

    async def update_scenario(self, name: str):
        sid = next((i["id"] for i in self.scenarios if i["name"] == name), None)

        if sid is None:
            await self.load_scenarios()
            sid = next(i["id"] for i in self.scenarios if i["name"] == name)

        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/{sid}/edit"
        )
        resp = await r.json()
        assert resp["status"] == "ok"

        payload = parse_scenario(resp["scenario"])
        r = await self.session.put(
            f"https://iot.quasar.yandex.ru/m/v3/user/scenarios/{sid}", 
            json=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def add_scenario(self, device_id: str, hash: str) -> str:
        """Добавляет сценарий-пустышку."""
        payload = scenario_speaker_tts("ХА " + device_id, hash, device_id, "пустышка")
        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios", 
            json=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp["scenario_id"]

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS."""
        if "scenario_id" not in device:
            return
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        device_id = device["id"]
        name = "ХА " + device_id
        trigger = encode(device_id)
        payload = (
            scenario_speaker_tts(name, trigger, device_id, text)
            if is_tts
            else scenario_speaker_action(name, trigger, device_id, text)
        )

        sid = device["scenario_id"]

        r = await self.session.put(
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/{sid}", 
            json=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}/actions"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def load_local_speakers(self):
        """Загружает список локальных колонок."""
        try:
            r = await self.session.get(
                "https://quasar.yandex.net/glagol/device_list"
            )
            resp = await r.json()
            return [
                {"device_id": d["id"], "name": d["name"], "platform": d["platform"]}
                for d in resp["devices"]
            ]

        except:
            _LOGGER.exception("Load local speakers")
            return None

    async def get_device_config(self, device: dict) -> (dict, str):
        did = device["id"]
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/v2/user/devices/{did}/configuration"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp["quasar_config"], resp["quasar_config_version"]

    async def set_device_config(self, device: dict, config: dict, version: str):
        _LOGGER.debug(f"Меняем конфиг станции: {config}")

        did = device["id"]
        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v3/user/devices/{did}/configuration/quasar",
            json={"config": config, "version": version}
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def get_device(self, device: dict):
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp

    async def device_action(self, device: dict, instance: str, value, relative=False):
        action = {
            "state": {"instance": instance, "value": value},
            "type": IOT_TYPES.get(instance, "devices.capabilities.custom.button"),
        }

        if relative:
            action["state"]["relative"] = True

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}/actions",
            json={"actions": [action]}
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        await asyncio.sleep(1)

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def get_device_action(self, device: dict, instance: str, value) -> list[dict]:
        _LOGGER.debug(f"Device action: {instance}={value}")

        action = {
            "state": {"instance": instance, "value": value},
            "type": IOT_TYPES[instance],
        }

        url = f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}/actions"
        r = await self.session.post(url, json={"actions": [action]})
        resp = await r.json()
        assert resp["status"] == "ok", resp

        return resp["devices"]

    async def device_actions(self, device: dict, **kwargs):
        _LOGGER.debug(f"Device action: {kwargs}")

        actions = []
        for k, v in kwargs.items():
            type_ = (
                "devices.capabilities.custom.button" if k.isdecimal() else IOT_TYPES[k]
            )
            state = (
                {"instance": k, "value": v, "relative": True}
                if k in ("volume", "channel")
                else {"instance": k, "value": v}
            )
            actions.append({"type": type_, "state": state})

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}/actions",
            json={"actions": actions}
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def device_color(self, device: dict, **kwargs):
        _LOGGER.debug(f"Device color: {kwargs}")

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v3/user/custom/group/color/apply",
            json={"device_ids": [device['id']], **kwargs}
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def update_online_stats(self):
        if not self.online_updated.is_set():
            await self.online_updated.wait()
            return

        self.online_updated.clear()

        try:
            r = await self.session.get(
                "https://quasar.yandex.ru/devices_online_stats"
            )
            resp = await r.json()
            assert resp["status"] == "ok", resp
        except:
            return
        finally:
            self.online_updated.set()

        for speaker in resp["items"]:
            for device in self.devices:
                if (
                    "quasar_info" not in device
                    or device["quasar_info"]["device_id"] != speaker["id"]
                ):
                    continue
                device["online"] = speaker["online"]
                break

    async def connect(self):
        r = await self.session.get(
            "https://iot.quasar.yandex.ru/m/v3/user/devices"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        for house in resp["households"]:
            if "sharing_info" in house:
                continue
            for device in house["all"]:
                self.dispatch_update(device["id"], device)

        ws = await self.session.ws_connect(resp["updates_url"], heartbeat=60)
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                break
            resp = msg.json()
            operation = resp.get("operation")
            if operation == "update_states":
                try:
                    resp = json.loads(resp["message"])
                    for device in resp["updated_devices"]:
                        self.dispatch_update(device["id"], device)
                except Exception as e:
                    _LOGGER.debug(f"Parse quasar update error: {msg.data}", exc_info=e)

            elif operation == "update_scenario_list":
                if '"source":"create_scenario_launch"' in resp["message"]:
                    _ = asyncio.create_task(self.get_voice_trigger(1))

    async def devices_passive_update(self, *args):
        try:
            r = await self.session.get(
                f"https://iot.quasar.yandex.ru/m/v3/user/devices", 
                timeout=15
            )
            resp = await r.json()
            assert resp["status"] == "ok", resp

            for house in resp["households"]:
                if "sharing_info" in house:
                    continue
                for device in house["all"]:
                    self.dispatch_update(device["id"], device)
        except Exception as e:
            _LOGGER.debug(f"Devices forceupdate problem: {repr(e)}")

    async def get_voice_trigger(self, retries: int = 0):
        try:
            r = await self.session.get(
                "https://iot.quasar.yandex.ru/m/user/scenarios/history"
            )
            raw = await r.json()

            for scenario in raw["scenarios"]:
                if scenario["trigger_type"] == "scenario.trigger.voice":
                    break
            else:
                return

            r = await self.session.get(
                f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/launches/{scenario['id']}"
            )
            raw = await r.json()

            for step in raw["launch"]["steps"]:
                for item in step["parameters"]["items"]:
                    if item["type"] != "step.action.item.device":
                        continue
                    device = item["value"]
                    if "quasar_info" not in device:
                        continue
                    device["scenario_name"] = raw["launch"]["name"]
                    self.dispatch_update(device["id"], device)

        except Exception as e:
            _LOGGER.debug("Can't get voice scenario", exc_info=e)

    async def run_forever(self):
        while not self.session.closed:
            try:
                await self.connect()
            except Exception as e:
                _LOGGER.debug("Quasar update error", exc_info=e)
            await asyncio.sleep(30)

    def start(self):
        self.updates_task = asyncio.create_task(self.run_forever())

    def stop(self):
        if self.updates_task:
            self.updates_task.cancel()
        self.dispatcher.clear()

    async def set_account_config(self, key: str, value):
        kv = ACCOUNT_CONFIG.get(key)
        assert kv and value in kv["values"], f"{key}={value}"

        if kv.get("api") == "user/settings":
            r = await self.session.post(
                f"https://iot.quasar.yandex.ru/m/user/settings",
                json={kv["key"]: kv["values"][value]}
            )

        else:
            r = await self.session.get(
                "https://quasar.yandex.ru/get_account_config"
            )
            resp = await r.json()
            assert resp["status"] == "ok", resp

            payload: dict = resp["config"]
            payload[kv["key"]] = kv["values"][value]

            r = await self.session.post(
                "https://quasar.yandex.ru/set_account_config", 
                json=payload
            )

        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def get_alarms(self, device: dict):
        r = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/get_alarms",
            json={"device_ids": [device["quasar_info"]["device_id"]]},
            headers=ALARM_HEADERS
        )
        resp = await r.json()
        return resp["alarms"]

    async def create_alarm(self, device: dict, alarm: dict) -> bool:
        alarm["device_id"] = device["quasar_info"]["device_id"]
        resp = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/create_alarm",
            json={"alarm": alarm, "device_type": device["type"]},
            headers=ALARM_HEADERS
        )
        return resp.ok

    async def change_alarm(self, device: dict, alarm: dict) -> bool:
        alarm["device_id"] = device["quasar_info"]["device_id"]
        resp = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/change_alarm",
            json={"alarm": alarm, "device_type": device["type"]},
            headers=ALARM_HEADERS
        )
        return resp.ok

    async def cancel_alarms(self, device: dict, alarm_id: str) -> bool:
        resp = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/cancel_alarms",
            json={
                "device_alarm_ids": [
                    {
                        "alarm_id": alarm_id,
                        "device_id": device["quasar_info"]["device_id"],
                    }
                ],
            },
            headers=ALARM_HEADERS
        )
        return resp.ok


ALARM_HEADERS = {
    "accept": "application/json",
    "origin": "https://yandex.ru",
    "x-ya-app-type": "iot-app",
    "x-ya-application": '{"app_id":"unknown","uuid":"unknown","lang":"ru"}',
}


BOOL_CONFIG = {"да": True, "нет": False}
ACCOUNT_CONFIG = {
    "без лишних слов": {
        "api": "user/settings",
        "key": "iot",
        "values": {
            "да": {"response_reaction_type": "sound"},
            "нет": {"response_reaction_type": "nlg"},
        },
    },
    "ответить шепотом": {
        "api": "user/settings",
        "key": "tts_whisper",
        "values": BOOL_CONFIG,
    },
    "анонсировать треки": {
        "api": "user/settings",
        "key": "music",
        "values": {
            "да": {"announce_tracks": True},
            "нет": {"announce_tracks": False},
        },
    },
    "скрывать названия товаров": {
        "api": "user/settings",
        "key": "order",
        "values": {
            "да": {"hide_item_names": True},
            "нет": {"hide_item_names": False},
        },
    },
    "звук активации": {"key": "jingle", "values": BOOL_CONFIG},
    "одним устройством": {
        "key": "smartActivation",
        "values": BOOL_CONFIG,
    },
    "понимать детей": {
        "key": "useBiometryChildScoring",
        "values": BOOL_CONFIG,
    },
    "рассказывать о навыках": {
        "key": "aliceProactivity",
        "values": BOOL_CONFIG,
    },
    "адаптивная громкость": {
        "key": "aliceAdaptiveVolume",
        "values": {
            "да": {"enabled": True},
            "нет": {"enabled": False},
        },
    },
    "кроссфейд": {
        "key": "audio_player",
        "values": {
            "да": {"crossfadeEnabled": True},
            "нет": {"crossfadeEnabled": False},
        },
    },
    "взрослый голос": {
        "key": "contentAccess",
        "values": {
            "умеренный": "medium",
            "семейный": "children",
            "безопасный": "safe",
            "без ограничений": "without",
        },
    },
    "детский голос": {
        "key": "childContentAccess",
        "values": {
            "безопасный": "safe",
            "семейный": "children",
        },
    },
    "имя": {
        "key": "spotter",
        "values": {
            "алиса": "alisa",
            "яндекс": "yandex",
        },
    },
}
