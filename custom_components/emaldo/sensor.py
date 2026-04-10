"""Sensor platform for Emaldo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EmaldoConfigEntry
from .const import DOMAIN
from .coordinator import EmaldoCoordinator


@dataclass(frozen=True, kw_only=True)
class EmaldoSensorDescription(SensorEntityDescription):
    """Describe an Emaldo sensor."""

    data_key: str
    scale: float = 1.0


SENSOR_DESCRIPTIONS: tuple[EmaldoSensorDescription, ...] = (
    EmaldoSensorDescription(
        key="solar_power",
        translation_key="solar_power",
        data_key="solar_w",
        scale=0.001,  # W to kW
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        data_key="grid_w",
        scale=0.001,
        icon="mdi:transmission-tower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        data_key="battery_w",
        scale=0.001,
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="load_power",
        translation_key="load_power",
        data_key="load_w",
        scale=0.001,
        icon="mdi:home-lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="vehicle_power",
        translation_key="vehicle_power",
        data_key="vehicle_w",
        scale=0.001,
        icon="mdi:car-electric",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        data_key="soc",
        scale=1.0,
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EmaldoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Emaldo sensors from a config entry."""
    entities: list[EmaldoSensor] = []
    for coordinator in entry.runtime_data:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(EmaldoSensor(coordinator, description))
    async_add_entities(entities)


class EmaldoSensor(CoordinatorEntity[EmaldoCoordinator], SensorEntity):
    """Representation of an Emaldo sensor."""

    entity_description: EmaldoSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: EmaldoCoordinator, description: EmaldoSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            name=self.coordinator.device_name,
            manufacturer="Emaldo",
            model=self.coordinator.device_model,
        )

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if not data:
            return None
        raw = data.get(self.entity_description.data_key)
        if raw is None:
            return None
        return round(raw * self.entity_description.scale, 3)
