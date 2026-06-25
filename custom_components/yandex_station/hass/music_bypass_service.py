"""Music Plus bypass service for Yandex Station.

Provides yandex_music_play service that:
1. Searches for a track by query
2. Gets a working URL (bypassing Plus restrictions)
3. Plays it on the speaker via streamUrl command
"""

import logging

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import ServiceCall

from .core import utils
from .core.const import DATA_CONFIG, DATA_SPEAKERS, DOMAIN
from .core.music_plus_bypass import search_and_get_url
from .core.yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)


async def async_setup_music_bypass(hass, session: YandexSession):
    """Set up Music Plus bypass service."""
    speakers = hass.data[DOMAIN][DATA_SPEAKERS]

    async def yandex_music_play(call: ServiceCall):
        """Play music from Yandex Music with Plus bypass.

        Service call data:
            query: Search query (e.g. "Marilyn Manson The Beautiful People")
            entity_id: Optional speaker entity ID (if not specified, finds first available)
            quality: Optional quality (lossless, nq, lq) - default lossless
        """
        query = call.data.get("query")
        if not query:
            _LOGGER.error("query parameter required")
            return

        entity_id = call.data.get(ATTR_ENTITY_ID)
        quality = call.data.get("quality", "lossless")

        # Find speaker
        if entity_id:
            speaker = speakers.get(entity_id)
            if not speaker:
                # Try to find by entity_id
                for did, sp in speakers.items():
                    entity = sp.get("entity")
                    if entity and entity.entity_id == entity_id:
                        speaker = sp
                        break
        else:
            # Find first available speaker
            speaker = None
            for did, sp in speakers.items():
                entity = sp.get("entity")
                if entity and entity.hass:
                    speaker = sp
                    break

        if not speaker:
            _LOGGER.error("No speaker found")
            return

        entity = speaker.get("entity")
        if not entity:
            _LOGGER.error("Speaker entity not available")
            return

        _LOGGER.info(f"Searching for: {query}")

        # Search and get URL
        result = await search_and_get_url(session, query, quality)
        if not result:
            _LOGGER.error(f"Could not find track: {query}")
            # Notify user
            hass.components.persistent_notification.async_create(
                f"Track not found: {query}",
                title="Yandex Music"
            )
            return

        _LOGGER.info(
            f"Found: {result['title']} by {result['artist']} "
            f"(duration={result['duration_ms']}ms)"
        )

        # Build stream URL command
        stream_url = result["direct_url"]
        if stream_url:
            # Use the existing stream URL playback mechanism
            from .core.utils import get_stream_url, external_command

            # Determine codec from URL
            if ".mp3" in stream_url:
                ext = "mp3"
            elif ".flac" in stream_url:
                ext = "flac"
            elif ".aac" in stream_url:
                ext = "aac"
            else:
                ext = "mp3"

            # Build the command
            payload = {
                "streamUrl": stream_url,
                "force_restart_player": True,
                "title": result["title"],
                "imageUrl": None,  # could add cover art URL here
            }
            command = external_command("radio_play", payload)

            # Send to speaker via Glagol
            if entity.glagol:
                _LOGGER.debug(f"Sending streamUrl to {entity.name}")
                await entity.glagol.send(command)

                # Notify user
                hass.components.persistent_notification.async_create(
                    f"Now playing: {result['title']} - {result['artist']}",
                    title="Yandex Music"
                )
            else:
                _LOGGER.error(f"Speaker {entity.name} not connected locally")
        else:
            _LOGGER.error(f"No URL for track {result['track_id']}")

    # Register service
    hass.services.async_register(
        DOMAIN,
        "yandex_music_play",
        yandex_music_play,
    )

    _LOGGER.info("Music Plus bypass service registered")
