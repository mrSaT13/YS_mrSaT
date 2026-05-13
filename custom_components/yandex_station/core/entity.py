import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)


def extract_instance(item: dict) -> str | None:
    try:
        if item.get("type") == "devices.capabilities.on_off":
            return "on"
        if item.get("type") == "devices.capabilities.lock":
            return "lock"
        if item.get("type") == "devices.capabilities.zigbee_node":
            return "zigbee"
        parameters = item.get("parameters")
        if parameters:
            return parameters.get("instance")
        return None
    except (KeyError, TypeError, AttributeError):
        return None


def extract_parameters(items: list[dict]) -> dict:
    result = {}
    if not items or not isinstance(items, list):
        return result
    for item in items:
        try:
            if not isinstance(item, dict):
                continue
            # skip none (unknown) instances
            if instance := extract_instance(item):
                params = item.get("parameters", {})
                result[instance] = {"retrievable": item.get("retrievable", False), **params}
        except (KeyError, TypeError) as e:
            _LOGGER.debug(f"Error extracting parameter: {e}")
    return result


def extract_state(items: list[dict]) -> dict:
    result = {}
    if not items or not isinstance(items, list):
        return result
    for item in items:
        try:
            if not isinstance(item, dict):
                continue
            if instance := extract_instance(item):
                state = item.get("state")
                value = state.get("value") if state else None
                result[instance] = value
        except (KeyError, TypeError, AttributeError) as e:
            _LOGGER.debug(f"Error extracting state: {e}")
    return result


class YandexEntity(Entity):
    def __init__(self, quasar: YandexQuasar, device: dict, config: dict = None):
        self.quasar = quasar
        self.device = device
        self.config = config

        # "online", "unknown" or key not exist
        self._attr_available = device.get("state") != "offline"
        self._attr_name = device["name"]
        self._attr_should_poll = False
        self._attr_unique_id = device["id"].replace("-", "")

        device_id = i["device_id"] if (i := device.get("quasar_info")) else device["id"]

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self.device["name"],
            suggested_area=self.device.get("room_name"),
        )

        if device_info := device.get("parameters", {}).get("device_info", {}):
            for key in ("manufacturer", "model", "sw_version", "hw_version"):
                if value := device_info.get(key):
                    self._attr_device_info[key] = value

        try:
            capabilities = device.get("capabilities") or []
            properties = device.get("properties") or []
            
            self.internal_init(
                extract_parameters(capabilities),
                extract_parameters(properties),
            )
            self.internal_update(
                extract_state(capabilities),
                extract_state(properties),
            )
        except Exception as e:
            _LOGGER.debug("Device init warning: %s", repr(e))

        self.quasar.subscribe_update(device["id"], self.on_update)

    def on_update(self, device: dict):
        self._attr_available = device["state"] in ("online", "unknown")

        self.internal_update(
            extract_state(device["capabilities"]) if "capabilities" in device else {},
            extract_state(device["properties"]) if "properties" in device else {},
        )

        if self.hass and self.entity_id:
            self._async_write_ha_state()

    def internal_init(self, capabilities: dict, properties: dict):
        """Will be called on Entity init. Capabilities and properties will have all
        variants.
        """
        pass

    def internal_update(self, capabilities: dict, properties: dict):
        """Will be called on Entity init and every data update. Variant
        - instance with some value (str, float, dict)
        - instance with null value
        - no instance (if it not upated)
        """
        pass

    async def async_update(self):
        device = await self.quasar.get_device(self.device)
        self.quasar.dispatch_update(device["id"], device)

    async def device_action(self, instance: str, value, relative=False):
        try:
            await self.quasar.device_action(self.device, instance, value, relative)
        except Exception as e:
            raise HomeAssistantError(f"Device action failed: {repr(e)}")

    async def device_actions(self, **kwargs):
        try:
            await self.quasar.device_actions(self.device, **kwargs)
        except Exception as e:
            raise HomeAssistantError(f"Device action failed: {repr(e)}")

    async def device_color(self, **kwargs):
        try:
            await self.quasar.device_color(self.device, **kwargs)
        except Exception as e:
            raise HomeAssistantError(f"Device action failed: {repr(e)}")


class YandexCustomEntity(YandexEntity):
    def __init__(self, quasar: YandexQuasar, device: dict, config: dict):
        self.instance = extract_instance(config)
        super().__init__(quasar, device, config)
        if name := config["parameters"].get("name"):
            self._attr_name += " " + name
        self._attr_unique_id += " " + self.instance
