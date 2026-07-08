"""Music Plus bypass -获得 рабочие ссылки на треки без Плюса.

Основан на подходе YandexMusicBetaMod:
- Использует Desktop HMAC ключ вместо Android
- Повторяет запросы если trackId не совпадает (реклама)
- Проверяет.trackId в ответе
- Дешифрует зашифрованные треки (AES-CTR-128)
"""

import asyncio
import base64
import hashlib
import hmac
import logging
from datetime import datetime

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)

# Desktop client HMAC key (from YandexMusicBetaMod)
DESKTOP_SECRET_KEY = "kzqU4XhfCaY6B6JTHODeq5"
# Original Android key (from original integration)
ANDROID_SECRET_KEY = "p93jhgh689SBReK6ghtw62"

# Desktop client headers
DESKTOP_HEADERS = {
    "X-Yandex-Music-Client": "YandexMusicDesktopAppWindows/5.28.1",
    "X-Yandex-Music-Frontend": "new",
    "X-Yandex-Music-Without-Invocation-Info": "1",
}

# Headers to remove (from YandexMusicBetaMod patcher)
BANNED_HEADERS = ["x-yandex-music-device", "x-request-id"]

# Quality levels
QUALITY_LOSSLESS = "lossless"
QUALITY_NQ = "nq"  # normal quality
QUALITY_LQ = "lq"  # low quality

# Codecs
DESKTOP_CODECS = "flac,aac,he-aac,mp3,flac-mp4,aac-mp4,he-aac-mp4"
ANDROID_CODECS = "flac,aac,he-aac,mp3"

# Max retries for ad bypass
MAX_RETRIES = 10
RETRY_DELAY = 0.15  # 150ms


def _sign_hmac(secret_key: str, *args) -> str:
    """Generate HMAC-SHA256 signature."""
    msg = "".join(str(i) for i in args).replace(",", "").encode()
    hmac_hash = hmac.new(secret_key.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(hmac_hash).decode()[:-1]


async def decrypt_yandex_audio(encrypted_data: bytes, secret_key_hex: str) -> bytes:
    """Decrypt Yandex Music encrypted audio stream.

    Uses AES-CTR-128 algorithm from YandexMusicBetaMod.
    The secret_key_hex is hex-encoded key from get-file-info response.

    Args:
        encrypted_data: encrypted audio bytes
        secret_key_hex: hex-encoded AES key from downloadInfo

    Returns:
        Decrypted audio bytes
    """
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        _LOGGER.error("cryptography package required for audio decryption: pip install cryptography")
        return encrypted_data

    # Convert hex key to bytes
    key_bytes = bytes.fromhex(secret_key_hex)

    # AES-CTR with zero IV (as in YandexMusicBetaMod)
    iv = b'\x00' * 16

    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.CTR(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()

    # Stream decryption in chunks
    chunk_size = 16384  # 16KB chunks
    decrypted_chunks = []
    for i in range(0, len(encrypted_data), chunk_size):
        chunk = encrypted_data[i:i + chunk_size]
        decrypted_chunks.append(decryptor.update(chunk))

    decrypted_chunks.append(decryptor.finalize())
    return b''.join(decrypted_chunks)


async def stream_decrypt_yandex_audio(
    encrypted_data: bytes,
    secret_key_hex: str,
    chunk_size: int = 16384,
):
    """Generator for streaming decryption of Yandex Music audio.

    Yields decrypted chunks for memory-efficient processing.
    """
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        _LOGGER.error("cryptography package required for audio decryption")
        yield encrypted_data
        return

    key_bytes = bytes.fromhex(secret_key_hex)
    iv = b'\x00' * 16

    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.CTR(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()

    for i in range(0, len(encrypted_data), chunk_size):
        chunk = encrypted_data[i:i + chunk_size]
        yield decryptor.update(chunk)

    yield decryptor.finalize()


async def get_file_info_desktop(
    session: YandexSession,
    track_id: int | str,
    quality: str = QUALITY_LOSSLESS,
    retries: int = MAX_RETRIES,
) -> dict | None:
    """Get track download info using Desktop client approach.

    This mimics the YandexMusicBetaMod approach:
    1. Uses Desktop HMAC key and headers
    2. Retries if trackId doesn't match (ad detection)
    3. Returns working download URL

    Returns:
        dict with keys: trackId, codec, bitrate_in_kbps, direct_url, file_size
        or None if failed
    """
    timestamp = int(datetime.now().timestamp())

    for attempt in range(retries):
        try:
            # Generate signature with Desktop key
            sign_data = f"{timestamp}{track_id}{quality}{DESKTOP_CODECS}encraw"
            signature = _sign_hmac(DESKTOP_SECRET_KEY, sign_data)

            params = {
                "ts": timestamp,
                "trackId": track_id,
                "quality": quality,
                "codecs": DESKTOP_CODECS,
                "transports": "encraw",
                "sign": signature,
            }

            r = await session.get(
                "https://api.music.yandex.net/get-file-info",
                headers=DESKTOP_HEADERS,
                params=params,
                timeout=10,
            )
            raw = await r.json()

            if "result" not in raw or "downloadInfo" not in raw["result"]:
                _LOGGER.debug(f"get-file-info: no result for track {track_id}")
                return None

            info = raw["result"]["downloadInfo"]

            # Check if trackId matches (ad detection)
            response_track_id = str(info.get("trackId", ""))
            if response_track_id != str(track_id):
                _LOGGER.debug(
                    f"TrackId mismatch: requested={track_id}, got={response_track_id} "
                    f"(attempt {attempt + 1}/{retries})"
                )
                # Wait and retry
                await asyncio.sleep(RETRY_DELAY)
                timestamp = int(datetime.now().timestamp())  # refresh timestamp
                continue

            # TrackId matches - return download info
            _LOGGER.debug(f"Got download info for track {track_id}: {info.get('codec')} {info.get('bitrate_in_kbps')}kbps")
            return info

        except Exception as e:
            _LOGGER.debug(f"get-file-info attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(RETRY_DELAY)
            timestamp = int(datetime.now().timestamp())

    _LOGGER.warning(f"Failed to get download info for track {track_id} after {retries} attempts")
    return None


async def get_file_info_android(
    session: YandexSession,
    track_id: int | str,
    quality: str = QUALITY_LOSSLESS,
) -> dict | None:
    """Get track download info using original Android approach.

    This is the existing approach from yandex_music.py.
    """
    timestamp = int(datetime.now().timestamp())
    params = {
        "ts": timestamp,
        "trackId": track_id,
        "quality": quality,
        "codecs": ANDROID_CODECS,
        "transports": "raw",
    }
    params["sign"] = _sign_hmac(ANDROID_SECRET_KEY, *params.values())

    try:
        r = await session.get(
            "https://api.music.yandex.net/get-file-info",
            headers={"X-Yandex-Music-Client": "YandexMusicAndroid/24023621"},
            params=params,
            timeout=5,
        )
        raw = await r.json()

        if "result" not in raw or "downloadInfo" not in raw["result"]:
            return None

        info = raw["result"]["downloadInfo"]

        # Check for ad (trackId mismatch)
        if str(info.get("trackId", "")) != str(track_id):
            _LOGGER.debug(f"Android: trackId mismatch for {track_id}, ad detected")
            return None

        return info

    except Exception as e:
        _LOGGER.debug(f"Android get-file-info failed: {e}")
        return None


async def check_track_premium(
    session: YandexSession,
    track_id: int | str,
) -> bool:
    """Check if a track requires Yandex Plus subscription."""
    try:
        r = await session.get(
            f"https://api.music.yandex.net/tracks/{track_id}",
            timeout=10,
        )
        raw = await r.json()

        if "result" not in raw:
            return False

        results = raw["result"]
        if isinstance(results, list) and results:
            track_data = results[0]
        elif isinstance(results, dict):
            track_data = results
        else:
            return False

        # Check various indicators of premium content
        if track_data.get("isPremium"):
            return True
        if track_data.get("hasRightholds"):
            return True

        download_info = track_data.get("downloadInfo", [])
        if not download_info:
            # No download info available - likely premium
            return True

        return False

    except Exception as e:
        _LOGGER.debug(f"check_track_premium failed for {track_id}: {e}")
        return False


async def get_track_preview_url(
    session: YandexSession,
    track_id: int | str,
) -> str | None:
    """Get preview URL for a track (30-second clip).

    Returns preview URL or None if not available.
    """
    try:
        r = await session.get(
            f"https://api.music.yandex.net/tracks/{track_id}/download-info",
            timeout=10,
        )
        raw = await r.json()

        if "result" not in raw:
            return None

        download_info = raw["result"]
        if not download_info:
            return None

        # Find mp3 entry with preview URL
        for info in download_info:
            codec = info.get("codec", "")
            bitrate = info.get("bitrateInKbps", 0)
            if codec == "mp3" and bitrate <= 192:
                # This is likely a preview
                url = info.get("downloadInfoUrl", "")
                if url:
                    return url

        # If no low-quality mp3, return first available
        if download_info:
            return download_info[0].get("downloadInfoUrl")

        return None

    except Exception as e:
        _LOGGER.debug(f"get_track_preview_url failed for {track_id}: {e}")
        return None


async def get_working_track_url(
    session: YandexSession,
    track_id: int | str,
    quality: str = QUALITY_LOSSLESS,
) -> dict | None:
    """Get a working download URL for a track.

    Tries Desktop approach first (with retries), then falls back to Android.
    Returns dict with keys: url, codec, encrypted, decrypt_key
    or None if all attempts fail.
    """
    # Try Desktop approach (with ad bypass retries)
    info = await get_file_info_desktop(session, track_id, quality)
    if info:
        result = _extract_download_info(info)
        if result:
            return result

    # Try Android approach
    info = await get_file_info_android(session, track_id, quality)
    if info:
        result = _extract_download_info(info)
        if result:
            return result

    # Try with lower quality
    if quality != QUALITY_LQ:
        info = await get_file_info_desktop(session, track_id, QUALITY_NQ)
        if info:
            result = _extract_download_info(info)
            if result:
                return result

    return None


def _extract_download_info(info: dict) -> dict | None:
    """Extract download info from get-file-info response.

    Returns dict with: url, codec, encrypted, decrypt_key
    """
    try:
        direct_url = info.get("directUrl") or info.get("direct_url")
        if not direct_url:
            return None

        codec = info.get("codec", "mp3")
        encrypted = info.get("encrypted", False)
        decrypt_key = info.get("key") or info.get("decryptKey")

        return {
            "url": direct_url,
            "codec": codec,
            "encrypted": encrypted,
            "decrypt_key": decrypt_key,
            "bitrate": info.get("bitrateInKbps", 0),
            "file_size": info.get("fileSize", 0),
        }
    except Exception as e:
        _LOGGER.debug(f"extract_download_info failed: {e}")
        return None


async def check_account_has_plus(session: YandexSession) -> bool:
    """Check if account has Yandex Plus subscription.

    Note: This checks real status, not spoofed.
    """
    try:
        r = await session.get(
            "https://api.music.yandex.net/account/about",
            headers=DESKTOP_HEADERS,
            timeout=10,
        )
        raw = await r.json()
        if "result" not in raw:
            return False
        return raw["result"].get("hasPlus", False)
    except Exception as e:
        _LOGGER.debug(f"check_account_has_plus failed: {e}")
        return False


async def get_track_download_info(
    session: YandexSession,
    track_id: int | str,
    quality: str = QUALITY_LOSSLESS,
) -> dict | None:
    """Get full download info for a track including decryption details.

    Returns dict with:
        - url: direct download URL
        - codec: audio codec (mp3, flac, aac)
        - encrypted: whether stream is encrypted
        - decrypt_key: hex key for AES decryption (if encrypted)
        - bitrate: bitrate in kbps
        - file_size: file size in bytes
    """
    info = await get_working_track_url(session, track_id, quality)
    if not info:
        return None

    # If encrypted, try to get decryption key
    if info.get("encrypted") and not info.get("decrypt_key"):
        # Some responses include key directly
        # For now, return as-is — decryption will be handled by caller
        pass

    return info


async def search_and_get_url(
    session: YandexSession,
    query: str,
    quality: str = QUALITY_LOSSLESS,
) -> dict | None:
    """Search for a track and get a working download URL.

    Returns:
        dict with keys: track_id, title, artist, duration_ms, url, codec, encrypted, decrypt_key
        or None if not found

    Special case: if track is premium-only, returns dict with premium_message
    """
    try:
        # Search for tracks
        r = await session.get(
            "https://api.music.yandex.net/search",
            params={"text": query, "type": "track", "page": 0, "nococrrect": "false"},
            timeout=10,
        )
        raw = await r.json()

        if "result" not in raw or "tracks" not in raw["result"]:
            _LOGGER.debug(f"Search: no results for '{query}'")
            return None

        tracks = raw["result"]["tracks"].get("results", [])
        if not tracks:
            _LOGGER.debug(f"Search: no tracks for '{query}'")
            return None

        # Get first track
        track = tracks[0]
        track_id = track["id"]
        title = track.get("title", "Unknown")
        artist = track.get("artists", [{}])[0].get("name", "Unknown")
        duration_ms = track.get("durationMs", 0)

        _LOGGER.debug(f"Found track: {title} by {artist} (id={track_id})")

        # Check if track is premium-only
        is_premium = await check_track_premium(session, track_id)
        if is_premium:
            # Try to get preview URL for premium tracks
            preview_url = await get_track_preview_url(session, track_id)
            if preview_url:
                _LOGGER.info(f"Track {title} by {artist} is premium, but preview available")
                return {
                    "track_id": track_id,
                    "title": title,
                    "artist": artist,
                    "duration_ms": duration_ms,
                    "url": preview_url,
                    "codec": "mp3",
                    "encrypted": False,
                    "decrypt_key": None,
                    "is_premium": True,
                    "is_preview": True,
                }

            _LOGGER.info(f"Track {title} by {artist} requires Yandex Plus subscription")
            return {
                "track_id": track_id,
                "title": title,
                "artist": artist,
                "duration_ms": duration_ms,
                "url": None,
                "codec": None,
                "encrypted": False,
                "decrypt_key": None,
                "is_premium": True,
                "is_preview": False,
                "premium_message": f"Трек {title} от {artist} требует подписки Яндекс Плюс",
            }

        # Get working URL with full info
        download_info = await get_track_download_info(session, track_id, quality)
        if not download_info:
            _LOGGER.warning(f"Could not get URL for track {track_id}")
            return None

        return {
            "track_id": track_id,
            "title": title,
            "artist": artist,
            "duration_ms": duration_ms,
            "url": download_info["url"],
            "codec": download_info["codec"],
            "encrypted": download_info["encrypted"],
            "decrypt_key": download_info.get("decrypt_key"),
            "is_premium": False,
        }

    except Exception as e:
        _LOGGER.error(f"search_and_get_url failed: {e}")
        return None


async def get_stream_url_for_track(
    session: YandexSession,
    track_id: int | str,
    quality: str = QUALITY_LOSSLESS,
) -> str | None:
    """Get a playable stream URL for a track.

    Handles decryption if needed. Returns URL ready for playback.
    For encrypted tracks, downloads, decrypts, and returns a temporary URL.
    """
    info = await get_working_track_url(session, track_id, quality)
    if not info:
        return None

    url = info["url"]
    if not info.get("encrypted"):
        return url

    # For encrypted tracks, we need to download and decrypt
    # This is memory-intensive, so we use a temporary file
    decrypt_key = info.get("decrypt_key")
    if not decrypt_key:
        _LOGGER.warning(f"Encrypted track {track_id} but no decrypt key")
        return url

    try:
        import tempfile
        import aiohttp

        # Download encrypted data
        async with aiohttp.ClientSession() as dl_session:
            async with dl_session.get(url) as resp:
                if resp.status != 200:
                    _LOGGER.warning(f"Failed to download encrypted track: {resp.status}")
                    return url
                encrypted_data = await resp.read()

        # Decrypt
        decrypted_data = await decrypt_yandex_audio(encrypted_data, decrypt_key)

        # Save to temp file
        ext = info.get("codec", "mp3")
        with tempfile.NamedTemporaryFile(
            suffix=f".{ext}",
            prefix="yandex_",
            delete=False,
        ) as f:
            f.write(decrypted_data)
            temp_path = f.name

        _LOGGER.info(f"Decrypted track {track_id} to {temp_path}")
        return temp_path

    except Exception as e:
        _LOGGER.error(f"Failed to decrypt track {track_id}: {e}")
        return url
