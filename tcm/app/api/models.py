"""Pydantic models shared across API routers."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel


class SensorModel(BaseModel):
    temp_batt: Optional[float]
    hum_batt: Optional[float]
    temp_cab: Optional[float]
    hum_cab: Optional[float]


class RuntimeStateModel(BaseModel):
    inputs: Dict[str, bool]
    sensors: SensorModel
    outputs: Dict[str, bool]
    alarm_reason: Optional[str]
    buzzer_muted: bool
    strike_active_until: Optional[float]
    last_updated: float
    error: Optional[str]
    manual_mode: bool
    manual_overrides: Dict[str, bool]


class OutputUpdateModel(BaseModel):
    name: str
    state: bool


class ManualModeModel(BaseModel):
    enabled: bool


class StrikeTriggerResponse(BaseModel):
    triggered: bool
    strike: str
    active_until: Optional[float]

