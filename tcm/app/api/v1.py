"""Version 1 of the public API."""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import (
    get_available_strikes,
    get_manual_overrides,
    get_runtime_state,
    get_sensor_data,
)
from ..rate_limit import limiter

router = APIRouter()


@router.get("/inputs")
@limiter.limit("5/second")
async def list_inputs(request: Request, runtime_state=Depends(get_runtime_state)):
    """Return the current logical inputs."""
    return runtime_state.get("inputs", {})


@router.get("/outputs")
@limiter.limit("5/second")
async def list_outputs(request: Request, runtime_state=Depends(get_runtime_state)):
    """Return the current logical outputs."""
    return runtime_state.get("outputs", {})


@router.post("/outputs/{name}")
@limiter.limit("5/second")
async def set_output(
    request: Request,
    name: str,
    enabled: bool,
    runtime_state=Depends(get_runtime_state),
):
    """Set a logical output to the requested state."""
    runtime_state.setdefault("outputs", {})[name] = enabled
    return {"name": name, "enabled": enabled}


@router.get("/sensors")
@limiter.limit("5/second")
async def get_sensors(request: Request, sensors=Depends(get_sensor_data)):
    """Return cached sensor readings."""
    return sensors


@router.post("/manual")
@limiter.limit("5/second")
async def set_manual_mode(
    request: Request,
    enabled: bool,
    manual_overrides=Depends(get_manual_overrides),
):
    """Enable or disable manual mode."""
    manual_overrides["enabled"] = enabled
    return manual_overrides


@router.post("/strikes/{strike_id}")
@limiter.limit("5/second")
async def trigger_strike(
    request: Request,
    strike_id: str,
    strikes=Depends(get_available_strikes),
):
    """Trigger a configured strike if it exists."""
    strike = strikes.get(strike_id)
    if not strike:
        raise HTTPException(status_code=404, detail="Unknown strike")
    return {"strike": strike_id, "status": "triggered", "meta": strike}
