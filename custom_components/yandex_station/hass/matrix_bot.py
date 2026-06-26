"""Matrix bot integration for Yandex Station."""

import logging
import asyncio
from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

EVENT_MATRIX_TEXT = "yandex_station_matrix_text"


class MatrixBotHandler:
    """Handle Matrix bot integration with Yandex Conversation."""

    def __init__(self, hass: HomeAssistant, config: dict):
        self.hass = hass
        self.config = config
        self.server_url = config.get("server_url")
        self.room_id = config.get("room_id")
        self.access_token = config.get("access_token")
        self.client = None
        self.sync_token = None
        self.sent_event_ids: list = []
        self._conversation_entity_id: Optional[str] = None
        self._sync_task = None

    @property
    def is_enabled(self) -> bool:
        return self.config.get("enabled", True)

    async def async_start(self):
        if not self.is_enabled:
            _LOGGER.info("Matrix bot disabled in config")
            return

        try:
            import nio

            if not self.server_url or not self.access_token:
                _LOGGER.error("Matrix server_url или access_token не установлены")
                return

            self.client = nio.AsyncClient(self.server_url)
            self.client.access_token = self.access_token

            _LOGGER.info(f"Matrix bot initialized: {self.server_url}")

            self._find_conversation_entity()

            self._sync_task = self.hass.create_task(self._sync_loop())

        except ImportError:
            _LOGGER.error("Matrix требует установки matrix-nio: pip install matrix-nio")
        except Exception as e:
            _LOGGER.error(f"Ошибка инициализации Matrix: {e}")
            self.client = None

    def _find_conversation_entity(self):
        configured = self.config.get("conversation_entity")
        if configured:
            entity = self.hass.data.get("entity_components", {}).get("conversation")
            if entity:
                for e in entity.entities:
                    if e.entity_id == configured:
                        self._conversation_entity_id = configured
                        _LOGGER.info(f"Using configured conversation entity: {configured}")
                        return
            if self.hass.states.get(configured):
                self._conversation_entity_id = configured
                _LOGGER.info(f"Using configured conversation entity: {configured}")
                return
            _LOGGER.warning(f"Configured entity {configured} not found, searching...")

        try:
            ec = self.hass.data.get("entity_components", {}).get("conversation")
            if ec:
                for entity in ec.entities:
                    if hasattr(entity, '_attr_unique_id') and 'yandex_station' in getattr(entity, '_attr_unique_id', ''):
                        self._conversation_entity_id = entity.entity_id
                        _LOGGER.info(f"Found conversation entity: {entity.entity_id}")
                        return
                    if hasattr(entity, 'platform') and hasattr(entity.platform, 'platform_name'):
                        if entity.platform.platform_name == "yandex_station":
                            self._conversation_entity_id = entity.entity_id
                            _LOGGER.info(f"Found conversation entity: {entity.entity_id}")
                            return

            for entity_id in self.hass.states.async_entity_ids("conversation"):
                if "yandex_station" in entity_id:
                    self._conversation_entity_id = entity_id
                    _LOGGER.info(f"Found conversation entity (states): {entity_id}")
                    return

            _LOGGER.warning("No Yandex Station conversation entity found")

        except Exception as e:
            _LOGGER.debug(f"Error finding conversation entity: {e}")

    async def async_stop(self):
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        if self.client:
            try:
                await self.client.close()
                _LOGGER.info("Matrix bot stopped")
            except Exception as e:
                _LOGGER.error(f"Ошибка при остановке Matrix: {e}")

    async def _sync_loop(self):
        await asyncio.sleep(2)

        retry_delay = 1
        max_delay = 60

        while self.client:
            try:
                if not self.client or not self.room_id:
                    await asyncio.sleep(5)
                    retry_delay = 1
                    continue

                response = await self.client.sync(
                    since=self.sync_token,
                    timeout=30000,
                    full_state=False
                )

                if not hasattr(response, 'next_batch'):
                    _LOGGER.warning(f"Matrix sync failed: {response}")
                    await asyncio.sleep(min(retry_delay, max_delay))
                    retry_delay = min(retry_delay * 2, max_delay)
                    continue

                self.sync_token = response.next_batch
                retry_delay = 1

                for room_id, room_info in response.rooms.join.items():
                    if room_id == self.room_id:
                        await self._process_room_messages(room_id, room_info.timeline.events)

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in sync loop: {e}")
                await asyncio.sleep(min(retry_delay, max_delay))
                retry_delay = min(retry_delay * 2, max_delay)

    async def _process_room_messages(self, room_id: str, events: list):
        import nio

        for event in events:
            if not isinstance(event, nio.RoomMessageText):
                continue

            if event.sender == self.client.user_id:
                continue

            if event.event_id in self.sent_event_ids:
                _LOGGER.debug(f"Skipping own message: {event.body}")
                continue

            if not event.body or not event.body.strip():
                continue

            text = event.body.strip()
            _LOGGER.info(f"Matrix message from {event.sender}: {text}")

            await self._handle_conversation(text, event.sender)

    async def _handle_conversation(self, text: str, sender: str):
        if not self._conversation_entity_id:
            _LOGGER.warning("No conversation entity configured")
            self._find_conversation_entity()
            if not self._conversation_entity_id:
                await self.send_message("❌ Колонка не найдена. Включите conversation entity в настройках.")
                return

        try:
            ec = self.hass.data.get("entity_components", {}).get("conversation")
            entity = None
            if ec:
                for e in ec.entities:
                    if e.entity_id == self._conversation_entity_id:
                        entity = e
                        break

            if not entity:
                await self.send_message(f"❌ Conversation entity {self._conversation_entity_id} не найдена")
                return

            from homeassistant.components.conversation import ConversationInput
            user_input = ConversationInput(
                text=text,
                language="ru",
                conversation_id=None,
                device_id=None,
            )

            result = await entity.async_process(user_input)

            response_text = None
            if result and result.response:
                response_text = result.response.speech.get("plain", {}).get("speech", "")

            if response_text:
                _LOGGER.info(f"Yandex response: {response_text}")
                await self.send_message(f"🤖 {response_text}")
            else:
                _LOGGER.debug("No text response from conversation")
                await self.send_message("🤔 Нет ответа от Алисы")

        except Exception as e:
            _LOGGER.error(f"Conversation process failed: {e}", exc_info=True)
            await self.send_message(f"❌ Ошибка: {str(e)[:100]}")

    async def send_message(self, text: str) -> bool:
        if not self.client or not self.room_id:
            return False

        try:
            import nio

            response = await self.client.room_send(
                room_id=self.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": text,
                }
            )

            if hasattr(response, 'event_id') and response.event_id:
                self.sent_event_ids.append(response.event_id)
                _LOGGER.debug(f"Sent to Matrix: {text} (event_id: {response.event_id})")
            elif not hasattr(response, 'status_code') or getattr(response, 'status_code', None) == "M_OK":
                _LOGGER.debug(f"Sent to Matrix: {text}")
            else:
                _LOGGER.error(f"Ошибка отправки в Matrix: {getattr(response, 'status_code', 'unknown')}")
                return False

            if len(self.sent_event_ids) > 100:
                self.sent_event_ids = self.sent_event_ids[-50:]

            return True

        except Exception as e:
            _LOGGER.error(f"Ошибка при отправке в Matrix: {e}")
            return False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    if "yandex_station" not in config:
        return True

    matrix_config = config.get("yandex_station", {}).get("matrix_bot")
    if not matrix_config:
        return True

    handler = MatrixBotHandler(hass, matrix_config)
    hass.data.setdefault("yandex_station_matrix", {})["handler"] = handler

    async def start_handler(event):
        await handler.async_start()

    async def stop_handler(event):
        await handler.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_handler)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_handler)

    @callback
    def handle_matrix_text(event):
        text = event.data.get("text")
        room_id = event.data.get("room_id")
        hass.bus.async_fire(
            "yandex_station_matrix_text",
            {"text": text, "room_id": room_id}
        )

    hass.bus.async_listen(EVENT_MATRIX_TEXT, handle_matrix_text)

    _LOGGER.info("Matrix bot integration loaded")
    return True
