"""Hardware abstraction layer for MCP23S17 and GPIO peripherals.

The code keeps the real SPI interactions behind an interface so that unit
tests can run without Raspberry Pi hardware present. When the platform does
not provide the required libraries the module falls back to an in-memory
simulation that mimics the behaviour of the GPIO expanders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Iterable, List

try:
    import RPi.GPIO as GPIO  # type: ignore
    import spidev  # type: ignore
except ImportError:  # pragma: no cover - running on development host
    GPIO = None
    spidev = None

LOGGER = logging.getLogger(__name__)


GPIOA = 0x12
GPIOB = 0x13
IODIRA = 0x00
IODIRB = 0x01
OLATA = 0x14
OLATB = 0x15
GPPUA = 0x0C
GPPUB = 0x0D
IOCON = 0x0A


RELAY_PIN_MAP = {f"K{i}": i - 1 for i in range(1, 9)}
TRANSISTOR_PIN_MAP = {f"T{i}": i - 1 for i in range(1, 9)}


def channel_to_index(channel: str) -> int:
    if len(channel) != 2 or channel[0] not in {"A", "B"}:
        raise ValueError(f"Unsupported channel reference: {channel}")
    idx = int(channel[1])
    if idx < 0 or idx > 7:
        raise ValueError("Channel index must be 0..7")
    return idx


@dataclass
class GPIOMap:
    relays: Dict[str, List[str]]
    transistors: Dict[str, List[str]]
    relays_active_low: bool
    transistors_active_low: bool


class HardwareInterface:
    """High-level interface used by the control loop."""

    def __init__(self, gpio_map: GPIOMap) -> None:
        self.gpio_map = gpio_map
        self._lock = Lock()
        self._relay_state = {name: False for name in RELAY_PIN_MAP}
        self._transistor_state = {name: False for name in TRANSISTOR_PIN_MAP}
        self._input_state = {f"A{i}": False for i in range(8)}
        self._input_state.update({f"B{i}": False for i in range(8)})
        self._setup()

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------
    def _setup(self) -> None:
        if spidev is None:
            LOGGER.warning("Running MCP23S17 in simulation mode")
            return
        self._bus = spidev.SpiDev()
        self._bus.open(0, 0)
        self._bus.max_speed_hz = 1000000
        # configure IOCON for sequential operations
        self._write_register(IOCON, 0x08)
        self._write_register(IODIRA, 0xFF)
        self._write_register(IODIRB, 0xFF)
        self._write_register(GPPUA, 0xFF)
        self._write_register(GPPUB, 0xFF)

    # ------------------------------------------------------------------
    def set_relays(self, logical_name: str, state: bool) -> None:
        pins = self.gpio_map.relays.get(logical_name, [])
        with self._lock:
            for pin in pins:
                self._relay_state[pin] = state
            self._flush_outputs()

    def set_transistors(self, logical_name: str, state: bool) -> None:
        pins = self.gpio_map.transistors.get(logical_name, [])
        with self._lock:
            for pin in pins:
                self._transistor_state[pin] = state
            self._flush_outputs()

    def set_transistor_channel(self, channel: str, state: bool) -> None:
        if channel not in self._transistor_state:
            raise KeyError(f"Unknown transistor channel {channel}")
        with self._lock:
            self._transistor_state[channel] = state
            self._flush_outputs()

    def has_transistor_channel(self, channel: str) -> bool:
        return channel in self._transistor_state

    def read_inputs(self, channels: Iterable[str]) -> Dict[str, bool]:
        with self._lock:
            return {ch: self._input_state.get(ch, False) for ch in channels}

    def set_input_simulation(self, channel: str, value: bool) -> None:
        with self._lock:
            self._input_state[channel] = value

    # ------------------------------------------------------------------
    def _flush_outputs(self) -> None:
        if spidev is None:
            return
        relay_byte = self._encode_outputs(
            self._relay_state, self.gpio_map.relays_active_low, RELAY_PIN_MAP
        )
        transistor_byte = self._encode_outputs(
            self._transistor_state,
            self.gpio_map.transistors_active_low,
            TRANSISTOR_PIN_MAP,
        )
        self._write_register(OLATA, relay_byte)
        self._write_register(OLATB, transistor_byte)

    def _write_register(self, address: int, value: int) -> None:
        if spidev is None:
            return
        self._bus.xfer2([0x40, address, value])  # 0x40 -> MCP23S17 write

    # ------------------------------------------------------------------
    @staticmethod
    def _encode_outputs(
        mapping: Dict[str, bool], active_low: bool, pin_map: Dict[str, int]
    ) -> int:
        value = 0
        for name, pin in pin_map.items():
            level = mapping.get(name, False)
            if active_low:
                level = not level
            if level:
                value |= 1 << pin
        return value


def build_gpio_map(
    relay_map: Dict[str, List[str]],
    relay_active_low: bool,
    transistor_map: Dict[str, List[str]],
    transistor_active_low: bool,
) -> GPIOMap:
    return GPIOMap(
        relays=relay_map,
        transistors=transistor_map,
        relays_active_low=relay_active_low,
        transistors_active_low=transistor_active_low,
    )
