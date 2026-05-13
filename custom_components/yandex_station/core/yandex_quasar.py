import asyncio
import json
import logging
import ssl
from datetime import datetime

import aiohttp

from .quasar_info import has_quasar
from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)


async def _safe_response_json(r):
    """Parse response as JSON, fallback to text if content-type is not JSON."""
    try:
        return await r.json()
    except Exception:
        try:
            text = await r.text()
            return json.loads(text)
        except Exception:
            return {"status": "error", "raw": (text[:1000] if 'text' in locals() else None)}

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

    def _official_headers(self) -> dict:
        if not self.session.x_token:
            raise Exception("x_token required")
        return {
            "Authorization": f"Bearer {self.session.x_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _official_query_device(self, device_id: str) -> dict:
        r = await self.session.post(
            "https://api.iot.yandex.net/v1.0/user/devices/query",
            headers=self._official_headers(),
            json={"devices": [{"id": device_id}]},
        )
        try:
            resp = await _safe_response_json(r)
            devices = resp.get("devices") or []
            if devices:
                return devices[0]
            raise Exception(f"Official query response without devices: {resp}")
        finally:
            r.close()

    async def _official_action(self, actions: list[dict]) -> dict:
        r = await self.session.post(
            "https://api.iot.yandex.net/v1.0/user/devices/action",
            headers=self._official_headers(),
            json={"payload": {"devices": actions}},
        )
        try:
            return await _safe_response_json(r)
        finally:
            r.close()

    async def _official_list_devices(self) -> list[dict]:
        r = await self.session.get(
            "https://api.iot.yandex.net/v1.0/user/devices",
            headers=self._official_headers(),
            timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
        )
        try:
            resp = await _safe_response_json(r)
            devices = resp.get("devices")
            if not isinstance(devices, list):
                raise Exception(f"Official list response without devices: {resp}")
            return devices
        finally:
            r.close()

    async def _legacy_list_devices(self) -> list[dict]:
        """Fallback: list devices via internal quasar API (includes quasar_info)."""
        r = await self.session.get(
            "https://iot.quasar.yandex.ru/m/v3/user/devices",
            timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
            ssl=self._get_ssl_context(),
        )
        try:
            raw = await asyncio.wait_for(r.read(), timeout=20)
            resp = json.loads(raw.decode("utf-8", errors="replace"))
            assert resp.get("status") == "ok", resp
        finally:
            r.close()

        devices: list[dict] = []
        for house in resp.get("households", []):
            if "sharing_info" in house:
                continue
            for device in house.get("all", house.get("devices", [])):
                devices.append(device)
        return devices

    async def _official_query_devices(self, device_ids: list[str]) -> list[dict]:
        if not device_ids:
            return []

        r = await self.session.post(
            "https://api.iot.yandex.net/v1.0/user/devices/query",
            headers=self._official_headers(),
            json={"devices": [{"id": did} for did in device_ids]},
            timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
        )
        try:
            resp = await _safe_response_json(r)
            devices = resp.get("devices")
            if not isinstance(devices, list):
                raise Exception(f"Official query response without devices: {resp}")
            return devices
        finally:
            r.close()

    def _merge_official_devices(
        self, listed: list[dict], queried: list[dict], dispatch: bool = False
    ):
        prev_by_id = {d["id"]: d for d in self.devices or [] if "id" in d}
        queried_by_id = {d["id"]: d for d in queried if "id" in d}

        merged_devices: list[dict] = []
        for listed_device in listed:
            did = listed_device.get("id")
            if not did:
                continue

            prev = prev_by_id.get(did, {})
            queried_device = queried_by_id.get(did, {})

            merged = {**prev, **listed_device, **queried_device}
            merged.setdefault("item_type", "device")

            room = merged.get("room")
            if isinstance(room, dict):
                room_name = room.get("name")
                if room_name:
                    merged["room_name"] = room_name
            elif isinstance(room, str) and room:
                merged["room_name"] = room

            merged_devices.append(merged)

        self.devices = merged_devices

        if not dispatch:
            return

        for device in self.devices:
            self.dispatch_update(device["id"], device)



    async def init(self):
        """Основная инициализация. По умолчанию используем Legacy Quasar API, так как Official API часто недоступен."""
        _LOGGER.info("=" * 70)
        _LOGGER.info("🚀 QUASAR INITIALIZATION STARTED")
        _LOGGER.debug(f"x_token present: {bool(self.session.x_token)}")
        
        # Режим работы API. По умолчанию Legacy, так как Official API v1.0 требует особых прав (OAuth scope).
        use_official = False 

        try:
            if use_official:
                try:
                    _LOGGER.info("📡 Trying official API v1.0...")
                    listed = await self._official_list_devices()
                    queried = await self._official_query_devices(
                        [d["id"] for d in listed if d.get("id")]
                    )
                    self._merge_official_devices(listed, queried, dispatch=False)
                    _LOGGER.info("✅ Official API v1.0 succeeded")
                except Exception as official_err:
                    _LOGGER.warning(f"⚠️ Official API failed ({official_err}), falling back to legacy...")
                    listed = await self._legacy_list_devices()
                    self._merge_official_devices(listed, [], dispatch=False)
                    _LOGGER.info("✅ Legacy API mode (fallback)")
            else:
                _LOGGER.info("📡 Using Legacy Quasar API as primary (iot.quasar.yandex.ru)")
                listed = await self._legacy_list_devices()
                self._merge_official_devices(listed, [], dispatch=False)
                _LOGGER.info("✅ Legacy API mode")

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
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
            device.update(resp["quasar_info"])
        finally:
            r.close()

    async def load_scenarios(self):
        """Получает список сценариев."""
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/user/scenarios",
            timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
            ssl=self._get_ssl_context(),
        )
        try:
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
        finally:
            r.close()

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
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok"

            payload = parse_scenario(resp["scenario"])
        finally:
            r.close()

        r = await self.session.put(
            f"https://iot.quasar.yandex.ru/m/v3/user/scenarios/{sid}", 
            json=payload
        )
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
        finally:
            r.close()

    async def add_scenario(self, device_id: str, hash: str) -> str:
        """Добавляет сценарий-пустышку."""
        payload = scenario_speaker_tts("ХА " + device_id, hash, device_id, "пустышка")
        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios", 
            json=payload
        )
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
            return resp["scenario_id"]
        finally:
            r.close()

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
            json=payload,
        )
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
        finally:
            r.close()

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}/actions"
        )
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
        finally:
            r.close()

    async def load_local_speakers(self):
        """Загружает список локальных колонок."""
        try:
            r = await self.session.get(
                "https://quasar.yandex.net/glagol/device_list"
            )
            try:
                resp = await _safe_response_json(r)
                return [
                    {"device_id": d["id"], "name": d["name"], "platform": d["platform"]}
                    for d in resp.get("devices", [])
                ]
            finally:
                r.close()

        except:
            _LOGGER.exception("Load local speakers")
            return None

    async def get_device_config(self, device: dict) -> tuple[dict, str]:
        did = device["id"]
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/v2/user/devices/{did}/configuration"
        )
        try:
            raw = await asyncio.wait_for(r.read(), timeout=20)
            resp = json.loads(raw.decode('utf-8', errors='replace'))
            assert resp["status"] == "ok", resp
        except asyncio.TimeoutError:
            raise Exception(f"Timeout reading device config for {did}")
        except Exception as e:
            _LOGGER.error(f"Failed to parse device config: {e}")
            raise
        finally:
            r.close()
        return resp["quasar_config"], resp["quasar_config_version"]

    async def set_device_config(self, device: dict, config: dict, version: str):
        _LOGGER.debug(f"Меняем конфиг станции: {config}")

        did = device["id"]
        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v3/user/devices/{did}/configuration/quasar",
            json={"config": config, "version": version},
        )
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
        finally:
            r.close()

    async def get_device(self, device: dict):
        try:
            # Пытаемся получить данные об одном устройстве через Legacy, если официальный API недоступен
            listed = await self._legacy_list_devices()
            queried = next((d for d in listed if d.get("id") == device["id"]), None)
            if not queried:
                raise Exception("Device not found in legacy list")
        except Exception as e:
            _LOGGER.debug(f"Legacy get_device failed ({e}), trying official")
            queried = await self._official_query_device(device["id"])

        return {
            "status": "ok",
            "id": queried.get("id", device["id"]),
            "name": queried.get("name", device.get("name")),
            "capabilities": queried.get("capabilities", []),
            "properties": queried.get("properties", []),
            "type": queried.get("type", device.get("type")),
            "state": queried.get("state"),
        }

    async def device_action(self, device: dict, instance: str, value, relative=False):
        action = {
            "state": {"instance": instance, "value": value},
            "type": IOT_TYPES.get(instance, "devices.capabilities.custom.button"),
        }

        if relative:
            action["state"]["relative"] = True
        # Prefer Legacy Quasar action endpoint (more reliable for many devices)
        try:
            item_type = device.get("item_type", "device")
            r = await self.session.post(
                f"https://iot.quasar.yandex.ru/m/user/{item_type}s/{device['id']}/actions",
                json={"actions": [action]},
            )
            try:
                resp = await _safe_response_json(r)
            finally:
                r.close()

            if resp.get("status") == "ok":
                _LOGGER.debug(f"Legacy action succeeded for {device['id']}: {action}")
            else:
                raise Exception(f"Legacy action failed: {resp}")

        except Exception as e:
            _LOGGER.debug(f"Legacy action failed ({e}), trying official API")
            # Try official API as fallback
            try:
                official_payload = [{"id": device["id"], "actions": [action]}]
                official_resp = await self._official_action(official_payload)
                if official_resp.get("status") == "ok":
                    _LOGGER.debug(f"Official action succeeded for {device['id']}: {action}")
                else:
                    raise Exception(f"Official action failed: {official_resp}")
            except Exception as e2:
                _LOGGER.warning(f"All action methods failed for {device.get('id')}: {e2}")

        await asyncio.sleep(1)

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def get_device_action(self, device: dict, instance: str, value) -> list[dict]:
        _LOGGER.debug(f"Device action: {instance}={value}")

        action = {
            "state": {"instance": instance, "value": value},
            "type": IOT_TYPES[instance],
        }

        try:
            official_payload = [{"id": device["id"], "actions": [action]}]
            resp = await self._official_action(official_payload)
            if resp.get("status") == "ok":
                return resp.get("devices", [])
        except Exception:
            pass
            
        return []

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

        try:
            official_payload = [{"id": device["id"], "actions": actions}]
            official_resp = await self._official_action(official_payload)
        except Exception:
            pass

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def device_color(self, device: dict, **kwargs):
        _LOGGER.debug(f"Device color: {kwargs}")

        actions = []
        for instance, value in kwargs.items():
            actions.append(
                {
                    "type": IOT_TYPES[instance],
                    "state": {"instance": instance, "value": value},
                }
            )

        official_payload = [{"id": device["id"], "actions": actions}]
        official_resp = await self._official_action(official_payload)
        if official_resp.get("status") != "ok":
            raise Exception(f"Official color action failed: {official_resp}")

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def update_online_stats(self):
        if not self.online_updated.is_set():
            await self.online_updated.wait()
            return

        self.online_updated.clear()

        try:
            # Обновляем статусы через Legacy API, чтобы не ловить 404 от официального
            _LOGGER.debug("Updating online stats via Legacy API")
            listed = await self._legacy_list_devices()
            
            # Создаем словарь текущих состояний из полученного списка
            online_map = {}
            for device in listed:
                did = device.get("id")
                if did:
                    # В легаси API статус обычно в поле 'online' или 'state'
                    online_map[did] = device.get("online", device.get("state") == "online")
            
            # Обновляем локальный список устройств
            for device in self.devices or []:
                did = device.get("id")
                if did in online_map:
                    device["online"] = online_map[did]
                    
        except Exception as e:
            _LOGGER.debug(f"Failed to update online stats via legacy: {e}")
            return
        finally:
            self.online_updated.set()

    async def connect(self):
        try:
            # Всегда предпочитаем Legacy API для стабильности
            _LOGGER.debug("Connecting via Legacy Quasar API")
            listed = await self._legacy_list_devices()
            queried = []
        except Exception as e:
            _LOGGER.warning(f"Legacy API unavailable in connect ({e}), trying official")
            try:
                listed = await self._official_list_devices()
                queried = await self._official_query_devices(
                    [d["id"] for d in listed if d.get("id")]
                )
            except Exception as e2:
                _LOGGER.error(f"Both APIs failed in connect: {e2}")
                return
        self._merge_official_devices(listed, queried, dispatch=True)

    async def devices_passive_update(self, *args):
        try:
            try:
                # Пассивное обновление тоже через Legacy
                listed = await self._legacy_list_devices()
                queried = []
            except Exception as e:
                _LOGGER.debug(f"Legacy API in passive update ({e}), trying official")
                listed = await self._official_list_devices()
                queried = await self._official_query_devices(
                    [d["id"] for d in listed if d.get("id")]
                )
            self._merge_official_devices(listed, queried, dispatch=True)
        except Exception as e:
            _LOGGER.debug(f"Devices forceupdate problem: {repr(e)}")

    async def get_voice_trigger(self, retries: int = 0):
        try:
            r = await self.session.get(
                "https://iot.quasar.yandex.ru/m/user/scenarios/history"
            )
            try:
                raw = await _safe_response_json(r)
            finally:
                r.close()

            for scenario in raw["scenarios"]:
                if scenario["trigger_type"] == "scenario.trigger.voice":
                    break
            else:
                return

            r = await self.session.get(
                f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/launches/{scenario['id']}"
            )
            try:
                raw = await _safe_response_json(r)
            finally:
                r.close()

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
            try:
                resp = await _safe_response_json(r)
                assert resp["status"] == "ok", resp
                payload: dict = resp["config"]
            finally:
                r.close()
            
            payload[kv["key"]] = kv["values"][value]

            r = await self.session.post(
                "https://quasar.yandex.ru/set_account_config", 
                json=payload
            )
        
        try:
            resp = await _safe_response_json(r)
            assert resp["status"] == "ok", resp
        finally:
            r.close()

    async def get_alarms(self, device: dict):
        r = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/get_alarms",
            json={"device_ids": [device["quasar_info"]["device_id"]]},
            headers=ALARM_HEADERS,
        )
        try:
            resp = await _safe_response_json(r)
            return resp.get("alarms", [])
        finally:
            r.close()

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
