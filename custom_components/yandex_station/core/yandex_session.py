"""
Yandex supports base auth methods:
- password
- magic_link - auth via link to email
- sms_code - auth via pin code to mobile phone
- magic (otp?) - auth via key-app (30 seconds password)
- magic_x_token - auth via QR-code (do not need username)

Advanced auth methods:
- x_token - auth via super-token (1 year)
- cookies - auth via cookies from passport.yandex.ru site

Errors:
- account.not_found - wrong login
- password.not_matched
- captcha.required
"""

import asyncio
import base64
import json
import logging
import pickle
import re
import time

from aiohttp import ClientSession

# Импорт библиотеки для авторизации
try:
    from ya_passport_auth import PassportClient, Credentials
    from ya_passport_auth.exceptions import QRTimeoutError, YaPassportError
    YA_PASSPORT_AVAILABLE = True
except ImportError:
    YA_PASSPORT_AVAILABLE = False

_LOGGER = logging.getLogger(__name__)


class LoginResponse:
    """Response wrapper for Yandex login."""

    def __init__(self, resp: dict):
        self.raw = resp

    @property
    def ok(self):
        return self.raw.get("status") == "ok"

    @property
    def errors(self):
        return self.raw.get("errors", [])

    @property
    def error(self):
        return self.raw["errors"][0] if self.errors else None

    @property
    def display_login(self):
        return self.raw.get("display_login")

    @property
    def x_token(self):
        return self.raw.get("x_token")

    @property
    def magic_link_email(self):
        return self.raw.get("magic_link_email")

    @property
    def error_captcha_required(self):
        return "captcha.required" in self.errors


class BasicSession:
    _session: ClientSession
    domain: str = None
    proxy: str = None
    ssl: bool = None

    def _request(self, method: str, url: str, **kwargs):
        """Internal request function with global support proxy and ssl options."""
        if self.domain:
            url = url.replace("yandex.ru", self.domain)
        kwargs["proxy"] = self.proxy
        kwargs["ssl"] = self.ssl
        kwargs.setdefault("timeout", 5.0)
        return getattr(self._session, method)(url, **kwargs)

    def _get(self, url: str, **kwargs):
        return self._request("get", url, **kwargs)

    def _post(self, url: str, **kwargs):
        return self._request("post", url, **kwargs)

    @property
    def closed(self):
        return self._session.closed

    @property
    def client_session(self):
        return self._session


class YandexSession(BasicSession):
    """Class for login in yandex via username, token, captcha."""

    auth_payload: dict = None
    csrf_token = None
    last_ts: float = 0
    
    # Для QR-авторизации через ya-passport-auth
    _passport_client = None
    _qr_session = None

    def __init__(
        self,
        session: ClientSession,
        x_token: str = None,
        music_token: str = None,
        cookie: str = None,
    ):
        """
        :param x_token: optional x-token
        :param music_token: optional token for glagol API
        :param cookie: optional base64 cookie from last session
        """
        self._session = session
        setattr(session.cookie_jar, "_quote_cookie", False)

        self.x_token = x_token
        self.music_token = music_token
        if cookie:
            cookie_jar = session.cookie_jar
            _cookies = cookie_jar._cookies
            try:
                raw = base64.b64decode(cookie)
                cookie_jar._cookies = pickle.loads(raw)
                cookie_jar.clear(lambda x: False)
            except:
                cookie_jar._cookies = _cookies

        self._update_listeners = []

    def add_update_listener(self, coro):
        """Listeners to handle automatic cookies update."""
        self._update_listeners.append(coro)

    async def _get_csrf_token(self):
        """Get CSRF token with fallback for new Yandex Passport format."""
        r = await self._get("https://passport.yandex.ru/am?app_platform=android")
        resp = await r.text()
        
        if r.status != 200 or "<title>400" in resp:
            raise Exception(
                f"Yandex passport returned {r.status}. "
                f"Check proxy/VPN settings."
            )
        
        m = re.search(r'"csrf_token" value="([^"]+)"', resp)
        if not m:
            m = re.search(r'window\.__CSRF__\s*=\s*"([^"]+)"', resp)
        
        assert m, f"CSRF token not found in response: {resp[:500]}"
        return m[1]

    async def login_username(self, username: str) -> LoginResponse:
        """Create login session and return supported auth methods."""
        csrf_token = await self._get_csrf_token()
        self.auth_payload = {"csrf_token": csrf_token}

        # Используем новый BFF эндпоинт для multistep_start
        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/multistep_start",
            headers={
                "X-CSRF-Token": csrf_token,
                "Origin": "https://passport.yandex.ru",
                "Referer": "https://passport.yandex.ru/am?app_platform=android",
            },
            data={"login": username},
        )
        resp = await r.json()
        if resp.get("can_register") is True:
            return LoginResponse({"errors": ["account.not_found"]})

        assert resp.get("status") == "ok", resp
        self.auth_payload["track_id"] = resp["track_id"]
        return LoginResponse(resp)

    async def login_password(self, password: str) -> LoginResponse:
        """Login using password or key-app (30 second password)."""
        assert self.auth_payload
        # Используем новый BFF эндпоинт для password/submit
        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/password/submit",
            headers={
                "X-CSRF-Token": self.auth_payload["csrf_token"],
                "Origin": "https://passport.yandex.ru",
                "Referer": "https://passport.yandex.ru/am?app_platform=android",
            },
            data={
                "track_id": self.auth_payload["track_id"],
                "password": password,
                "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login",
            },
        )
        resp = await r.json()
        if resp.get("status") != "ok":
            return LoginResponse(resp)
        if "redirect_url" in resp:
            return LoginResponse({"errors": ["redirect.unsupported"]})
        return await self.login_cookies()

    async def get_qr(self) -> str:
        """Get link to QR-code auth."""
        # Fallback to legacy if library fails or not available
        if not YA_PASSPORT_AVAILABLE:
            _LOGGER.debug("ya-passport-auth not available, using legacy BFF method")
            return await self._get_qr_legacy()
        
        try:
            # Правильная инициализация без await
            self._passport_client = PassportClient()
            
            # Если нужен прокси, библиотека обычно берёт его из окружения или session
            # Если ошибка останется - fallback сработает автоматически
            
            self._qr_session = await self._passport_client.start_qr_login()
            return self._qr_session.qr_url
            
        except Exception as e:
            _LOGGER.warning(f"QR auth library error: {e}. Falling back to legacy method.")
            return await self.get_qr_legacy()  # Рекурсивно вызовем fallback

    async def _get_qr_legacy(self) -> str:
        """Stable legacy QR method using BFF endpoints."""
        r = await self._get("https://passport.yandex.ru/am?app_platform=android")
        resp = await r.text()
        
        m = re.search(r'"csrf_token" value="([^"]+)"', resp)
        if not m:
            m = re.search(r'window\.__CSRF__\s*=\s*"([^"]+)"', resp)
        assert m, f"CSRF not found: {resp[:300]}"
        csrf = m[1]
        
        # BFF multistep_start
        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/multistep_start",
            headers={
                "X-CSRF-Token": csrf,
                "Origin": "https://passport.yandex.ru",
                "Referer": "https://passport.yandex.ru/am?app_platform=android",
            },
            data={}
        )
        resp = await r.json()
        assert resp.get("status") == "ok", resp
        track_id = resp["track_id"]
        
        # BFF password/submit with with_code=1 for QR
        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/password/submit",
            headers={
                "X-CSRF-Token": csrf,
                "Origin": "https://passport.yandex.ru",
                "Referer": "https://passport.yandex.ru/am?app_platform=android",
            },
            data={"track_id": track_id, "with_code": 1, "retpath": "https://passport.yandex.ru/profile"}
        )
        resp = await r.json()
        assert resp.get("status") == "ok", resp
        
        self.auth_payload = {"csrf_token": resp["csrf_token"], "track_id": track_id}
        return f"https://passport.yandex.ru/auth/magic/code/?track_id={track_id}"

    async def login_qr(self) -> LoginResponse:
        """Poll QR confirmation."""
        # Если используется библиотека
        if self._passport_client and self._qr_session and YA_PASSPORT_AVAILABLE:
            try:
                # Неблокирующая проверка статуса
                status = await self._passport_client.check_qr_status(self._qr_session)
                if status.is_confirmed:
                    creds = await self._passport_client.get_credentials(self._qr_session)
                    self.x_token = creds.x_token
                    return await self.validate_token(self.x_token)
                return LoginResponse({})
            except Exception as e:
                _LOGGER.debug(f"QR poll library error: {e}")
                return LoginResponse({})
        
        # Legacy fallback polling
        return await self._login_qr_legacy()

    async def _login_qr_legacy(self) -> LoginResponse:
        """Legacy QR polling method."""
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/auth/new/magic/status/", data=self.auth_payload
        )
        resp = await r.json()
        if resp.get("status") != "ok":
            return LoginResponse({})
        return await self.login_cookies()
    async def get_sms(self):
        """Request an SMS to user phone."""
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code-submit",
            data={**self.auth_payload, "mode": "tracked"},
        )
        resp = await r.json()
        assert resp["status"] == "ok"

    async def login_sms(self, code: str) -> LoginResponse:
        """Login with code from SMS."""
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code",
            data={**self.auth_payload, "mode": "tracked", "code": code},
        )
        resp = await r.json()
        assert resp["status"] == "ok"

        r = await self._post(
            "https://passport.yandex.ru/registration-validations/multi-step-commit-sms-code",
            data={
                **self.auth_payload,
                "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login",
            },
        )
        resp = await r.json()
        assert resp["status"] == "ok"
        return await self.login_cookies()

    async def get_letter(self):
        """Request a magic link to user E-mail address."""
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/registration-validations/auth/send_magic_letter",
            data=self.auth_payload,
        )
        resp = await r.json()
        assert resp["status"] == "ok"

    async def login_letter(self) -> LoginResponse:
        """Check if already logged in via magic link."""
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/auth/letter/status/", data=self.auth_payload
        )
        resp = await r.json()
        assert resp["status"] == "ok"
        if not resp["magic_link_confirmed"]:
            return LoginResponse({})
        return await self.login_cookies()

    async def get_captcha(self) -> str:
        """Get link to captcha image."""
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/registration-validations/textcaptcha",
            data=self.auth_payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        resp = await r.json()
        assert resp["status"] == "ok"
        self.auth_payload["key"] = resp["key"]
        return resp["image_url"]

    async def login_captcha(self, captcha_answer: str) -> bool:
        """Login with answer to captcha from login_username."""
        _LOGGER.debug("Login in Yandex with captcha")
        assert self.auth_payload
        r = await self._post(
            "https://passport.yandex.ru/registration-validations/checkHuman",
            data={**self.auth_payload, "answer": captcha_answer},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        resp = await r.json()
        return resp["status"] == "ok"

    async def login_cookies(self, cookies: str = None) -> LoginResponse:
        """Support three formats for cookies auth."""
        host = "passport.yandex.ru"
        if cookies is None:
            cookies = "; ".join(
                [f"{c.key}={c.value}" for c in self._session.cookie_jar if c["domain"].endswith("yandex.ru")]
            )
        elif cookies[0] == "[":
            raw = json.loads(cookies)
            host = next(p["domain"] for p in raw if p["domain"].startswith(".yandex."))
            cookies = "; ".join([f"{p['name']}={p['value']}" for p in raw])

        r = await self._post(
            "https://mobileproxy.passport.yandex.net/1/bundle/oauth/token_by_sessionid",
            data={
                "client_id": "c0ebe342af7d48fbbbfcf2d2eedb8f9e",
                "client_secret": "ad0a908f0aa341a182a37ecd75bc319e",
            },
            headers={"Ya-Client-Host": host, "Ya-Client-Cookie": cookies},
        )
        resp = await r.json()
        x_token = resp["access_token"]
        return await self.validate_token(x_token)

    async def validate_token(self, x_token: str) -> LoginResponse:
        """Return user info using token."""
        r = await self._get(
            "https://mobileproxy.passport.yandex.net/1/bundle/account/short_info/?avatar_size=islands-300",
            headers={"Authorization": f"OAuth {x_token}"},
        )
        resp = await r.json()
        resp["x_token"] = x_token
        return LoginResponse(resp)

    async def login_token(self, x_token: str) -> bool:
        """Login to Yandex with x-token."""
        _LOGGER.debug("Login in Yandex with token")
        payload = {"type": "x-token", "retpath": "https://www.yandex.ru"}
        headers = {"Ya-Consumer-Authorization": f"OAuth {x_token}"}
        r = await self._post(
            "https://mobileproxy.passport.yandex.net/1/bundle/auth/x_token/",
            data=payload,
            headers=headers,
        )
        resp = await r.json()
        if resp["status"] != "ok":
            _LOGGER.error(f"Login with token error: {resp}")
            return False
        host = resp["passport_host"]
        payload = {"track_id": resp["track_id"]}
        r = await self._get(f"{host}/auth/session/", params=payload, allow_redirects=False)
        assert r.status == 302, await r.read()
        return True

    async def refresh_cookies(self) -> bool:
        """Checks if cookies ok and updates them if necessary."""
        r = await self._get("https://yandex.ru/quasar?storage=1")
        resp = await r.json()
        if resp["storage"]["user"]["uid"]:
            return True
        ok = await self.login_token(self.x_token)
        if ok:
            await self._handle_update()
        return ok

    async def get_music_token(self, x_token: str):
        """Get music token using x-token."""
        _LOGGER.debug("Get music token")
        payload = {
            "client_secret": "53bc75238f0c4d08a118e51fe9203300",
            "client_id": "23cabbbdc6cd418abb4b39c32c41195d",
            "grant_type": "x-token",
            "access_token": x_token,
        }
        r = await self._post("https://oauth.mobile.yandex.net/1/token", data=payload)
        resp = await r.json()
        assert "access_token" in resp, resp
        return resp["access_token"]

    async def get(self, url: str, **kwargs):
        if url.startswith(("https://quasar.yandex.net/glagol/", "https://api.music.yandex.net/")):
            return await self.request_glagol(url, **kwargs)
        return await self.request("get", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("post", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request("put", url, **kwargs)

    async def ws_connect(self, *args, **kwargs):
        if "ssl" not in kwargs:
            kwargs.setdefault("proxy", self.proxy)
            kwargs.setdefault("ssl", self.ssl)
        return await self._session.ws_connect(*args, **kwargs)

    async def request(self, method: str, url: str, retry: int = 2, **kwargs):
        """Public request function."""
        while (delay := self.last_ts + 0.2 - time.time()) > 0:
            await asyncio.sleep(delay)
        self.last_ts = time.time()

        if method != "get" and not url.startswith("https://rpc.alice.yandex.ru"):
            if self.csrf_token is None:
                _LOGGER.debug(f"Обновление CSRF-токена, proxy: {self.proxy}")
                r = await self._get("https://yandex.ru/quasar", proxy=self.proxy, ssl=self.ssl)
                raw = await r.text()
                m = re.search('"csrfToken2":"(.+?)"', raw)
                assert m, raw
                self.csrf_token = m[1]
            kwargs["headers"] = {"x-csrf-token": self.csrf_token}

        r = await self._request(method, url, **kwargs)
        if r.status == 200:
            return r
        elif r.status == 400:
            retry = 0
        elif r.status == 401:
            await self.refresh_cookies()
        elif r.status == 403:
            self.csrf_token = None
        elif not url.endswith("/get_alarms"):
            _LOGGER.warning(f"{url} return {r.status} status")

        if retry:
            _LOGGER.debug(f"Retry {method} {url}")
            return await self.request(method, url, retry - 1, **kwargs)
        raise Exception(f"{url} return {r.status} status")

    async def request_glagol(self, url: str, retry: int = 2, **kwargs):
        if not self.music_token:
            assert self.x_token, "x-token required"
            self.music_token = await self.get_music_token(self.x_token)
            await self._handle_update()
        headers = kwargs.setdefault("headers", {})
        headers["Authorization"] = f"OAuth {self.music_token}"
        r = await self._get(url, **kwargs)
        if r.status == 200:
            return r
        elif r.status == 403:
            self.music_token = None
        if retry:
            _LOGGER.debug(f"Retry {url}")
            return await self.request_glagol(url, retry - 1)
        raise Exception(f"{url} return {r.status} status")

    @property
    def cookie(self):
        raw = pickle.dumps(getattr(self._session.cookie_jar, "_cookies"), pickle.HIGHEST_PROTOCOL)
        return base64.b64encode(raw).decode()

    async def _handle_update(self):
        for coro in self._update_listeners:
            await coro(x_token=self.x_token, music_token=self.music_token, cookie=self.cookie)