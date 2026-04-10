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
from homeassistant.const import UnitOfPower
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

    stat_type: str
    value_index: int
    scale: float = 0.001  # API returns watts, convert to kW


SENSOR_DESCRIPTIONS: tuple[EmaldoSensorDescription, ...] = (
    # Solar
    EmaldoSensorDescription(
        key="solar_power",
        translation_key="solar_power",
        stat_type="mppt",
        value_index=-1,  # sum of all values
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="solar_string_1",
        translation_key="solar_string_1",
        stat_type="mppt",
        value_index=0,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="solar_string_2",
        translation_key="solar_string_2",
        stat_type="mppt",
        value_index=1,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Battery
    EmaldoSensorDescription(
        key="battery_charge_power",
        translation_key="battery_charge_power",
        stat_type="battery",
        value_index=0,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="battery_discharge_power",
        translation_key="battery_discharge_power",
        stat_type="battery",
        value_index=1,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="battery_grid_charge_power",
        translation_key="battery_grid_charge_power",
        stat_type="battery",
        value_index=2,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Load
    EmaldoSensorDescription(
        key="load_grid_power",
        translation_key="load_grid_power",
        stat_type="load/usage",
        value_index=0,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="load_backup_power",
        translation_key="load_backup_power",
        stat_type="load/usage",
        value_index=1,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Grid
    EmaldoSensorDescription(
        key="grid_export_power",
        translation_key="grid_export_power",
        stat_type="grid",
        value_index=2,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EmaldoSensorDescription(
        key="grid_import_power",
        translation_key="grid_import_power",
        stat_type="grid",
        value_index=4,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EmaldoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Emaldo sensors from a config entry."""
    coordinators = entry.runtime_data

    entities: list[EmaldoSensor] = []
    for coordinator in coordinators:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(EmaldoSensor(coordinator, description))

    async_add_entities(entities)


class EmaldoSensor(CoordinatorEntity[EmaldoCoordinator], SensorEntity):
    """Representation of an Emaldo sensor."""

    entity_description: EmaldoSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EmaldoCoordinator,
        description: EmaldoSensorDescription,
    ) -> None:
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

        stat = data.get(self.entity_description.stat_type)
        if not stat:
            return None

        values = stat.get("values", [])
        idx = self.entity_description.value_index
        scale = self.entity_description.scale

        if idx == -1:
            # Sum all values
            return round(sum(values) * scale, 3)

        if idx >= len(values):
            return None

        return round(values[idx] * scale, 3)
