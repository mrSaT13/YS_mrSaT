"""Music Plus bypass -获得 рабочие ссылки на треки без Плюса.

Основан на подходе YandexMusicBetaMod:
- Использует Desktop HMAC ключ вместо Android
- Повторяет запросы если trackId не совпадает (реклама)
- Проверяет.trackId в ответе
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


async def get_working_track_url(
    session: YandexSession,
    track_id: int | str,
    quality: str = QUALITY_LOSSLESS,
) -> str | None:
    """Get a working download URL for a track.

    Tries Desktop approach first (with retries), then falls back to Android.
    Returns direct URL or None if all attempts fail.
    """
    # Try Desktop approach (with ad bypass retries)
    info = await get_file_info_desktop(session, track_id, quality)
    if info and info.get("direct_url"):
        return info["direct_url"]

    # Try Android approach
    info = await get_file_info_android(session, track_id, quality)
    if info and info.get("direct_url"):
        return info["direct_url"]

    # Try with lower quality
    if quality != QUALITY_LQ:
        info = await get_file_info_desktop(session, track_id, QUALITY_NQ)
        if info and info.get("direct_url"):
            return info["direct_url"]

    return None


async def search_and_get_url(
    session: YandexSession,
    query: str,
    quality: str = QUALITY_LOSSLESS,
) -> dict | None:
    """Search for a track and get a working download URL.

    Returns:
        dict with keys: track_id, title, artist, duration_ms, direct_url
        or None if not found
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

        # Get working URL
        direct_url = await get_working_track_url(session, track_id, quality)
        if not direct_url:
            _LOGGER.warning(f"Could not get URL for track {track_id}")
            return None

        return {
            "track_id": track_id,
            "title": title,
            "artist": artist,
            "duration_ms": duration_ms,
            "direct_url": direct_url,
        }

    except Exception as e:
        _LOGGER.error(f"search_and_get_url failed: {e}")
        return None
