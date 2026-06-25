"""Matrix bot integration for Yandex Station."""

import logging
import asyncio
from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

# Matrix events
EVENT_MATRIX_TEXT = "yandex_station_matrix_text"
EVENT_MATRIX_MESSAGE_RESPONSE = "matrix_message_response"


class MatrixBotHandler:
    """Handle Matrix bot integration with Yandex Conversation."""

    def __init__(self, hass: HomeAssistant, config: dict):
        """Initialize Matrix bot handler."""
        self.hass = hass
        self.config = config
        self.server_url = config.get("server_url")
        self.room_id = config.get("room_id")
        self.access_token = config.get("access_token")
        self.client = None
        self.sync_token = None
        self.sent_event_ids: list = []  # Sent by us - don't process again

    async def async_start(self):
        """Start Matrix bot client."""
        try:
            # Import nio here to avoid import errors if not installed
            import nio

            if not self.server_url or not self.access_token:
                _LOGGER.error("Matrix server_url или access_token не установлены")
                return
            
            self.client = nio.AsyncClient(self.server_url)
            self.client.access_token = self.access_token
            
            _LOGGER.info(f"Matrix bot initialized: {self.server_url}")
            
            # Start sync loop
            self.hass.create_task(self._sync_loop())
            
        except ImportError:
            _LOGGER.error("Matrix требует установки matrix-nio: pip install matrix-nio")
        except Exception as e:
            _LOGGER.error(f"Ошибка инициализации Matrix: {e}")
            self.client = None

    async def async_stop(self):
        """Stop Matrix bot client."""
        if self.client:
            try:
                await self.client.close()
                _LOGGER.info("Matrix bot stopped")
            except Exception as e:
                _LOGGER.error(f"Ошибка при остановке Matrix: {e}")

    async def _sync_loop(self):
        """Sync messages from Matrix room."""
        await asyncio.sleep(2)  # Wait for client initialization
        
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
                
                # Check if sync was successful (SyncResponse doesn't have status_code)
                if not hasattr(response, 'next_batch'):
                    _LOGGER.warning(f"Matrix sync failed: {response}")
                    await asyncio.sleep(min(retry_delay, max_delay))
                    retry_delay = min(retry_delay * 2, max_delay)
                    continue
                
                self.sync_token = response.next_batch
                retry_delay = 1  # Reset on success
                
                # Process room messages
                for room_id, room_info in response.rooms.join.items():
                    if room_id == self.room_id:
                        await self._process_room_messages(room_id, room_info.timeline.events)
                
                # Avoid busy loop
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in sync loop: {e}")
                await asyncio.sleep(min(retry_delay, max_delay))
                retry_delay = min(retry_delay * 2, max_delay)

    async def _process_room_messages(self, room_id: str, events: list):
        """Process incoming room messages."""
        import nio
        
        for event in events:
            if not isinstance(event, nio.RoomMessageText):
                continue
            
            # Skip bot's own messages
            if event.sender == self.client.user_id:
                continue
            
            # Skip messages that we sent (to prevent infinite loop)
            if event.event_id in self.sent_event_ids:
                _LOGGER.debug(f"Skipping own message: {event.body}")
                continue
            
            # Skip empty messages
            if not event.body or not event.body.strip():
                continue
            
            _LOGGER.debug(f"Matrix message from {event.sender}: {event.body}")
            
            # Fire Home Assistant event
            self.hass.bus.async_fire(
                EVENT_MATRIX_TEXT,
                {
                    "text": event.body,
                    "sender": event.sender,
                    "room_id": room_id,
                    "event_id": event.event_id,
                }
            )

    async def send_message(self, text: str) -> bool:
        """Send message to Matrix room."""
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
            
            if response.status_code == "M_OK":
                # Mark this event_id as sent by us (don't reprocess it)
                if hasattr(response, 'event_id'):
                    self.sent_event_ids.append(response.event_id)
                    _LOGGER.debug(f"Sent to Matrix: {text} (event_id: {response.event_id})")
                else:
                    _LOGGER.debug(f"Sent to Matrix: {text}")

                # Clean up old event_ids to avoid memory leak
                if len(self.sent_event_ids) > 100:
                    self.sent_event_ids = self.sent_event_ids[-50:]
                
                return True
            else:
                _LOGGER.error(f"Ошибка отправки в Matrix: {response.status_code}")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Ошибка при отправке в Matrix: {e}")
            return False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Matrix bot handler."""
    if "yandex_station" not in config:
        return True
    
    matrix_config = config.get("yandex_station", {}).get("matrix_bot")
    if not matrix_config:
        return True
    
    handler = MatrixBotHandler(hass, matrix_config)
    hass.data.setdefault("yandex_station_matrix", {})["handler"] = handler
    
    async def start_handler(event):
        """Start handler on HA startup."""
        await handler.async_start()
    
    async def stop_handler(event):
        """Stop handler on HA shutdown."""
        await handler.async_stop()
    
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_handler)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_handler)
    
    # Listen for conversation responses
    @callback
    def handle_matrix_text(event):
        """Handle incoming Matrix text."""
        text = event.data.get("text")
        room_id = event.data.get("room_id")
        
        # Fire conversation event to be handled by automation
        hass.bus.async_fire(
            "yandex_station_matrix_text",
            {
                "text": text,
                "room_id": room_id,
            }
        )
    
    hass.bus.async_listen(EVENT_MATRIX_TEXT, handle_matrix_text)
    
    _LOGGER.info("Matrix bot integration loaded")
    return True
