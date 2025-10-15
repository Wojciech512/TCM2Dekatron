"""Sensor access and graceful fallbacks for the controller."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .state import SensorSnapshot

LOGGER = logging.getLogger(__name__)

_DHT_INIT_ERROR: Optional[str] = None

try:  # pragma: no cover - optional hardware dependency
    import board
    import adafruit_dht
except (ImportError, NotImplementedError, AttributeError, RuntimeError) as exc:  # pragma: no cover - running without hardware
    # AttributeError/RuntimeError cover cases where platform detection fails within
    # the CircuitPython stack (e.g. Blinka raising "Avoid infinite recursion" when
    # GPIO access is unavailable inside a constrained container). Treat those as a
    # missing sensor driver so the application can still start.
    _DHT_INIT_ERROR = str(exc)
    LOGGER.warning("DHT11 driver unavailable: %s", _DHT_INIT_ERROR)
    board = None
    adafruit_dht = None


@dataclass
class SensorReading:
    snapshot: SensorSnapshot
    errors: List[str]


def read_dht11(batt_pin: int, cab_pin: int) -> SensorReading:
    """Read the DHT11 sensor pair. Missing libraries result in None readings."""

    snapshot = SensorSnapshot()
    errors: List[str] = []

    if adafruit_dht is None or board is None:
        if _DHT_INIT_ERROR:
            errors.append(
                "DHT library not available; running without sensor data"
                f" ({_DHT_INIT_ERROR})"
            )
        else:
            errors.append("DHT library not available; running without sensor data")
        return SensorReading(snapshot=snapshot, errors=errors)

    for label, pin in (("batt", batt_pin), ("cab", cab_pin)):
        board_pin_name = f"D{pin}"
        if not hasattr(board, board_pin_name):
            errors.append(f"DHT11 {label} pin D{pin} not available on this board")
            continue

        gpio = getattr(board, board_pin_name)
        sensor = adafruit_dht.DHT11(gpio, use_pulseio=False)
        humidity: Optional[float] = None
        temperature: Optional[float] = None
        last_error: Optional[str] = None

        for _ in range(3):
            try:
                humidity = sensor.humidity
                temperature = sensor.temperature
            except RuntimeError as exc:  # pragma: no cover - transient hardware error
                last_error = str(exc)
                humidity = temperature = None
            if humidity is not None and temperature is not None:
                break
            time.sleep(2.0)

        sensor.exit()

        if humidity is None or temperature is None:
            if last_error:
                errors.append(f"DHT11 {label} read failed: {last_error}")
            else:
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
