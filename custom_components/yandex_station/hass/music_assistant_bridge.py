"""Music Assistant integration for Yandex Station."""
import logging
from homeassistant.core import HomeAssistant
from ..core.const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MA_DOMAIN = "music_assistant"
MIN_SEARCH_INTERVAL = 10
MA_API_PLAY_MEDIA = "/api/players/{player_id}/play_media"
MA_API_COMMAND = "/api/command"
MA_API_PLAYERS = "/api/players"


class MusicAssistantBridge:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._last_search_time = {}
        self._options = {}
        self._active_ma_players = {}  # speaker_entity_id -> ma_entity_id
        self._direct_player_cache = {}  # player_id -> {name, state, raw}

    def load_options(self, config_entry):
        self._options = config_entry.options.get("music_assistant", {})
        self._ma_url = self._options.get("ma_url", "").rstrip("/")
        self._ma_token = self._options.get("ma_token", "")
        _LOGGER.debug(f"MA bridge options loaded: enabled={self.is_enabled()}, "
                      f"ma_url={self._ma_url}, player={self._get_configured_ma_player()}")

        # Fetch direct API players on startup
        if self._use_direct_api:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._fetch_direct_players())
                else:
                    loop.run_until_complete(self._fetch_direct_players())
            except Exception as e:
                _LOGGER.debug(f"Failed to fetch direct players on load: {e}")

    async def _fetch_direct_players(self):
        """Fetch and cache player list from MA direct API."""
        try:
            players = await self._direct_player_list()
            self._direct_player_cache = {}
            for p in players:
                pid = p.get("player_id", p.get("id", ""))
                name = p.get("name", pid)
                state = p.get("state", {}).get("status", "idle")
                if pid:
                    self._direct_player_cache[pid] = {
                        "name": name,
                        "state": state,
                        "raw": p,
                    }
            _LOGGER.info(f"MA direct: cached {len(self._direct_player_cache)} players: "
                         f"{list(self._direct_player_cache.keys())}")
        except Exception as e:
            _LOGGER.debug(f"MA direct player fetch failed: {e}")

    @property
    def _use_direct_api(self) -> bool:
        """True when MA runs outside HA and we have URL + token."""
        return bool(self._ma_url and self._ma_token)

    def _direct_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._ma_token}",
                "Content-Type": "application/json"}

    async def _direct_get(self, path: str) -> dict | None:
        """GET request to MA REST API."""
        import aiohttp
        url = f"{self._ma_url}{path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._direct_headers(),
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    _LOGGER.warning(f"MA API GET {path} returned {resp.status}")
        except Exception as e:
            _LOGGER.error(f"MA API GET {path} failed: {e}")
        return None

    async def _direct_post(self, path: str, payload: dict) -> dict | None:
        """POST request to MA REST API."""
        import aiohttp
        url = f"{self._ma_url}{path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload,
                                        headers=self._direct_headers(),
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text()
                    if resp.status in (200, 201):
                        try:
                            import json
                            return json.loads(text)
                        except Exception:
                            return {"status": "ok"}
                    _LOGGER.warning(f"MA API POST {path} returned {resp.status}: {text[:300]}")
        except Exception as e:
            _LOGGER.error(f"MA API POST {path} failed: {e}")
        return None

    async def _direct_play_media(self, player_id: str, media_id: str,
                                  media_type: str = "artist",
                                  enqueue: str = "replace") -> bool:
        """Play media via MA direct REST API."""
        payload = {
            "media_id": media_id,
            "media_type": media_type,
        }
        if enqueue:
            payload["enqueue"] = enqueue

        path = MA_API_PLAY_MEDIA.format(player_id=player_id)
        result = await self._direct_post(path, payload)
        if result is not None:
            _LOGGER.info(f"MA direct play: player={player_id}, type={media_type}, id={media_id}")
            return True
        return False

    async def _direct_player_list(self) -> list:
        """Get list of players from MA REST API."""
        result = await self._direct_get(MA_API_PLAYERS)
        if result and isinstance(result, list):
            return result
        return []

    async def _direct_player_state(self, player_id: str) -> str | None:
        """Get player state from MA REST API."""
        result = await self._direct_get(f"{MA_API_PLAYERS}/{player_id}")
        if result:
            return result.get("state", {}).get("status")
        return None

    def is_enabled(self):
        return self._options.get("enabled", False)

    def is_ma_available(self) -> bool:
        # Direct API: URL + token configured
        if self._use_direct_api:
            return True
        # HA-integrated MA
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

    def get_all_ma_players(self) -> dict:
        """Get all Music Assistant media_player entities."""
        players = {}
        try:
            from homeassistant.helpers import entity_registry as er
            er_registry = er.async_get(self.hass)
            for entity_id, entity in er_registry.entities.items():
                if entity.platform == MA_DOMAIN and entity.domain == "media_player":
                    state = self.hass.states.get(entity_id)
                    name = state.attributes.get("friendly_name", entity_id) if state else entity_id
                    players[entity_id] = f"{name} (MA)"
        except Exception as e:
            _LOGGER.debug(f"MA player discovery failed: {e}")

        if not players:
            try:
                ec = self.hass.data.get("entity_components", {}).get("media_player")
                if ec:
                    for entity in ec.entities:
                        if (hasattr(entity, "player_id") and entity.platform
                                and entity.platform.platform_name == MA_DOMAIN):
                            players[entity.entity_id] = f"{entity.name} (MA)"
            except Exception as e:
                _LOGGER.debug(f"MA player discovery via entity_components failed: {e}")

        return players

    def get_all_media_players(self) -> dict:
        """Get all media_player entities."""
        players = {}
        try:
            all_entities = self.hass.states.async_entity_ids("media_player")
            for entity_id in all_entities:
                state = self.hass.states.get(entity_id)
                if state:
                    name = state.attributes.get("friendly_name", entity_id)
                    players[entity_id] = name
        except Exception as e:
            _LOGGER.debug(f"Media player discovery failed: {e}")
        return players

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

        # Direct API path: no HA entity needed
        if self._use_direct_api:
            return await self._search_and_play_direct(
                speaker_entity_id, artist, track, request_type, query, announce)

        # HA-integrated path
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
                self._active_ma_players[speaker_entity_id] = ma_entity

            return ok
        except Exception as e:
            _LOGGER.error(f"MA play failed: {e}")
            return False

    async def _search_and_play_direct(self, speaker_entity_id, artist, track,
                                       request_type, query, announce):
        """Play via direct MA REST API (standalone MA server)."""
        try:
            # Find the target player
            player_id = self._get_direct_player_id()
            if not player_id:
                _LOGGER.warning("MA direct: no player_id found")
                return False

            if announce and self._should_announce():
                await self._announce(f"Playing: {query}")

            enqueue = self._get_enqueue_mode()
            media_id = query
            media_type = request_type if request_type in ("artist", "track", "album") else "artist"

            # For track with artist, use combined query
            if request_type == "track" and artist and track:
                media_id = f"{artist} {track}"

            ok = await self._direct_play_media(
                player_id, media_id, media_type=media_type, enqueue=enqueue)

            if ok:
                self._active_ma_players[speaker_entity_id] = player_id
                # Apply settings via direct API
                await self._direct_apply_settings(player_id)

            return ok

        except Exception as e:
            _LOGGER.error(f"MA direct play failed: {e}")
            return False

    def _get_direct_player_id(self) -> str | None:
        """Get player_id for direct API calls."""
        # Use configured player
        configured = self._get_configured_ma_player()
        if configured:
            # If it's an HA entity_id, extract the player_id part
            if "." in configured:
                pid = configured.split(".")[-1]
            else:
                pid = configured
            # Verify it exists in cache
            if pid in self._direct_player_cache:
                return pid
            # May not be cached yet, return anyway
            return pid

        # Auto-detect: pick first available player from cache
        if self._direct_player_cache:
            for pid, info in self._direct_player_cache.items():
                if info.get("state") in ("playing", "paused", "idle"):
                    _LOGGER.info(f"MA direct: auto-selected player '{info['name']}' ({pid})")
                    return pid

        # Fallback: try options
        return self._options.get("ma_player_id", None)

    async def _direct_apply_settings(self, player_id: str):
        """Apply shuffle/repeat/volume via direct API."""
        try:
            volume = self._get_volume()
            if volume > 0:
                await self._direct_post(
                    f"{MA_API_PLAYERS}/{player_id}/command",
                    {"command": "volume_set", "volume_level": volume / 100.0})

            shuffle = self._should_shuffle()
            await self._direct_post(
                f"{MA_API_PLAYERS}/{player_id}/command",
                {"command": "shuffle_set", "shuffle": shuffle})

            repeat = self._get_repeat()
            await self._direct_post(
                f"{MA_API_PLAYERS}/{player_id}/command",
                {"command": "repeat_set", "repeat": repeat})

        except Exception as e:
            _LOGGER.debug(f"MA direct settings failed: {e}")

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
