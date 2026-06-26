"""Music Assistant integration for Yandex Station."""
import logging
from homeassistant.core import HomeAssistant
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
        return self._options.get("enabled", False)

    def is_ma_available(self) -> bool:
        if MA_DOMAIN in self.hass.data:
            return True
        try:
            from homeassistant.helpers import entity_registry as er
            er_registry = er.async_get(self.hass)
            for entity in er_registry.entities.values():
                if entity.platform == MA_DOMAIN:
                    return True
        except Exception:
            pass
        try:
            if self.hass.services.has_service(MA_DOMAIN, "play_media"):
                return True
        except Exception:
            pass
        return False

    def _get_configured_ma_player(self):
        v = self._options.get("ma_player")
        return v if v else None

    def _should_announce(self):
        return self._options.get("announce", True)

    def _should_clear_queue(self):
        return self._options.get("clear_queue", True)

    def _should_shuffle(self):
        return self._options.get("shuffle", True)

    def _get_repeat(self):
        return self._options.get("repeat", "off")

    def _get_enqueue_mode(self):
        return self._options.get("enqueue_mode", "replace")

    def _should_fallback_to_similar(self):
        return self._options.get("fallback_to_similar", True)

    def _get_volume(self):
        return self._options.get("volume", 0)

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

    async def _apply_playback_settings(self, ma_entity):
        """Apply shuffle, repeat, volume settings to MA player."""
        try:
            # Volume (0 = don't change)
            volume = self._get_volume()
            if volume > 0:
                await self.hass.services.async_call(
                    "media_player", "volume_set",
                    {"entity_id": ma_entity, "volume_level": volume / 100.0},
                    blocking=True
                )
                _LOGGER.debug(f"MA volume set to {volume}%")

            # Shuffle
            shuffle = self._should_shuffle()
            await self.hass.services.async_call(
                "media_player", "shuffle_set",
                {"entity_id": ma_entity, "shuffle": shuffle},
                blocking=True
            )
            _LOGGER.debug(f"MA shuffle set to {shuffle}")

            # Repeat
            repeat = self._get_repeat()
            await self.hass.services.async_call(
                "media_player", "repeat_set",
                {"entity_id": ma_entity, "repeat": repeat},
                blocking=True
            )
            _LOGGER.debug(f"MA repeat set to {repeat}")

        except Exception as e:
            _LOGGER.debug(f"Failed to apply playback settings: {e}")

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
        _LOGGER.info(f"MA play: type={request_type}, query={query}")
        ma_entity = self.get_ma_entity_for_speaker(speaker_entity_id)
        if not ma_entity:
            return False
        try:
            if self._should_clear_queue() and request_type in ("artist", "album", "playlist"):
                await self._clear_queue(ma_entity)

            if request_type == "artist":
                ok = await self._play_artist(ma_entity, artist or query, announce)
            elif request_type == "track":
                ok = await self._play_track(ma_entity, artist, track or query, announce)
            elif request_type == "album":
                ok = await self._play_artist(ma_entity, query, announce)
            else:
                ok = await self._play_artist(ma_entity, query, announce)

            if ok:
                await self._apply_playback_settings(ma_entity)

            return ok
        except Exception as e:
            _LOGGER.error(f"MA play failed: {e}")
            return False

    async def _clear_queue(self, ma_entity):
        try:
            await self.hass.services.async_call(
                MA_DOMAIN, "clear_queue",
                {"entity_id": ma_entity},
                blocking=True
            )
            _LOGGER.debug(f"MA queue cleared for {ma_entity}")
        except Exception as e:
            _LOGGER.debug(f"Failed to clear queue: {e}")

    async def _play_track(self, ma_entity, artist, track, announce):
        query = f"{artist} {track}".strip() if artist else track
        if announce and self._should_announce():
            await self._announce(f"Playing: {query}")
        enqueue = self._get_enqueue_mode()
        try:
            await self.hass.services.async_call(
                MA_DOMAIN, "play_media",
                {"entity_id": ma_entity, "media_id": query, "media_type": "track", "enqueue": enqueue},
                blocking=True
            )
            _LOGGER.info(f"Playing track: {query}")
            return True
        except Exception as e:
            _LOGGER.error(f"MA play_track failed: {e}")
            return False

    async def _play_artist(self, ma_entity, artist, announce):
        if announce and self._should_announce():
            await self._announce(f"Playing: {artist}")
        enqueue = self._get_enqueue_mode()
        try:
            await self.hass.services.async_call(
                MA_DOMAIN, "play_media",
                {"entity_id": ma_entity, "media_id": artist, "media_type": "artist", "enqueue": enqueue},
                blocking=True
            )
            _LOGGER.info(f"Playing artist: {artist}")
            return True
        except Exception as e:
            _LOGGER.error(f"MA play_artist failed: {e}")
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
