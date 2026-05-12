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

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar
from .core.yandex_session import LoginResponse, YandexSession

_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
class YandexStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Yandex Station."""
    VERSION = 1

    def __init__(self):
        super().__init__()
        self.cur_step = None

    @property
    @lru_cache()
    def yandex(self):
        session = async_create_clientsession(self.hass)
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
            return await self.async_step_auth(data)

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
                                "auth": "Пароль или одноразовый ключ",
                                "email": "Ссылка на E-mail",
                                "cookies": "Cookies",
                                "token": "Токен",
                            }
                        )
                    }
                ),
            )

        method = user_input["method"]
        if method == "qr":
            return self.async_show_form(
                step_id="qr",
                description_placeholders={
                    "qr_url": await self.yandex.get_qr(),
                    "ya_url": "https://passport.yandex.ru/profile",
                },
            )

        if method == "auth":
            return self.async_show_form(
                step_id=method,
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
            )

        if method == "email":
            return self.async_show_form(
                step_id=method,
                data_schema=vol.Schema({vol.Required("username"): str}),
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

    async def async_step_qr(self, user_input=None):
        if user_input is None:
            # Предотвращаем ошибку при первом заходе
            return self.async_show_form(
                step_id="qr",
                description_placeholders={
                    "qr_url": await self.yandex.get_qr(),
                    "ya_url": "https://passport.yandex.ru/profile",
                },
            )
            
        resp = await self.yandex.login_qr()
        if not resp:
            return self.async_show_form(
                step_id="qr",
                errors={"base": "unauthorised"},
                description_placeholders={
                    "qr_url": await self.yandex.get_qr(),
                    "ya_url": "https://passport.yandex.ru/profile",
                },
            )
        return await self._check_yandex_response(resp)

    async def async_step_auth(self, user_input=None):
        """User submited username and password. Or YAML error."""
        if user_input is None:
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
            )

        resp = await self.yandex.login_username(user_input["username"])
        if resp.ok:
            resp = await self.yandex.login_password(user_input["password"])
        return await self._check_yandex_response(resp)

    async def async_step_email(self, user_input):
        resp = await self.yandex.login_username(user_input["username"])
        if not resp.magic_link_email:
            self.cur_step["errors"] = {"base": "email.unsupported"}
            return self.cur_step

        await self.yandex.get_letter()
        return self.async_show_form(
            step_id="email2", description_placeholders={"email": resp.magic_link_email}
        )

    async def async_step_email2(self, user_input):
        resp = await self.yandex.login_letter()
        if not resp:
            self.cur_step["errors"] = {"base": "unauthorised"}
            return self.cur_step

        return await self._check_yandex_response(resp)

    async def async_step_cookies(self, user_input):
        resp = await self.yandex.login_cookies(user_input["cookies"])
        return await self._check_yandex_response(resp)

    async def async_step_token(self, user_input):
        # Показываем форму при первом заходе
        if user_input is None:
            return self.async_show_form(
                step_id="token",
                data_schema=vol.Schema(
                    {
                        vol.Required("token"): str,
                        vol.Required("token_type", default="x_token"): vol.In(
                            {"x_token": "x_token (account)", "music_token": "music_token (audio)"}
                        ),
                    }
                ),
            )

        token = user_input.get("token")
        token_type = user_input.get("token_type", "x_token")

        # Если пользователь указал music_token — сохраняем его сразу
        if token_type == "music_token":
            return self.async_create_entry(title="music_token", data={"music_token": token})

        # Иначе пробуем валидировать x_token
        resp = await self.yandex.validate_token(token)
        if resp and resp.ok:
            # Сохраняем x_token
            return self.async_create_entry(title=resp.display_login or "yandex", data={"x_token": token})

        # Если валидация не удалась — показываем ошибку на форме
        errors = {"base": resp.errors[0] if resp and resp.errors else "invalid_token"}
        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required("token"): str,
                    vol.Required("token_type", default="x_token"): vol.In(
                        {"x_token": "x_token (account)", "music_token": "music_token (audio)"}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_captcha(self, user_input):
        """User submited captcha. Or YAML error."""
        if user_input is None:
            return self.cur_step

        ok = await self.yandex.login_captcha(user_input["captcha_answer"])
        if not ok:
            return self.cur_step

        return self.async_show_form(
            step_id="captcha2",
            data_schema=vol.Schema(
                {
                    vol.Required("password"): str,
                }
            ),
        )

    async def async_step_captcha2(self, user_input):
        resp = await self.yandex.login_password(user_input["password"])
        return await self._check_yandex_response(resp)

    async def _check_yandex_response(self, resp: LoginResponse):
        """Check Yandex response. Handle captcha, 2FA, push, and log errors."""
        if resp.ok:
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

        # Сохраняем последний ответ для отображения ошибок в текущем шаге
        errors = {"base": resp.errors[0]} if resp.errors else {"base": "unknown_error"}

        # Капча
        if resp.error_captcha_required or (resp.errors and any("captcha" in e for e in resp.errors)):
            _LOGGER.debug(f"Captcha required: {resp.errors}")
            return self.async_show_form(
                step_id="captcha",
                data_schema=vol.Schema({vol.Required("captcha_answer"): str}),
                description_placeholders={"captcha_url": await self.yandex.get_captcha()},
                errors=errors
            )

        # 2FA (код из SMS, приложения, e-mail)
        if resp.errors and any(e in ("need_2fa", "2fa.required", "twofa.required") for e in resp.errors):
            _LOGGER.debug(f"2FA required: {resp.errors}")
            return self.async_show_form(
                step_id="twofa",
                data_schema=vol.Schema({vol.Required("twofa_code"): str}),
                description_placeholders={"info": "Введите код из SMS или приложения Яндекс."},
                errors=errors
            )

        # Push-код (подтверждение входа)
        if resp.errors and any("push.required" in e for e in resp.errors):
            _LOGGER.debug(f"Push confirmation required: {resp.errors}")
            return self.async_show_form(
                step_id="push",
                data_schema=vol.Schema({vol.Required("push_code"): str}),
                description_placeholders={"info": "Введите код из пуш-уведомления Яндекс."},
                errors=errors
            )

        # Неизвестная ошибка — показать форму с ошибкой
        _LOGGER.error(f"Yandex auth error: {resp.errors}")
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors
        )

        # Если ничего не подошло — логируем всё
        _LOGGER.error(f"Unknown Yandex response: {resp.raw}")
        raise AbortFlow("not_implemented")

    @callback
    def async_get_options_flow(self, config_entry: ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry):
        super().__init__(config_entry)
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict = None):
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        quasar: YandexQuasar = self.hass.data[DOMAIN][self._config_entry.unique_id]
        devices = {i["id"]: device_name(i) for i in quasar.devices}

        # sort by names
        devices = dict(sorted(devices.items(), key=lambda x: x[1]))

        defaults = dict(self._config_entry.options)
        if include := defaults.get("include"):
            # filter only existing devices
            defaults["include"] = [i for i in include if i in devices]

        data = vol_schema({vol.Optional("include"): cv.multi_select(devices)}, defaults)
        return self.async_show_form(step_id="init", data_schema=data)


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
