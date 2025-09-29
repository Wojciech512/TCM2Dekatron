"""In-memory runtime state for the controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import time
from typing import Dict, Optional

LOGICAL_OUTPUTS = [
    "alarm",
    "klimatyzacja",
    "oswietlenie",
    "grzalka",
    "went_48v",
    "went_230v",
]


@dataclass
class SensorSnapshot:
    temp_batt: Optional[float] = None
    hum_batt: Optional[float] = None
    temp_cab: Optional[float] = None
    hum_cab: Optional[float] = None


@dataclass
class RuntimeState:
    inputs: Dict[str, bool] = field(default_factory=dict)
    sensors: SensorSnapshot = field(default_factory=SensorSnapshot)
    outputs: Dict[str, bool] = field(
        default_factory=lambda: {name: False for name in LOGICAL_OUTPUTS}
    )
    alarm_reason: Optional[str] = None
    buzzer_muted: bool = False
    strike_active_until: Optional[float] = None
    last_updated: float = field(default_factory=time)
    error: Optional[str] = None
    manual_mode: bool = False
    manual_overrides: Dict[str, bool] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, object]:
        return {
            "inputs": dict(self.inputs),
            "sensors": self.sensors.__dict__,
            "outputs": dict(self.outputs),
            "alarm_reason": self.alarm_reason,
            "buzzer_muted": self.buzzer_muted,
            "strike_active_until": self.strike_active_until,
            "last_updated": self.last_updated,
            "error": self.error,
            "manual_mode": self.manual_mode,
            "manual_overrides": dict(self.manual_overrides),
        }


class StateContainer:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state = RuntimeState()

    def read(self) -> RuntimeState:
        with self._lock:
            return self._snapshot_unlocked()

    def update(self, **kwargs) -> RuntimeState:
        with self._lock:
            for key, value in kwargs.items():
                if key == "inputs":
                    self._state.inputs = dict(value)
                elif key == "sensors" and isinstance(value, SensorSnapshot):
                    self._state.sensors = value
                elif key == "outputs":
                    self._state.outputs.update(value)
                elif key == "manual_overrides":
                    self._state.manual_overrides = dict(value)
                elif hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._state.last_updated = time()
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> RuntimeState:
        """Return a deep copy of the runtime state.

        The caller must hold ``self._lock`` before invoking this helper.  This
        avoids attempting to reacquire the non-reentrant lock inside
        ``update`` while still giving both ``read`` and ``update`` access to a
        fresh copy of the runtime data.
        """

        return RuntimeState(
            inputs=dict(self._state.inputs),
            sensors=SensorSnapshot(**self._state.sensors.__dict__),
            outputs=dict(self._state.outputs),
            alarm_reason=self._state.alarm_reason,
            buzzer_muted=self._state.buzzer_muted,
            strike_active_until=self._state.strike_active_until,
            last_updated=self._state.last_updated,
            error=self._state.error,
            manual_mode=self._state.manual_mode,
            manual_overrides=dict(self._state.manual_overrides),
        )


GLOBAL_STATE = StateContainer()
