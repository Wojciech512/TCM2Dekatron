"""Shared dependency utilities for the API."""
from functools import lru_cache


class RuntimeState(dict):
    """A simplistic runtime state container."""


@lru_cache
def get_runtime_state() -> RuntimeState:
    """Return a cached runtime state object."""
    return RuntimeState(inputs={"door1": False, "door2": True}, outputs={"fan": False})


@lru_cache
def get_manual_overrides() -> dict:
    """Return manual override configuration."""
    return {"enabled": False, "outputs": {"fan": False}}


@lru_cache
def get_sensor_data() -> dict:
    """Return cached sensor readings."""
    return {"temperature": 21.5, "humidity": 45.0}


@lru_cache
def get_available_strikes() -> dict:
    """Return static strike mapping used by the API."""
    return {"strike_1": {"transistor": "T2"}}
