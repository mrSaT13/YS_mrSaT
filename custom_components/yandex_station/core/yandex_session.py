"""
Yandex Session Manager with robust SSL and Auth handling.
"""
import asyncio
import base64
import json
import logging
import pickle
import re
import time
import ssl
import aiohttp
from http.cookies import Morsel
from aiohttp import ClientSession, ClientConnectorError
from urllib.parse import urlparse

from aiohttp import ClientSession

# Пытаемся импортировать библиотеку, но не ломаем всё, если её нет
try:
    from ya_passport_auth import PassportClient, ClientConfig, Credentials
    from ya_passport_auth.exceptions import QRTimeoutError, QRPendingError, YaPassportError
    YA_PASSPORT_AVAILABLE = True
except ImportError:
    YA_PASSPORT_AVAILABLE = False
    PassportClient = None
    ClientConfig = None
    Credentials = None
    QRTimeoutError = Exception
    QRPendingError = Exception

_LOGGER = logging.getLogger(__name__)

# Дефолтный User-Agent
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


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
    ssl_context: ssl.SSLContext = None
    _ssl_context_created: bool = False

    def __init__(self):
        # SSL контекст создаётся лениво при первом использовании
        # Это избегает блокировки event loop при инициализации
        pass
    
    def _get_ssl_context(self) -> ssl.SSLContext:
        """Ленивая инициализация SSL контекста - избегает блокировки event loop."""
        if self._ssl_context_created:
            return self.ssl_context
        
        # Создаем контекст SSL без проверки - решает проблему Connection closed
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self._ssl_context_created = True
        _LOGGER.debug("SSL context created (lazy init)")
        return self.ssl_context

    def _request(self, method: str, url: str, **kwargs):
        """Internal request function with proxy and ssl support. Добавляет User-Agent Яндекс.Браузера."""
        if self.domain:
            url = url.replace("yandex.ru", self.domain)

        # Если ssl не передан явно, используем наш контекст (ленивая инициализация)
        if "ssl" not in kwargs:
            kwargs["ssl"] = self._get_ssl_context()

        kwargs["proxy"] = self.proxy
        kwargs.setdefault("timeout", 15.0)

        # Добавляем User-Agent Яндекс.Браузера, если не задан
        headers = kwargs.setdefault("headers", {})
        headers.setdefault("User-Agent", DEFAULT_UA)

        return getattr(self._session, method)(url, **kwargs)

    async def _get_json(self, url: str, **kwargs):
        async with self._request("get", url, **kwargs) as r:
            return await r.json()

    async def _post_json(self, url: str, **kwargs):
        async with self._request("post", url, **kwargs) as r:
            return await r.json()

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
    
    _passport_client = None
    _qr_session = None
    _qr_start_time: float = 0

    def __init__(
        self,
        session: ClientSession,
        x_token: str = None,
        music_token: str = None,
        cookie: str = None,
    ):
        super().__init__()
        self._session = session
        if hasattr(session.cookie_jar, "_quote_cookie"):
            setattr(session.cookie_jar, "_quote_cookie", False)

        self.x_token = x_token
        self.music_token = music_token

        # cooldowns for endpoints that returned 403: {key: timestamp_until}
        self._forbidden_cooldowns: dict[str, float] = {}
        
        if cookie:
            self._load_cookies_from_base64(cookie)

        self._update_listeners = []

    def _load_cookies_from_base64(self, cookie: str):
        try:
            raw = base64.b64decode(cookie)
            loaded_cookies = pickle.loads(raw)
            self._session.cookie_jar._cookies.update(loaded_cookies)
        except Exception as e:
            _LOGGER.warning(f"Failed to load cookies: {e}")

    def add_update_listener(self, coro):
        self._update_listeners.append(coro)

    async def _get_csrf_token(self):
        """Get CSRF token."""
        headers = {"User-Agent": DEFAULT_UA}
        async with self._get("https://passport.yandex.ru/am?app_platform=android", headers=headers) as r:
            resp = await r.text()
            
            if r.status != 200 or "<title>400" in resp:
                raise Exception(f"Yandex passport returned {r.status}")
        
        m = re.search(r'"csrf_token" value="([^"]+)"', resp)
        if not m:
            m = re.search(r'window\.__CSRF__\s*=\s*"([^"]+)"', resp)
        
        if not m:
            raise Exception("CSRF token not found")
            
        return m[1]

    async def login_username(self, username: str) -> LoginResponse:
        """Create login session."""
        try:
            csrf_token = await self._get_csrf_token()
        except Exception as e:
            return LoginResponse({"errors": [str(e)]})

        self.auth_payload = {"csrf_token": csrf_token}

        headers = {
            "X-CSRF-Token": csrf_token,
            "Origin": "https://passport.yandex.ru",
            "Referer": "https://passport.yandex.ru/am?app_platform=android",
            "User-Agent": DEFAULT_UA
        }

        try:
            resp = await self._post_json(
                "https://passport.yandex.ru/pwl-yandex/api/passport/auth/multistep_start",
                headers=headers,
                data={"login": username},
            )
        except Exception as e:
            return LoginResponse({"errors": [f"Network error: {str(e)}"]})

        if resp.get("status") != "ok":
            return LoginResponse(resp)
        if resp.get("can_register") is True:
            return LoginResponse({"errors": ["account.not_found"]})

        self.auth_payload["track_id"] = resp["track_id"]
        return LoginResponse(resp)

    async def login_password(self, password: str) -> LoginResponse:
        """Login using password."""
        if not self.auth_payload:
            return LoginResponse({"errors": ["auth.no_session"]})

        headers = {
            "X-CSRF-Token": self.auth_payload["csrf_token"],
            "Origin": "https://passport.yandex.ru",
            "Referer": "https://passport.yandex.ru/am?app_platform=android",
            "User-Agent": DEFAULT_UA
        }

        try:
            resp = await self._post_json(
                "https://passport.yandex.ru/pwl-yandex/api/passport/auth/password/submit",
                headers=headers,
                data={
                    "track_id": self.auth_payload["track_id"],
                    "password": password,
                    "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login",
                },
            )
        except Exception as e:
            return LoginResponse({"errors": [f"Network error: {str(e)}"]})

        if resp.get("status") != "ok":
            return LoginResponse(resp)

        # После успешного логина по паролю — получаем x_token через cookies-flow
        login_cookies_resp = None
        if "redirect_url" in resp:
            if "/am/finish" in resp["redirect_url"]:
                login_cookies_resp = await self.login_cookies()
            else:
                async with self._get(resp["redirect_url"]) as r:
                    await r.text()
                login_cookies_resp = await self.login_cookies()
        else:
            login_cookies_resp = await self.login_cookies()

        # После получения x_token обязательно обновляем cookies через login_token
        login_token_ok = False
        if self.x_token:
            try:
                login_token_ok = await self.login_token(self.x_token)
                _LOGGER.info(f"login_token после логин/пароль: {'успешно' if login_token_ok else 'не удалось'}")
            except Exception as e:
                _LOGGER.warning(f"Ошибка login_token после логин/пароль: {e}")

        return login_cookies_resp

    async def get_qr(self) -> str:
        """Get link to QR-code auth."""
        if not YA_PASSPORT_AVAILABLE:
            raise Exception("ya-passport-auth library is required for QR auth")
        
        try:
            config = ClientConfig(user_agent=DEFAULT_UA)
            self._passport_client = PassportClient(session=self._session, config=config)
            
            self._qr_session = await self._passport_client.start_qr_login()
            self._qr_start_time = time.time()
            
            return self._qr_session.qr_url
            
        except Exception as e:
            _LOGGER.error(f"QR init failed: {e}", exc_info=True)
            raise Exception(f"QR initialization failed: {str(e)}")

    async def login_qr(self) -> LoginResponse:
        """Poll QR confirmation."""
        if not self._passport_client or not self._qr_session:
            return LoginResponse({"errors": ["qr.not_initialized"]})
        
        try:
            credentials = await self._passport_client.poll_qr_until_confirmed(
                self._qr_session,
                poll_interval=0.5,
                total_timeout=60.0,
            )
            
            self.x_token = credentials.x_token.get_secret() if hasattr(credentials.x_token, 'get_secret') else str(credentials.x_token)
            self.music_token = credentials.music_token.get_secret() if hasattr(credentials.music_token, 'get_secret') and credentials.music_token else None
            
            # Если music_token не был получен из credentials — получим его явно
            if not self.music_token and self.x_token:
                _LOGGER.debug("Music token not in credentials, fetching separately...")
                try:
                    self.music_token = await self.get_music_token(self.x_token)
                    _LOGGER.info(f"✅ Music token obtained: {bool(self.music_token)}")
                except Exception as e:
                    _LOGGER.warning(f"Failed to get music token: {e}")
            
            # После получения x_token обязательно обновляем cookies через login_token
            login_token_ok = False
            if self.x_token:
                try:
                    login_token_ok = await self.login_token(self.x_token)
                    _LOGGER.info(f"login_token после QR: {'успешно' if login_token_ok else 'не удалось'}")
                except Exception as e:
                    _LOGGER.warning(f"Ошибка login_token после QR: {e}")

            return await self.validate_token(self.x_token)
            
        except QRTimeoutError:
            return LoginResponse({"errors": ["qr.timeout"]})
        except Exception as e:
            _LOGGER.error(f"QR polling failed: {e}", exc_info=True)
            return LoginResponse({"errors": [f"qr.error: {str(e)}"]})

    async def get_sms(self):
        """Request SMS."""
        if not self.auth_payload:
            raise Exception("No auth payload")
            
        headers = {
            "X-CSRF-Token": self.auth_payload["csrf_token"],
            "User-Agent": DEFAULT_UA
        }
        
        resp = await self._post_json(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code-submit",
            headers=headers,
            data={**self.auth_payload, "mode": "tracked"},
        )
        if resp["status"] != "ok":
            raise Exception(resp.get("errors", ["Unknown error"]))

    async def login_sms(self, code: str) -> LoginResponse:
        """Login with SMS code."""
        if not self.auth_payload:
            return LoginResponse({"errors": ["auth.no_session"]})

        headers = {
            "X-CSRF-Token": self.auth_payload["csrf_token"],
            "User-Agent": DEFAULT_UA
        }

        resp = await self._post_json(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code",
            headers=headers,
            data={**self.auth_payload, "mode": "tracked", "code": code},
        )
        if resp["status"] != "ok":
            return LoginResponse(resp)

        resp = await self._post_json(
            "https://passport.yandex.ru/registration-validations/multi-step-commit-sms-code",
            headers=headers,
            data={**self.auth_payload, "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login"},
        )
        if resp["status"] != "ok":
            return LoginResponse(resp)
            
        return await self.login_cookies()

    async def login_cookies(self, cookies: str = None) -> LoginResponse:
        """Exchange cookies for x-token. Если cookies в формате JSON — сразу кладём их в cookie_jar."""
        host = "passport.yandex.ru"
        # Если cookies — JSON-экспорт (список объектов), кладём их в cookie_jar
        if cookies and cookies.strip().startswith("["):
            try:
                raw = json.loads(cookies)
                for p in raw:
                    # Пропускаем не yandex-домены
                    if not p["domain"].startswith(".yandex."):
                        continue
                    morsel = Morsel()
                    morsel.set(p["name"], p["value"], p["value"])
                    morsel["domain"] = p["domain"].lstrip(".")
                    morsel["path"] = p.get("path", "/")
                    if p.get("secure"):
                        morsel["secure"] = True
                    self._session.cookie_jar.update_cookies(
                        {p["name"]: morsel},
                        response_url=aiohttp.client_reqrep.URL(f"https://{p['domain'].lstrip('.')}"),
                    )
                # После этого cookies будут доступны для дальнейших запросов
                cookies = "; ".join([f"{p['name']}={p['value']}" for p in raw])
            except Exception as e:
                _LOGGER.warning(f"Не удалось обработать JSON cookies: {e}")

        if cookies is None:
            cookies = "; ".join(
                [f"{c.key}={c.value}" for c in self._session.cookie_jar if "yandex.ru" in c.domain]
            )

        if not cookies:
            return LoginResponse({"errors": ["no_cookies_found"]})

        # Client ID и Secret от Яндекс.Музыки
        client_id = "23cabbbdc6cd418abb4b39c32c41195d"
        client_secret = "53bc75238f0c4d08a118e51fe9203300"

        headers = {
            "Ya-Client-Host": host,
            "Ya-Client-Cookie": cookies,
            "User-Agent": DEFAULT_UA
        }

        try:
            resp = await self._post_json(
                "https://mobileproxy.passport.yandex.net/1/bundle/oauth/token_by_sessionid",
                headers=headers,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

            if "access_token" not in resp:
                _LOGGER.error(f"Token exchange failed: {resp}")
                return LoginResponse(resp)

            return await self.validate_token(resp["access_token"])

        except Exception as e:
            _LOGGER.error(f"Cookie exchange error: {e}", exc_info=True)
            return LoginResponse({"errors": [f"exchange_error: {str(e)}"]})

    async def validate_token(self, x_token: str) -> LoginResponse:
        """Validate x-token."""
        headers = {
            "Authorization": f"OAuth {x_token}",
            "User-Agent": DEFAULT_UA
        }
        
        try:
            async with self._get(
                "https://mobileproxy.passport.yandex.net/1/bundle/account/short_info/?avatar_size=islands-300",
                headers=headers,
            ) as r:
                if r.status != 200:
                    text = await r.text()
                    _LOGGER.error(f"Validation failed HTTP {r.status}: {text}")
                    return LoginResponse({"errors": [f"http_{r.status}"]})
                
                resp = await r.json()
                resp["x_token"] = x_token
                _LOGGER.info(f"Token validated for user: {resp.get('login', 'unknown')}")
                return LoginResponse(resp)
        except Exception as e:
            _LOGGER.error(f"Validation network error: {e}")
            return LoginResponse({"errors": [f"network_error: {str(e)}"]})

    async def login_token(self, x_token: str) -> bool:
        """Login with x-token to get cookies, затем оживить cookies через профиль."""
        headers = {
            "Ya-Consumer-Authorization": f"OAuth {x_token}",
            "User-Agent": DEFAULT_UA
        }
        try:
            async with self._post(
                "https://mobileproxy.passport.yandex.net/1/bundle/auth/x_token/",
                headers=headers,
                data={"type": "x-token", "retpath": "https://www.yandex.ru"},
            ) as r:
                resp = await r.json()

            if resp["status"] != "ok":
                return False

            host = resp["passport_host"]
            async with self._get(
                f"{host}/auth/session/", 
                params={"track_id": resp["track_id"]}, 
                allow_redirects=False
            ) as r:
                pass

            # Оживляем cookies через профиль
            try:
                async with self._get("https://passport.yandex.ru/profile") as r:
                    await r.text()
                _LOGGER.info("Профиль Яндекса запрошен для оживления cookies после login_token")
            except Exception as e:
                _LOGGER.warning(f"Ошибка при запросе профиля Яндекса: {e}")

            # Логируем все cookies после login_token
            for c in self._session.cookie_jar:
                # В aiohttp cookie_jar объекты не имеют атрибута domain напрямую, 
                # нужно смотреть в аргументы или просто выводить ключ/значение
                _LOGGER.warning(f"COOKIE после login_token: {c.key}={c.value}")

            return True
        except Exception as e:
            _LOGGER.error(f"Login token error: {e}")
            return False

    async def refresh_cookies(self) -> bool:
        """Refresh cookies if expired."""
        if self.x_token:
            return await self.login_token(self.x_token)
        return False

    async def get_music_token(self, x_token: str):
        """Get music token."""
        payload = {
            "client_secret": "53bc75238f0c4d08a118e51fe9203300",
            "client_id": "23cabbbdc6cd418abb4b39c32c41195d",
            "grant_type": "x-token",
            "access_token": x_token,
        }
        try:
            resp = await self._post_json("https://oauth.mobile.yandex.net/1/token", data=payload)
            return resp.get("access_token")
        except Exception as e:
            _LOGGER.error(f"Get music token error: {e}")
            return None

    async def request(self, method: str, url: str, retry: int = 2, **kwargs):
        """Public request function with retry logic and minimal headers for Quasar."""
        # If this URL/host is in cooldown after recent 403, avoid hitting it.
        key = urlparse(url).netloc or url
        until = self._forbidden_cooldowns.get(key)
        if until and time.time() < until:
            _LOGGER.warning(f"Cooldown active for {key} until {until}; skipping request to {url}")
            raise Exception(f"{url} is in 403 cooldown")
        # Rate limiting
        while (delay := self.last_ts + 0.2 - time.time()) > 0:
            await asyncio.sleep(delay)
        self.last_ts = time.time()

        # Добавляем дефолтные заголовки
        headers = kwargs.setdefault("headers", {})
        headers.setdefault("User-Agent", DEFAULT_UA)
        
        # Если это запрос к Quasar/IoT, добавляем токен и МИНИМАЛЬНЫЕ заголовки
        if "iot.quasar" in url or "quasar.yandex" in url:
            # Если вызывающий код уже передал Authorization (например, с music_token),
            # НЕ перезаписываем его. В противном случае используем x_token.
            if "Authorization" not in headers:
                if self.x_token:
                    headers["Authorization"] = f"OAuth {self.x_token}"
                else:
                    _LOGGER.error(f"❌ x_token is empty for Quasar request to {url}!")
                    raise Exception("x_token required for Quasar request")

            # Минимальные заголовки - избегаем фингерпринтинга
            headers.setdefault("Accept", "application/json")
            headers.setdefault("Connection", "keep-alive")
            # Debug which Authorization (masked) is being used for Quasar requests
            auth_preview = None
            if "Authorization" in headers:
                try:
                    a = headers["Authorization"]
                    auth_preview = f"{a[:12]}... (len={len(a)})"
                except Exception:
                    auth_preview = "<unavailable>"
            _LOGGER.debug(f"Quasar request to {url} with headers: {list(headers.keys())} Authorization={auth_preview}")
        elif "alice.yandex" in url:
            if self.x_token:
                headers["Authorization"] = f"OAuth {self.x_token}"
                _LOGGER.debug(f"Added Authorization header for Alice {url}")

        try:
            _LOGGER.debug(f"→ {method.upper()} {url}")
            async with self._request(method, url, **kwargs) as r:
                _LOGGER.info(f"← {method.upper()} {url} → {r.status}")
                
                if r.status == 200:
                    return r
                elif r.status == 401:
                    _LOGGER.warning(f"401 Unauthorized for {url}")
                    if self.x_token:
                        _LOGGER.debug("Got 401, refreshing cookies...")
                        await self.refresh_cookies()
                        if retry > 0:
                            return await self.request(method, url, retry - 1, **kwargs)
                elif r.status == 403:
                    _LOGGER.warning(f"403 Forbidden for {url}")
                    # set cooldown for the host to avoid rapid repeated 403s
                    host = urlparse(url).netloc
                    cooldown = 300  # 5 minutes
                    self._forbidden_cooldowns[host] = time.time() + cooldown
                    _LOGGER.warning(f"Set 403 cooldown for {host} ({cooldown}s)")
                    # Do not retry immediately; raise to caller so caller can decide
                    raise Exception(f"{url} returned 403")
                
                if retry > 0:
                    _LOGGER.debug(f"Retrying {method} {url} (status {r.status})")
                    await asyncio.sleep(1)
                    return await self.request(method, url, retry - 1, **kwargs)

                raise Exception(f"{url} returned {r.status}")
        except asyncio.TimeoutError as e:
            _LOGGER.error(f"⏱️ Timeout for {method.upper()} {url}: {e}")
            if retry > 0:
                await asyncio.sleep(1)
                return await self.request(method, url, retry - 1, **kwargs)
            raise
        except Exception as e:
            # If session is closed, re-raise with clear message
            if isinstance(e, RuntimeError) and "closed" in str(e).lower():
                _LOGGER.error(f"Session closed when requesting {url}: {e}")
                raise

            _LOGGER.error(f"❌ Request error for {method.upper()} {url}: {type(e).__name__}: {e}")
            # Retry on common connection errors
            if retry > 0 and isinstance(e, (ClientConnectorError, ConnectionResetError)):
                _LOGGER.debug(f"Connection error ({type(e).__name__}), retrying {url}")
                # exponential-ish backoff
                await asyncio.sleep(1 + (3 - retry) * 2)
                return await self.request(method, url, retry - 1, **kwargs)

            raise

    async def get(self, url: str, **kwargs):
        return await self.request("get", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("post", url, **kwargs)

    @property
    def cookie(self):
        """Serialize cookies to base64."""
        raw = pickle.dumps(self._session.cookie_jar._cookies, pickle.HIGHEST_PROTOCOL)
        return base64.b64encode(raw).decode()

    def get_cookies_json(self) -> str:
        """Export cookies as JSON list."""
        cookie_list = []
        for cookie in self._session.cookie_jar:
            if "yandex.ru" in cookie.domain or "yandex.net" in cookie.domain:
                cookie_list.append({
                    "name": cookie.key,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path or "/",
                    "secure": bool(cookie.secure),
                    "httpOnly": bool(cookie.get("httponly", False)),
                    "expirationDate": int(cookie.expires) if cookie.expires else None
                })
        return json.dumps(cookie_list, indent=2)

    async def _handle_update(self):
        for coro in self._update_listeners:
            try:
                await coro(x_token=self.x_token, music_token=self.music_token, cookie=self.cookie)
            except Exception as e:
                _LOGGER.error(f"Listener error: {e}")