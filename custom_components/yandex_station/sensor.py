import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from .core.const import DOMAIN
from .core.entity import YandexCustomEntity
from .core.yandex_quasar import YandexQuasar
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

# https://yandex.ru/dev/dialogs/smart-home/doc/concepts/device-type-sensor.html
INCLUDE_TYPES = (
    "devices.types.sensor",
    "devices.types.sensor.button",
    "devices.types.sensor.climate",
    "devices.types.sensor.gas",
    "devices.types.sensor.illumination",
    "devices.types.sensor.motion",
    "devices.types.sensor.open",
    "devices.types.sensor.smoke",
    "devices.types.sensor.vibration",
    "devices.types.sensor.water_leak",
    "devices.types.smart_meter",
    "devices.types.smart_meter.cold_water",
    "devices.types.smart_meter.electricity",
    "devices.types.smart_meter.gas",
    "devices.types.smart_meter.heat",
    "devices.types.smart_meter.hot_water",
    "devices.types.socket",
    "devices.types.remote_car",  # fuel_level, petrol_mileage
    "devices.types.remote.ir",  # temperature, humidity
    "devices.types.smart_speaker.yandex.station.pickle",  # co2_level, temp., hum.
    "devices.types.smart_speaker.yandex.station.plum",  # battery
)
INCLUDE_PROPERTIES = ("devices.properties.float", "devices.properties.event")

SENSOR = SensorDeviceClass  # just to reduce the code

ENTITY_DESCRIPTIONS: dict[str, dict] = {
    "temperature": {"class": SENSOR.TEMPERATURE, "units": UnitOfTemperature.CELSIUS},
    "humidity": {"class": SENSOR.HUMIDITY, "units": PERCENTAGE},
    "pm2.5_density": {
        "class": SENSOR.PM25,
        "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    "pm10_density": {
        "class": SENSOR.PM10,
        "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    "co2_level": {"class": SENSOR.CO2, "units": CONCENTRATION_PARTS_PER_MILLION},
    "illumination": {"class": SENSOR.ILLUMINANCE, "units": LIGHT_LUX},
    "battery_level": {"class": SENSOR.BATTERY, "units": PERCENTAGE},
    "pressure": {"class": SENSOR.PRESSURE, "units": UnitOfPressure.MMHG},
    "voltage": {"class": SENSOR.VOLTAGE, "units": UnitOfElectricPotential.VOLT},
    "power": {"class": SENSOR.POWER, "units": UnitOfPower.WATT},
    "amperage": {"class": SENSOR.CURRENT, "units": UnitOfElectricCurrent.AMPERE},
    "vibration": {"class": SENSOR.ENUM},
    "open": {"class": SENSOR.ENUM},
    "button": {"class": SENSOR.ENUM},
    "motion": {"class": SENSOR.ENUM},
    "smoke": {"class": SENSOR.ENUM},
    "gas": {"class": SENSOR.ENUM},
    "food_level": {"class": SENSOR.ENUM},
    "water_level": {"class": SENSOR.ENUM},
    "water_leak": {"class": SENSOR.ENUM},
    "electricity_meter": {"class": SENSOR.ENERGY, "units": UnitOfEnergy.KILO_WATT_HOUR},
    "gas_meter": {"class": SENSOR.GAS, "units": UnitOfVolume.CUBIC_METERS},
    "water_meter": {"class": SENSOR.WATER, "units": UnitOfVolume.CUBIC_METERS},
    # there is no better option than a battery for fuel_level
    "fuel_level": {"class": SENSOR.BATTERY, "units": PERCENTAGE},
    "petrol_mileage": {"class": SENSOR.DISTANCE, "units": UnitOfLength.KILOMETERS},
}


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.include_devices(hass, entry):
        if "properties" in config:
            instances = config["properties"]
        elif device["type"] in INCLUDE_TYPES:
            instances = ENTITY_DESCRIPTIONS.keys()  # all supported instances
        else:
            continue

        for instance in device["properties"]:
            if instance["type"] not in INCLUDE_PROPERTIES:
                continue
            if instance["parameters"]["instance"] in instances:
                entities.append(YandexCustomSensor(quasar, device, instance))

    # one lyrics sensor per Yandex Station speaker
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    for speaker in quasar.speakers:
        entities.append(YandexLyricsSensor(hass, quasar, speaker))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexCustomSensor(SensorEntity, YandexCustomEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        if desc := ENTITY_DESCRIPTIONS.get(self.instance):
            self._attr_device_class = desc["class"]
            if "units" in desc:
                self._attr_native_unit_of_measurement = desc["units"]
                self._attr_state_class = SensorStateClass.MEASUREMENT
        try:
            if self.config["parameters"]["range"]["precision"] == 1:
                self._attr_suggested_display_precision = 0
        except KeyError:
            pass

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in properties:
            self._attr_native_value = properties[self.instance]


# noinspection PyAbstractClass
class YandexLyricsSensor(SensorEntity):
    """Lyrics of the current track on a Yandex Station speaker.

    State is the first non-empty line of the lyrics (or "No lyrics").
    Attributes expose the full lyrics, title, and artist.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:text-lyrics"

    def __init__(self, hass, quasar: YandexQuasar, speaker: dict):
        self.hass = hass
        self.quasar = quasar
        self.device = speaker

        device_id = speaker["quasar_info"]["device_id"]
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}-lyrics"
        self._attr_name = f"{speaker['name']} Lyrics"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
        )

        self._track_id: str | None = None
        self._title: str | None = None
        self._artist: str | None = None
        self._lyrics: str | None = None
        self._attr_native_value: str | None = None
        self._attr_extra_state_attributes: dict = {}

    async def async_added_to_hass(self):
        # media_player is set up before sensor in PLATFORMS, so the entity
        # should already be in the registry by the time we get here.
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(self.hass)
        mp_entity_id = registry.async_get_entity_id(
            "media_player", DOMAIN, self._device_id
        )
        if not mp_entity_id:
            return
        from homeassistant.helpers.event import async_track_state_change_event
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, mp_entity_id, self._on_speaker_state
            )
        )
        state = self.hass.states.get(mp_entity_id)
        if state:
            self._maybe_refresh(state)

    @callback
    def _on_speaker_state(self, event):
        new_state = event.data.get("new_state")
        if new_state is not None:
            self._maybe_refresh(new_state)

    def _maybe_refresh(self, state):
        # YandexStation sets media_content_id to playerState["id"] which is the
        # Yandex.Music track id (digits) for music tracks.
        track_id = state.attributes.get("media_content_id")
        title = state.attributes.get("media_title")
        artist = state.attributes.get("media_artist")

        if not track_id or not str(track_id).isdigit():
            return

        if str(track_id) == self._track_id and self._lyrics is not None:
            return

        self._track_id = str(track_id)
        self._title = title
        self._artist = artist
        self.hass.async_create_task(self._fetch_lyrics())

    async def _fetch_lyrics(self):
        try:
            r = await self.quasar.session.get(
                f"https://api.music.yandex.net/tracks/{self._track_id}/lyrics",
            )
            resp = await r.json()
        except Exception as e:
            _LOGGER.debug(f"lyrics fetch failed for track {self._track_id}: {e}")
            return

        # API response shape:
        #   {"result": {"lyrics": {"text": "...", "fullLyrics": "..."}}}
        result = (resp or {}).get("result") or {}
        lyrics_obj = result.get("lyrics") or {}
        text = (lyrics_obj.get("text") or "").strip() or (
            (lyrics_obj.get("fullLyrics") or "").strip()
        )

        if not text:
            self._attr_native_value = "No lyrics"
            self._lyrics = ""
        else:
            self._lyrics = text
            first_line = next(
                (ln.strip() for ln in text.splitlines() if ln.strip()), "No lyrics"
            )
            self._attr_native_value = first_line[:255]

        self._attr_extra_state_attributes = {
            "lyrics": self._lyrics,
            "title": self._title,
            "artist": self._artist,
            "track_id": self._track_id,
        }
        self.async_write_ha_state()
