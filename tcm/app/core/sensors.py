"""Sensor access and graceful fallbacks for the controller."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .state import SensorSnapshot

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - optional hardware dependency
    import Adafruit_DHT  # type: ignore
except ImportError:  # pragma: no cover
    Adafruit_DHT = None


@dataclass
class SensorReading:
    snapshot: SensorSnapshot
    errors: List[str]


def read_dht11(batt_pin: int, cab_pin: int) -> SensorReading:
    """Read the DHT11 sensor pair. Missing libraries result in None readings."""

    snapshot = SensorSnapshot()
    errors: List[str] = []

    if Adafruit_DHT is None:
        errors.append("DHT library not available; running without sensor data")
        return SensorReading(snapshot=snapshot, errors=errors)

    for label, pin in (("batt", batt_pin), ("cab", cab_pin)):
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, pin)
        if humidity is None or temperature is None:
            errors.append(f"DHT11 {label} read failed")
            continue
        if label == "batt":
            snapshot.hum_batt = float(humidity)
            snapshot.temp_batt = float(temperature)
        else:
            snapshot.hum_cab = float(humidity)
            snapshot.temp_cab = float(temperature)

    return SensorReading(snapshot=snapshot, errors=errors)


def read_ds18b20(bus_path: str, sensor_ids: List[str]) -> Dict[str, Optional[float]]:
    """Return dictionary with DS18B20 temperatures."""

    readings: Dict[str, Optional[float]] = {}
    for sensor_id in sensor_ids:
        device_path = f"{bus_path}/{sensor_id}/w1_slave"
        try:
            with open(device_path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except FileNotFoundError:
            LOGGER.warning("DS18B20 sensor %s not found", sensor_id)
            readings[sensor_id] = None
            continue

        if len(lines) < 2 or "YES" not in lines[0]:
            LOGGER.warning("CRC failure for DS18B20 sensor %s", sensor_id)
            readings[sensor_id] = None
            continue

        marker = "t="
        if marker not in lines[1]:
            readings[sensor_id] = None
            continue
        temp_c = float(lines[1].split(marker)[-1]) / 1000.0
        readings[sensor_id] = temp_c

    return readings
