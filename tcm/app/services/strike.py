"""Strike triggering service controlling door releases."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional

from threading import Thread

from ..core.hardware import HardwareInterface
from ..core.state import GLOBAL_STATE
from .logging import EventLogger


@dataclass
class StrikeDefinition:
    name: str
    transistor: Optional[str]


class StrikeService:
    def __init__(self, hardware: HardwareInterface, logger: EventLogger,
                 default_duration: float, assignments: Dict[str, Optional[str]]) -> None:
        self.hardware = hardware
        self.logger = logger
        self.default_duration = default_duration
        self.assignments = assignments

    def trigger(self, strike_id: str, duration: Optional[float] = None) -> bool:
        transistor = self.assignments.get(strike_id)
        if transistor is None:
            return False
        duration = duration or self.default_duration

        def worker() -> None:
            try:
                self.hardware.set_transistor_channel(transistor, False)
                self.hardware.set_transistor_channel(transistor, True)
            except KeyError:
                self.logger.log("STRIKE", "Strike transistor unavailable", {"strike": strike_id})
                return
            GLOBAL_STATE.update(strike_active_until=time.time() + duration)
            self.logger.log(
                "STRIKE",
                "Strike triggered",
                {"strike": strike_id, "transistor": transistor, "duration": duration},
            )
            time.sleep(duration)
            self.hardware.set_transistor_channel(transistor, False)
            GLOBAL_STATE.update(strike_active_until=None)
            self.logger.log("STRIKE", "Strike released", {"strike": strike_id})

        Thread(target=worker, daemon=True).start()
        return True

