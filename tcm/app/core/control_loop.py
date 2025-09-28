"""Asynchronous control loop supervising inputs, sensors and outputs."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from .config import AppConfig
from .hardware import HardwareInterface
from .sensors import read_dht11, read_ds18b20
from .state import GLOBAL_STATE, SensorSnapshot
from ..services.logging import EventLogger

LOGGER = logging.getLogger(__name__)


@dataclass
class StrikeConfig:
    transistor: Optional[str]
    duration_seconds: float


class ControlLoop:
    def __init__(self, config: AppConfig, hardware: HardwareInterface, logger: EventLogger) -> None:
        self.config = config
        self.hardware = hardware
        self.logger = logger
        self._fast_task: Optional[asyncio.Task] = None
        self._logic_task: Optional[asyncio.Task] = None
        self._running = False
        self._door_state: Dict[str, bool] = {}
        self._flood_state: Dict[str, bool] = {}
        self._door_pending: Dict[str, Tuple[bool, float]] = {}
        self._flood_last_change: Dict[str, float] = {}
        current_state = GLOBAL_STATE.read()
        self._output_keys = list(current_state.outputs.keys())
        self._last_output_state: Dict[str, bool] = {key: current_state.outputs[key] for key in self._output_keys}
        self._strike_until: Optional[float] = None

    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._fast_task = asyncio.create_task(self._fast_loop())
        self._logic_task = asyncio.create_task(self._logic_loop())
        LOGGER.info("Control loop started")

    async def stop(self) -> None:
        self._running = False
        for task in (self._fast_task, self._logic_task):
            if task:
                task.cancel()
        await asyncio.sleep(0)

    # ------------------------------------------------------------------
    async def _fast_loop(self) -> None:
        interval = self.config.loops.fast_tick_seconds
        door_channels = self.config.inputs.door_channels
        flood_channels = self.config.inputs.flood_channels
        while self._running:
            try:
                await self._read_inputs(door_channels, flood_channels)
            except Exception as exc:  # pragma: no cover - defensive programming
                LOGGER.exception("Fast loop failure: %s", exc)
            await asyncio.sleep(interval)

    async def _logic_loop(self) -> None:
        interval = self.config.loops.logic_tick_seconds
        while self._running:
            try:
                await self._evaluate_logic()
            except Exception as exc:  # pragma: no cover - defensive programming
                LOGGER.exception("Logic loop failure: %s", exc)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    async def _read_inputs(self, door_channels: Iterable[str], flood_channels: Iterable[str]) -> None:
        states = self.hardware.read_inputs([*door_channels, *flood_channels])
        door_open_is_high = self.config.inputs.polarities.door_open_is_high
        flood_active_is_low = self.config.inputs.polarities.flood_active_is_low
        door_events = {}
        flood_events = {}
        now = time.time()
        debounce_threshold = self.config.inputs.anti_glitch_ms / 1000.0
        anti_flap = self.config.inputs.anti_flap_seconds

        for channel in door_channels:
            raw_state = states.get(channel, False)
            door_open = raw_state if door_open_is_high else not raw_state
            prev = self._door_state.get(channel)
            pending = self._door_pending.get(channel)
            if pending and pending[0] == door_open:
                if now - pending[1] >= debounce_threshold:
                    if prev != door_open:
                        self.logger.log("INPUT", "Door state changed", {"channel": channel, "open": door_open})
                    self._door_state[channel] = door_open
                    self._door_pending.pop(channel, None)
            elif prev != door_open:
                self._door_pending[channel] = (door_open, now)
            door_events[channel] = self._door_state.get(channel, False)

        for channel in flood_channels:
            raw_state = states.get(channel, False)
            flooded = not raw_state if flood_active_is_low else raw_state
            prev = self._flood_state.get(channel)
            last_change = self._flood_last_change.get(channel, 0.0)
            if prev != flooded and (now - last_change) >= anti_flap:
                self.logger.log("INPUT", "Flood state changed", {"channel": channel, "flood": flooded})
                self._flood_state[channel] = flooded
                self._flood_last_change[channel] = now
            flood_events[channel] = self._flood_state.get(channel, False)

        GLOBAL_STATE.update(inputs={**door_events, **flood_events})

    # ------------------------------------------------------------------
    async def _evaluate_logic(self) -> None:
        state = GLOBAL_STATE.read()
        manual_mode = state.manual_mode
        outputs = dict(state.outputs)
        alarm_reason: Optional[str] = None

        sensor_snapshot = await self._read_sensors()
        GLOBAL_STATE.update(sensors=sensor_snapshot)

        doors_open = any(self._door_state.values())
        flood_active = any(self._flood_state.values())

        if manual_mode:
            outputs.update(state.manual_overrides)
            alarm_reason = state.alarm_reason
        else:
            outputs = self._automatic_logic(sensor_snapshot, doors_open, flood_active)
            if doors_open:
                alarm_reason = "door_open"
            elif flood_active:
                alarm_reason = "flood"
            elif any(outputs.get(name, False) for name in ("went_48v", "went_230v")):
                alarm_reason = "overheat"
            else:
                alarm_reason = None

        self._apply_outputs(outputs)
        GLOBAL_STATE.update(outputs=outputs, alarm_reason=alarm_reason)

    # ------------------------------------------------------------------
    async def _read_sensors(self) -> SensorSnapshot:
        if not self.config.sensors.dht11.enabled:
            return SensorSnapshot()

        reading = read_dht11(self.config.sensors.dht11.battery_pin, self.config.sensors.dht11.cabinet_pin)
        for error in reading.errors:
            self.logger.log("SENSOR", error, {})
        snapshot = reading.snapshot
        if self.config.sensors.ds18b20.enabled:
            ds_data = read_ds18b20(str(self.config.sensors.ds18b20.bus_path), self.config.sensors.ds18b20.ids)
            for sensor_id, value in ds_data.items():
                field_name = f"ds18b20_{sensor_id}"
                self.logger.log("SENSOR", "DS18B20 reading", {"sensor": sensor_id, "value": value})
        return snapshot

    def _automatic_logic(self, sensors: SensorSnapshot, doors_open: bool, flood_active: bool) -> Dict[str, bool]:
        outputs = {name: False for name in self._output_keys}
        thresholds = self.config.thresholds

        if doors_open:
            outputs.update({"alarm": True, "oswietlenie": True})
            return outputs

        if flood_active:
            outputs["alarm"] = True
            return outputs

        temp_batt = sensors.temp_batt
        temp_cab = sensors.temp_cab

        if temp_batt is None and temp_cab is None:
            self.logger.log("SENSOR", "Missing temperature data - entering safe mode", {})
            return outputs

        temperature = max(filter(lambda x: x is not None, [temp_batt, temp_cab])) if any(
            t is not None for t in [temp_batt, temp_cab]
        ) else None

        if temperature is None:
            return outputs

        hysteresis = thresholds.histereza_c
        if temperature <= thresholds.grzalka_c - hysteresis:
            outputs["grzalka"] = True
        elif temperature >= thresholds.grzalka_c + hysteresis:
            outputs["grzalka"] = False

        if temperature >= thresholds.klimatyzacja_c + hysteresis:
            outputs["klimatyzacja"] = True
        elif temperature <= thresholds.klimatyzacja_c - hysteresis:
            outputs["klimatyzacja"] = False

        if temperature >= thresholds.went_c:
            outputs["went_48v"] = True
            outputs["went_230v"] = True

        return outputs

    def _apply_outputs(self, outputs: Dict[str, bool]) -> None:
        for name, state in outputs.items():
            previous = self._last_output_state.get(name)
            if previous == state:
                continue
            if name in self.hardware.gpio_map.transistors:
                self.hardware.set_transistors(name, state)
            else:
                self.hardware.set_relays(name, state)
            self.logger.log("OUTPUT", "Output state changed", {"name": name, "state": state})
            self._last_output_state[name] = state

