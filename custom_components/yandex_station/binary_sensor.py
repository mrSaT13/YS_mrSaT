from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .core.entity import YandexCustomEntity, YandexEntity
from .hass import hass_utils

INCLUDE_CAPABILITIES = ("devices.capabilities.lock",)

ENTITY_DESCRIPTIONS = {
    "lock": BinarySensorDeviceClass.LOCK,
}


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        for instance in device["capabilities"]:
            if instance["type"] in INCLUDE_CAPABILITIES:
                entities.append(YandexBinarySensor(quasar, device, instance))
        
        # Добавляем диагностические сенсоры для каждой Станции
        if device.get("type", "").startswith("devices.types.smart_speaker"):
             entities.append(YandexCloudStatusSensor(quasar, device))
             entities.append(YandexLocalStatusSensor(quasar, device))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexBinarySensor(BinarySensorEntity, YandexCustomEntity):
# ... существующий код ...

class YandexCloudStatusSensor(BinarySensorEntity, YandexEntity):
    """Сенсор статуса облачного подключения."""
    _attr_name = "Cloud Connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, quasar, device):
        super().__init__(quasar, device)
        self._attr_unique_id += "_cloud"

    @property
    def is_on(self) -> bool:
        return bool(self.quasar.session.x_token)

class YandexLocalStatusSensor(BinarySensorEntity, YandexEntity):
    """Сенсор статуса локального (Glagol) подключения."""
    _attr_name = "Local Connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, quasar, device):
        super().__init__(quasar, device)
        self._attr_unique_id += "_local"

    @property
    def is_on(self) -> bool:
        # Пытаемся найти объект Станции и проверить его glagol
        for speaker in self.quasar.speakers:
            if speaker["id"] == self.device["id"]:
                if entity := speaker.get("entity"):
                    return entity.glagol and entity.glagol.ws and not entity.glagol.ws.closed
        return False

    def internal_init(self, capabilities: dict, properties: dict):
        # {'access_methods': None, 'instance': 'lock', 'retrievable': True, 'values': ['closed', 'open']}
        if desc := ENTITY_DESCRIPTIONS.get(self.instance):
            self._attr_device_class = desc

    def internal_update(self, capabilities: dict, properties: dict):
        if value := capabilities.get(self.instance):
            if self.instance == "lock":
                # On means open (unlocked), Off means closed (locked)
                self._attr_is_on = value == "open"
