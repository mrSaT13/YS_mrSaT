"""
1. User can enter login/pass from GUI
2. User can set login/pass in YAML
3. If the password requires updating, user need to configure another component
   with the same login.
4. Captcha will be requested if necessary
5. If authorization through YAML does not work, user can continue it through
   the GUI.
"""

import logging
from functools import lru_cache

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util.ssl import SSLCipherList

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar
from .core.yandex_session import LoginResponse, YandexSession

_LOGGER = logging.getLogger(__name__)


def generate_qr_code(data: str) -> str:
    try:
        from homeassistant.auth.mfa_modules import totp

        # noinspection PyProtectedMember
        return totp._generate_qr_code(data)
    except Exception as e:
        return repr(e)


# noinspection PyUnusedLocal
class YandexStationFlowHandler(ConfigFlow, domain=DOMAIN):
    @property
    @lru_cache()
    def yandex(self):
        session = async_create_clientsession(self.hass, ssl_cipher=SSLCipherList.INTERMEDIATE)
        return YandexSession(session)

    async def async_step_import(self, data: dict):
        """Init by component setup. Forward YAML login/pass to auth."""
        await self.async_set_unique_id(data["username"])
        self._abort_if_unique_id_configured()

        if "x_token" in data:
            return self.async_create_entry(
                title=data["username"], data={"x_token": data["x_token"]}
            )

        else:
            return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Init by user via GUI"""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("method", default="qr"): vol.In(
                            {
                                "qr": "QR-код",
                                "cookies": "Cookies",
                                "token": "Токен",
                            }
                        )
                    }
                ),
            )

        method = user_input["method"]
        if method == "qr":
            qr_url = await self.yandex.get_qr()
            return self.async_show_form(
                step_id="qr",
                description_placeholders={
                    "qr_url": qr_url,
                    "qr_data": generate_qr_code(qr_url),
                    "ya_url": "https://passport.yandex.ru/profile",
                },
            )

        if method == "cookies":
            return self.async_show_form(
                step_id=method,
                data_schema=vol.Schema({vol.Required(method): str}),
                description_placeholders={
                    # hassfest prohibits the use of links in translation files
                    "ex_url": "https://chrome.google.com/webstore/detail/copy-cookies/jcbpglbplpblnagieibnemmkiamekcdg",
                    "ya_url": "https://passport.yandex.ru/profile",
                },
            )

        # cookies, token
        return self.async_show_form(
            step_id=method,
            data_schema=vol.Schema({vol.Required(method): str}),
        )

    async def async_step_qr(self, user_input):
        resp = await self.yandex.login_qr()
        if not resp:
            self.cur_step["errors"] = {"base": "unauthorised"}
            return self.cur_step
        self._login_method = "QR-код"
        return await self._check_yandex_response(resp)

    async def async_step_cookies(self, user_input):
        try:
            resp = await self.yandex.login_cookies(user_input["cookies"])
            self._login_method = "Cookies"
            return await self._check_yandex_response(resp)
        except Exception as e:
            _LOGGER.error(f"Cookies login failed: {e}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": "cookies.not_matched"}
                return self.cur_step
            raise

    async def async_step_token(self, user_input):
        try:
            resp = await self.yandex.validate_token(user_input["token"])
            self._login_method = "Токен"
            return await self._check_yandex_response(resp)
        except Exception as e:
            _LOGGER.error(f"Token validation failed: {e}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": "token.invalid"}
                return self.cur_step
            raise

    async def _check_yandex_response(self, resp: LoginResponse):
        """Check Yandex response. Do not create entry for the same login. Show
        captcha form if captcha required. Show auth form with error if error.
        """
        if not resp or not isinstance(resp, LoginResponse):
            _LOGGER.error(f"Invalid response type: {type(resp)}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": "unauthorised"}
                return self.cur_step
            raise AbortFlow("unauthorized")

        if resp.ok:
            if not resp.x_token:
                _LOGGER.error(f"No x_token in response")
                if self.cur_step:
                    self.cur_step["errors"] = {"base": "unauthorised"}
                    return self.cur_step
                raise AbortFlow("unauthorized")
            
            # Log which auth method was used
            login_type = getattr(self, "_login_method", "unknown")
            _LOGGER.info(f"Successful auth via {login_type}: {resp.display_login}")
            
            # set unique_id or return existing entry
            entry = await self.async_set_unique_id(resp.display_login)
            if entry:
                # update existing entry with same login
                self.hass.config_entries.async_update_entry(
                    entry, data={"x_token": resp.x_token}
                )
                return self.async_abort(reason="account_updated")
            else:
                # create new entry for new login
                return self.async_create_entry(
                    title=resp.display_login, data={"x_token": resp.x_token}
                )
        elif resp.errors:
            _LOGGER.warning(f"Yandex error: {resp.error}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": resp.error}
                return self.cur_step
        else:
            _LOGGER.error(f"Unknown response state: ok={resp.ok}, errors={resp.errors}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": "unauthorised"}
                return self.cur_step

        raise AbortFlow("unauthorized")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    @property
    def config_entry(self):
        return self.hass.config_entries.async_get_entry(self.handler)

    async def async_step_init(self, user_input: dict = None):
        """Show options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["devices", "matrix_bot", "music_assistant"]
        )

    async def async_step_devices(self, user_input: dict = None):
        """Configure devices to include."""
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        quasar: YandexQuasar = self.hass.data[DOMAIN][self.config_entry.unique_id]
        devices = {i["id"]: device_name(i) for i in quasar.devices}

        # sort by names
        devices = dict(sorted(devices.items(), key=lambda x: x[1]))

        defaults = dict(self.config_entry.options)
        if include := defaults.get("include"):
            # filter only existing devices
            defaults["include"] = [i for i in include if i in devices]

        data = vol_schema({vol.Optional("include"): cv.multi_select(devices)}, defaults)
        return self.async_show_form(step_id="devices", data_schema=data)

    async def async_step_matrix_bot(self, user_input: dict = None):
        """Configure Matrix bot."""
        if user_input is not None:
            # Save Matrix bot configuration
            options = dict(self.config_entry.options)
            options["matrix_bot"] = user_input
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_abort(reason="matrix_bot_configured")

        defaults = self.config_entry.options.get("matrix_bot", {})

        # Find conversation entities (Yandex Station speakers)
        conversation_entities = {}
        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(self.hass)
        for entity_id, entity in registry.entities.items():
            if entity.domain == "conversation" and entity.platform == "yandex_station":
                state = self.hass.states.get(entity_id)
                name = state.attributes.get("friendly_name", entity_id) if state else entity_id
                conversation_entities[entity_id] = name

        # Also check states for conversation entities
        for entity_id in self.hass.states.async_entity_ids("conversation"):
            if "yandex_station" in entity_id and entity_id not in conversation_entities:
                state = self.hass.states.get(entity_id)
                name = state.attributes.get("friendly_name", entity_id) if state else entity_id
                conversation_entities[entity_id] = name

        schema_dict = {
            vol.Required(
                "enabled",
                default=defaults.get("enabled", True),
            ): bool,
            vol.Required("server_url", default=defaults.get("server_url", "https://matrix.org")): str,
            vol.Required("room_id", default=defaults.get("room_id", "")): str,
            vol.Required("access_token", default=defaults.get("access_token", "")): str,
        }

        # Add speaker selection if conversation entities exist
        if conversation_entities:
            schema_dict[vol.Optional(
                "conversation_entity",
                default=defaults.get("conversation_entity", ""),
            )] = vol.In({**{"": "Авто (первая доступная)"}, **conversation_entities})

        data = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="matrix_bot",
            data_schema=data,
            description_placeholders={
                "docs": "https://github.com/mrSaT13/YandexStation/blob/master/custom_components/yandex_station/hass/MATRIX_BOT.md",
                "speaker_count": str(len(conversation_entities)),
            }
        )

    async def async_step_music_assistant(self, user_input: dict = None):
        """Configure Music Assistant integration."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            options["music_assistant"] = user_input
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_abort(reason="music_assistant_configured")

        defaults = self.config_entry.options.get("music_assistant", {})

        from .hass.music_assistant_bridge import get_bridge, MusicAssistantBridge
        bridge = get_bridge(self.hass)

        # Try to discover players from all available sources
        ma_players = bridge.get_all_ma_players()
        all_players = bridge.get_all_media_players()

        # If URL+token configured, also fetch players via direct REST API
        direct_players = {}
        ma_url = defaults.get("ma_url", "")
        ma_token = defaults.get("ma_token", "")
        ma_status = []

        if ma_url and ma_token:
            try:
                import aiohttp
                headers = {"Authorization": f"Bearer {ma_token}",
                           "Content-Type": "application/json"}
                url = f"{ma_url.rstrip('/')}/api/players"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, list):
                                for p in data:
                                    pid = p.get("player_id", p.get("id", ""))
                                    name = p.get("name", pid)
                                    state = p.get("state", {}).get("status", "idle")
                                    direct_players[pid] = f"{name} [{state}] (API)"
                                ma_status.append(f"API: найдено {len(direct_players)} плееров")
                            else:
                                ma_status.append(f"API: неожиданный формат ответа")
                        else:
                            ma_status.append(f"API: ошибка {resp.status}")
            except Exception as e:
                ma_status.append(f"API: {e}")

        # Yandex Station speakers
        yandex_speakers = {}
        from .core.const import DATA_SPEAKERS
        speakers = self.hass.data.get(DOMAIN, {}).get(DATA_SPEAKERS, {})
        for did, speaker in speakers.items():
            entity = speaker.get("entity")
            if entity and entity.hass:
                name = speaker.get("name", entity.entity_id)
                yandex_speakers[entity.entity_id] = name

        # MA status info
        ma_status.insert(0, f"MA доступен: {'Да' if bridge.is_ma_available() else 'Нет'}")
        ma_status.insert(1, f"HA плееров: {len(ma_players)}, API плееров: {len(direct_players)}")

        # Build player choices — merge all sources
        player_choices = {"": "Автоматически"}
        # Direct API players first (most relevant when URL+token set)
        for eid, name in direct_players.items():
            player_choices[eid] = name
        # HA-integrated players
        for eid, name in ma_players.items():
            if eid not in player_choices:
                player_choices[eid] = name
        # Fallback: all media players
        if len(player_choices) <= 1:
            for eid, name in all_players.items():
                player_choices[eid] = f"{name} (не MA)"

        schema_dict = {
            vol.Required(
                "enabled",
                default=defaults.get("enabled", False),
            ): bool,
        }

        # MA URL and token — shown FIRST so user can fill them in
        schema_dict[vol.Optional(
            "ma_url",
            description={"suggested_value": defaults.get("ma_url", "")},
        )] = str

        schema_dict[vol.Optional(
            "ma_token",
            description={"suggested_value": defaults.get("ma_token", "")},
        )] = str

        # Player selection — dropdown if players found, text input otherwise
        if len(player_choices) > 1:
            schema_dict[vol.Optional(
                "ma_player",
                default=defaults.get("ma_player", ""),
            )] = vol.In(player_choices)
        else:
            schema_dict[vol.Optional(
                "ma_player",
                description={"suggested_value": defaults.get("ma_player", "")},
            )] = str

        if yandex_speakers:
            schema_dict[vol.Optional(
                "yandex_speaker",
                default=defaults.get("yandex_speaker", ""),
            )] = vol.In({**{"": "Все колонки"}, **yandex_speakers})

        schema_dict.update({
            vol.Optional("announce", default=defaults.get("announce", True)): bool,
            vol.Optional("clear_queue", default=defaults.get("clear_queue", True)): bool,
            vol.Optional("shuffle", default=defaults.get("shuffle", True)): bool,
            vol.Optional(
                "repeat",
                default=defaults.get("repeat", "off"),
            ): vol.In({"off": "Выкл", "one": "Повтор трека", "all": "Повтор плейлиста"}),
            vol.Optional(
                "enqueue_mode",
                default=defaults.get("enqueue_mode", "replace"),
            ): vol.In({"replace": "Заменить очередь", "next": "Добавить следующим", "add": "Добавить в конец"}),
            vol.Optional("fallback_to_similar", default=defaults.get("fallback_to_similar", True)): bool,
            vol.Optional(
                "volume",
                default=defaults.get("volume", 0),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        })

        return self.async_show_form(
            step_id="music_assistant",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "info": "\n".join(ma_status),
            }
        )


def vol_schema(schema: dict, defaults: dict | None) -> vol.Schema:
    if defaults:
        for key in schema:
            if (value := defaults.get(key.schema)) is not None:
                key.default = vol.default_factory(value)
    return vol.Schema(schema)


def device_name(device: dict) -> str:
    if room := device.get("room_name"):
        return f"{device['house_name']} - {room} - {device['name']}"
    return f"{device['house_name']} - {device['name']}"
