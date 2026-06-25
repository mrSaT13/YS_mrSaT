"""Music Assistant integration for Yandex Station."""
import logging
from typing import Optional
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from ..core.const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MA_DOMAIN = "music_assistant"
MIN_SEARCH_INTERVAL = 10


class MusicAssistantBridge:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._last_search_time = {}
        self._options = {}

    def load_options(self, config_entry):
        self._options = config_entry.options.get("music_assistant", {})
        _LOGGER.debug(f"MA bridge options loaded: {self._options}")

    def is_enabled(self):
        enabled = self._options.get("enabled", False)
        _LOGGER.debug(f"MA bridge enabled={enabled}, ma_available={self.is_ma_available()}")
        return enabled

    def is_ma_available(self):
        return MA_DOMAIN in self.hass.data

    def _get_configured_ma_player(self):
        v = self._options.get("ma_player")
        return v if v else None

    def _should_announce(self):
        return self._options.get("announce", True)

    def _should_fallback_to_similar(self):
        return self._options.get("fallback_to_similar", True)

    def get_ma_entity_for_speaker(self, speaker_entity_id):
        if not self.is_ma_available():
            return None
        configured = self._get_configured_ma_player()
        if configured:
            return configured
        ec = self.hass.data.get("entity_components", {}).get("media_player")
        if not ec:
            return None
        for entity in ec.entities:
            if (hasattr(entity, "player_id") and entity.platform
                    and entity.platform.platform_name == MA_DOMAIN):
                return entity.entity_id
        return None

    def parse_voice_request(self, player_state):
        title = player_state.get("title", "")
        subtitle = player_state.get("subtitle", "")
        playlist_type = player_state.get("playlistType", "")
        result = {"type": "unknown", "artist": subtitle or "", "track": title or "", "query": ""}
        if playlist_type == "Artist":
            result["type"] = "artist"
            result["query"] = subtitle or title
        elif playlist_type == "Album":
            result["type"] = "album"
            result["query"] = f"{subtitle} {title}".strip()
        elif playlist_type == "Track":
            result["type"] = "track"
            result["query"] = f"{subtitle} {title}".strip()
        elif playlist_type == "Playlist":
            result["type"] = "playlist"
            result["query"] = title
        else:
            if subtitle and title:
                result["type"] = "track"
                result["query"] = f"{subtitle} {title}".strip()
            elif title:
                result["type"] = "artist"
                result["query"] = title
        return result

    async def search_and_play(self, speaker_entity_id, artist=None, track=None, request_type="track", announce=True):
        import time
        now = time.time()
        last_search = self._last_search_time.get(speaker_entity_id, 0)
        if now - last_search < MIN_SEARCH_INTERVAL:
            return False
        self._last_search_time[speaker_entity_id] = now
        if not self.is_ma_available():
            return False
        if artist and track:
            query = f"{artist} {track}"
        elif artist:
            query = artist
        elif track:
            query = track
        else:
            return False
        _LOGGER.info(f"MA search: type={request_type}, query={query}")
        ma_entity = self.get_ma_entity_for_speaker(speaker_entity_id)
        if not ma_entity:
            return False
        try:
            media_type = "artist" if request_type == "artist" else ("album" if request_type == "album" else "track")
            result = await self.hass.services.async_call(
                MA_DOMAIN, "search", {"query": query, "media_type": media_type},
                blocking=True, return_response=True,
            )
            if not result:
                if self._should_fallback_to_similar() and artist:
                    return await self._play_artist_radio(ma_entity, artist, announce)
                return False
            provider_results = result.get("provider", {})
            for provider_name, items in provider_results.items():
                if not items:
                    continue
                if request_type == "track":
                    for item in items:
                        if self._is_track_match(item, artist, track):
                            return await self._play_item(ma_entity, item, announce, f"Вот что я нашла: {item.get('name', query)}")
                    if items:
                        return await self._play_item(ma_entity, items[0], announce, f"Точный трек не найден. Вот что-то похожее: {items[0].get('name', query)}")
                elif request_type == "artist":
                    if items:
                        first = items[0]
                        if first.get("media_type") == "artist":
                            return await self._play_artist_radio(ma_entity, first.get("name", artist), announce)
                        return await self._play_item(ma_entity, first, announce, f"Исполнитель: {first.get('name', artist)}")
                elif request_type == "album":
                    if items:
                        return await self._play_item(ma_entity, items[0], announce, f"Альбом: {items[0].get('name', query)}")
            if self._should_fallback_to_similar() and artist:
                return await self._play_artist_radio(ma_entity, artist, announce)
            return False
        except Exception as e:
            _LOGGER.error(f"MA search/play failed: {e}")
            return False

    def _is_track_match(self, item, artist, track):
        item_name = (item.get("name", "") or "").lower()
        item_artist = (item.get("artist", "") or "").lower()
        track_lower = (track or "").lower()
        artist_lower = (artist or "").lower()
        if track_lower and track_lower in item_name:
            if not artist or artist_lower in item_artist:
                return True
        return False

    async def _play_item(self, ma_entity, item, announce, message):
        media_uri = item.get("uri")
        if not media_uri:
            return False
        if announce and self._should_announce():
            await self._announce(message)
        try:
            await self.hass.services.async_call(MA_DOMAIN, "play_media",
                {"entity_id": ma_entity, "media_id": media_uri}, blocking=True)
            _LOGGER.info(f"Playing: {item.get('name', media_uri)}")
            return True
        except Exception as e:
            _LOGGER.error(f"MA play_media failed: {e}")
            return False

    async def _play_artist_radio(self, ma_entity, artist, announce):
        if announce and self._should_announce():
            await self._announce(f"Включаю радио: {artist}")
        try:
            await self.hass.services.async_call(MA_DOMAIN, "play_media",
                {"entity_id": ma_entity, "media_id": artist, "media_type": "artist", "radio_mode": True},
                blocking=True)
            _LOGGER.info(f"Playing artist radio: {artist}")
            return True
        except Exception as e:
            _LOGGER.error(f"MA artist radio failed: {e}")
            return False

    async def _announce(self, text):
        try:
            speakers = self.hass.data.get(DOMAIN, {}).get("speakers", {})
            for did, speaker in speakers.items():
                entity = speaker.get("entity")
                if entity and entity.hass and hasattr(entity, "glagol") and entity.glagol:
                    from ..core.utils import external_command
                    command = external_command("tts", {"text": text})
                    await entity.glagol.send(command)
                    return
        except Exception as e:
            _LOGGER.debug(f"Announce failed: {e}")


_bridge = None


def get_bridge(hass):
    global _bridge
    if _bridge is None:
        _bridge = MusicAssistantBridge(hass)
    return _bridge
