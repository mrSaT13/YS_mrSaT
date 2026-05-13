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


# Passport OAuth client credentials (scope для quasar)
try:
    from ya_passport_auth.constants import (
        PASSPORT_CLIENT_ID,
        PASSPORT_CLIENT_SECRET,
    )
except ImportError:
    PASSPORT_CLIENT_ID = "c0ebe342af7d48fbbbfcf2d2eedb8f9e"
    PASSPORT_CLIENT_SECRET = "ad0a908f0aa341a182a37ecd75bc319e"

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


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
            return await _safe_response_json(r)

    async def _post_json(self, url: str, **kwargs):
        async with self._request("post", url, **kwargs) as r:
            return await _safe_response_json(r)

    def _get(self, url: str, **kwargs):
        return self._request("get", url, **kwargs)

    def _post(self, url: str, **kwargs):
        return self._request("post", url, **kwargs)

    # Convenience passthroughs to behave like an aiohttp ClientSession
    async def get(self, url: str, **kwargs):
        return await self._request("get", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self._request("post", url, **kwargs)

    async def put(self, url: str, **kwargs):
        return await self._request("put", url, **kwargs)

    async def delete(self, url: str, **kwargs):
        return await self._request("delete", url, **kwargs)

    async def patch(self, url: str, **kwargs):
        return await self._request("patch", url, **kwargs)

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

    async def login_username(self, username: str) -> LoginResponse:
        """First step of login: enter username."""
        # Очищаем сессию перед новым входом
        self._session.cookie_jar.clear()
        self.auth_payload = None
        self.csrf_token = None

        headers = {"User-Agent": DEFAULT_UA}
        try:
            async with self._get("https://passport.yandex.ru/am?app_platform=android", headers=headers) as r:
                text = await r.text()
                # Извлекаем CSRF
                m = re.search(r'name="csrf_token" value="([^"]+)"', text)
                csrf = m.group(1) if m else None
                if not csrf:
                    m = re.search(r'csrf_token["\':\s]+"?([0-9a-fA-F-]+)"?', text)
                    csrf = m.group(1) if m else None
                
                if not csrf:
                    _LOGGER.error("CSRF not found in passport init")
                    return LoginResponse({"errors": ["csrf_not_found"]})
                
                self.csrf_token = csrf
                self.auth_payload = {"csrf_token": csrf, "login": username}

            resp = await self._post_json(
                "https://passport.yandex.ru/pwl-yandex/api/passport/auth/multistep_start",
                data=self.auth_payload,
                headers={"User-Agent": DEFAULT_UA, "X-CSRF-Token": csrf}
            )
            
            if resp.get("status") == "ok":
                # Сохраняем tracks/state для следующих шагов
                self.auth_payload.update({
                    "track_id": resp.get("track_id"),
                })
            
            return LoginResponse(resp)
        except Exception as e:
            _LOGGER.exception("login_username error")
            return LoginResponse({"errors": [str(e)]})

    async def login_password(self, password: str) -> LoginResponse:
        """Second step: enter password."""
        if not self.auth_payload or not self.auth_payload.get("track_id"):
            return LoginResponse({"errors": ["session_expired"]})

        headers = {
            "User-Agent": DEFAULT_UA,
            "X-CSRF-Token": self.csrf_token,
        }
        
        data = {
            "csrf_token": self.csrf_token,
            "track_id": self.auth_payload["track_id"],
            "password": password,
            "retpath": "https://passport.yandex.ru/am/finish"
        }

        try:
            resp = await self._post_json(
                "https://passport.yandex.ru/pwl-yandex/api/passport/auth/password/submit",
                data=data,
                headers=headers
            )
            
            if resp.get("status") == "ok":
                # Если успех — пробуем забрать куки
                return await self.login_cookies()
            
            return LoginResponse(resp)
        except Exception as e:
            _LOGGER.exception("login_password error")
            return LoginResponse({"errors": [str(e)]})

    async def login_2fa(self, code: str) -> LoginResponse:
        """Step for 2FA/SMS/App code."""
        if not self.auth_payload or not self.auth_payload.get("track_id"):
            return LoginResponse({"errors": ["session_expired"]})

        headers = {
            "User-Agent": DEFAULT_UA,
            "X-CSRF-Token": self.csrf_token,
        }
        
        data = {
            "csrf_token": self.csrf_token,
            "track_id": self.auth_payload["track_id"],
            "code": code,
        }

        try:
            # Пытаемся отправить код (универсальный endpoint для 2FA)
            resp = await self._post_json(
                "https://passport.yandex.ru/pwl-yandex/api/passport/auth/challenge/submit",
                data=data,
                headers=headers
            )
            
            if resp.get("status") == "ok":
                return await self.login_cookies()
            
            return LoginResponse(resp)
        except Exception as e:
            _LOGGER.exception("login_2fa error")
            return LoginResponse({"errors": [str(e)]})

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
        """Exchange cookies for x-token. Использует Passport client_id для scope quasar."""
        host = "passport.yandex.ru"
        # Если cookies — JSON-экспорт (список объектов), кладём их в cookie_jar
        if cookies and cookies.strip().startswith("["):
            try:
                raw = json.loads(cookies)
                for p in raw:
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
                cookies = "; ".join([f"{p['name']}={p['value']}" for p in raw])
            except Exception as e:
                _LOGGER.warning(f"Не удалось обработать JSON cookies: {e}")

        if cookies is None:
            cookies = "; ".join(
                [f"{c.key}={c.value}" for c in self._session.cookie_jar if "yandex.ru" in c.domain]
            )

        if not cookies:
            return LoginResponse({"errors": ["no_cookies_found"]})

        # Passport client_id/secret (scope для quasar)
        client_id = PASSPORT_CLIENT_ID
        client_secret = PASSPORT_CLIENT_SECRET

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
    async def _ensure_csrf_token(self) -> None:
        """Ленивая загрузка x-csrf-token для не-GET Quasar/Alice запросов."""
        if self.csrf_token:
            return
        try:
            async with self._get("https://yandex.ru/quasar", timeout=10) as page:
                text = await page.text()
                m = re.search(r'"csrfToken2":"(.+?)"', text)
                if m:
                    self.csrf_token = m.group(1)
                    _LOGGER.debug("Quasar CSRF token fetched")
                else:
                    _LOGGER.warning("Quasar CSRF token not found on /quasar")
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch Quasar CSRF: {e}")

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
                
                resp = await _safe_response_json(r)
                resp["x_token"] = x_token
                _LOGGER.info(f"Token validated for user: {resp.get('login', 'unknown')}")
                return LoginResponse(resp)
        except Exception as e:
            _LOGGER.error(f"Validation network error: {e}")
            return LoginResponse({"errors": [f"network_error: {str(e)}"]})

    async def login_token(self, x_token: str) -> bool:
        """Login with x-token to get Session_id/sessar cookies через чистую сессию.

        КРИТИЧНО: запрос к /auth/session/ делается через ЧИСТЫЙ cookie_jar.
        Если делать его через основной jar с накопленными tracking-cookies,
        антифрод Яндекса видит "анонимную" сессию и вместо Session_id/sessionid2/L/sessar
        выдаёт только spravka+технические куки → Quasar/Glagol возвращают 403.
        """
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
                resp = await _safe_response_json(r)

            if resp["status"] != "ok":
                _LOGGER.warning(f"login_token: статус не ok: {resp}")
                return False

            host = resp["passport_host"]
            track_id = resp["track_id"]
            ssl_ctx = self._get_ssl_context()

            # Используем чистую сессию без накопленных tracking cookies
            clean_jar = aiohttp.CookieJar()
            async with aiohttp.ClientSession(cookie_jar=clean_jar) as clean_session:
                async with clean_session.get(
                    f"{host}/auth/session/",
                    params={"track_id": track_id},
                    headers={"User-Agent": DEFAULT_UA},
                    ssl=ssl_ctx,
                    proxy=self.proxy,
                    allow_redirects=True,
                ) as r:
                    await r.text()

            # Копируем полученные cookies из чистой сессии в основную
            self._session.cookie_jar._cookies.update(clean_jar._cookies)

            # Диагностика: какие cookies реально получены
            cookie_keys = [c.key for c in self._session.cookie_jar]
            has_session_id = "Session_id" in cookie_keys
            _LOGGER.info(f"Cookies после login_token ({len(cookie_keys)} шт.): {cookie_keys}")
            if has_session_id:
                _LOGGER.info("✅ Session_id получен — сессионные cookies в норме")
            else:
                _LOGGER.warning("❌ Session_id НЕ получен — антифрод мог сработать!")

            # Сохраняем обновлённые cookies в entry.data
            await self._handle_update()

            return True
        except Exception as e:
            _LOGGER.error(f"Login token error: {e}", exc_info=True)
            return False

    async def refresh_cookies(self) -> bool:
        """Refresh cookies if expired. Пробует storage=1, если невалидно — login_token."""
        # Оптимистичный probe: если сессионные cookies в jar валидны,
        # storage отдаст uid — перелогин не нужен (см. AlexxIT/YandexStation#764).
        try:
            async with self._get("https://yandex.ru/quasar?storage=1", timeout=10) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    if data.get("storage", {}).get("user", {}).get("uid"):
                        _LOGGER.debug("refresh_cookies: storage uid OK")
                        return True
        except Exception as e:
            _LOGGER.debug(f"storage=1 probe failed, falling back: {e}")
        if self.x_token:
            return await self.login_token(self.x_token)
        return False

    async def diagnostics(self) -> dict:
        """Return diagnostic info useful for debugging auth issues."""
        try:
            cookie_keys = [c.key for c in self._session.cookie_jar]
        except Exception:
            cookie_keys = []
        has_session_id = any(k.lower() in ("session_id", "sessionid", "sessar") for k in cookie_keys)
        return {
            "has_x_token": bool(self.x_token),
            "has_music_token": bool(self.music_token),
            "cookie_keys": cookie_keys,
            "has_session_id": has_session_id,
            "forbidden_cooldowns": self._forbidden_cooldowns,
        }

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
        """Public request function with retry logic, CSRF, Passport client_id, подробный лог."""
        key = urlparse(url).netloc or url
        until = self._forbidden_cooldowns.get(key)
        if until and time.time() < until:
            _LOGGER.warning(f"Cooldown active for {key} until {until}; skipping request to {url}")
            raise Exception(f"{url} is in 403 cooldown")
        # Rate limiting
        while (delay := self.last_ts + 0.2 - time.time()) > 0:
            await asyncio.sleep(delay)
        self.last_ts = time.time()

        headers = kwargs.setdefault("headers", {})
        headers.setdefault("User-Agent", DEFAULT_UA)

        # CSRF для не-GET Quasar/Alice
        is_quasar = "iot.quasar" in url or "quasar.yandex" in url
        is_alice = "alice.yandex" in url
        if is_quasar or is_alice:
            if "Authorization" not in headers:
                if self.x_token:
                    headers["Authorization"] = f"OAuth {self.x_token}"
                else:
                    _LOGGER.error(f"❌ x_token is empty for Quasar request to {url}!")
                    raise Exception("x_token required for Quasar request")
            # Минимальные заголовки
            headers.setdefault("Accept", "application/json")
            headers.setdefault("Connection", "keep-alive")
            # CSRF только для не-GET
            if method.lower() != "get":
                await self._ensure_csrf_token()
                if self.csrf_token:
                    headers["x-csrf-token"] = self.csrf_token
            # Debug which Authorization (masked) is being used for Quasar requests
            auth_preview = None
            if "Authorization" in headers:
                try:
                    a = headers["Authorization"]
                    auth_preview = f"{a[:12]}... (len={len(a)})"
                except Exception:
                    auth_preview = "<unavailable>"
            _LOGGER.debug(f"Quasar request to {url} with headers: {list(headers.keys())} Authorization={auth_preview}")
        try:
            _LOGGER.debug(f"→ {method.upper()} {url}")
            r = await self._request(method, url, **kwargs)
            _LOGGER.info(f"← {method.upper()} {url} → {r.status}")
            if r.status == 200:
                return r
            # 401 Unauthorized
            if r.status == 401:
                r.close()
                _LOGGER.warning(f"401 Unauthorized for {url}")
                if self.x_token:
                    _LOGGER.debug("Got 401, refreshing cookies...")
                    await self.refresh_cookies()
                    if retry > 0:
                        return await self.request(method, url, retry - 1, **kwargs)
            # 403 Forbidden
            elif r.status == 403:
                # Для не-GET Quasar/Alice: сбрасываем CSRF и ретраим 1 раз до cooldown
                if (is_quasar or is_alice) and method.lower() != "get" and self.csrf_token:
                    _LOGGER.debug("Got 403 on non-GET Quasar, dropping CSRF and retrying")
                    self.csrf_token = None
                    r.close()
                    if retry > 0:
                        return await self.request(method, url, retry - 1, **kwargs)
                r.close()
                _LOGGER.warning(f"403 Forbidden for {url}")
                host = urlparse(url).netloc
                cooldown = 300  # 5 минут
                self._forbidden_cooldowns[host] = time.time() + cooldown
                _LOGGER.warning(f"Set 403 cooldown for {host} ({cooldown}s)")
                raise Exception(f"{url} returned 403")
            else:
                # Подробный лог ошибки
                text = await r.text()
                _LOGGER.error(f"HTTP {r.status} for {url}: {text[:300]}")
                r.close()
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
            if isinstance(e, RuntimeError) and "closed" in str(e).lower():
                _LOGGER.error(f"Session closed when requesting {url}: {e}")
                raise
            _LOGGER.error(f"❌ Request error for {method.upper()} {url}: {type(e).__name__}: {e}")
            if retry > 0 and isinstance(e, (ClientConnectorError, ConnectionResetError)):
                _LOGGER.debug(f"Connection error ({type(e).__name__}), retrying {url}")
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