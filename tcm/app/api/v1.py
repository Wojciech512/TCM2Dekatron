"""API v1 routers covering inputs, outputs, sensors and strike."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..core.state import GLOBAL_STATE, LOGICAL_OUTPUTS
from ..security.auth import get_authenticated_user, require_role
from ..services.strike import StrikeService
from .models import (
    ManualModeModel,
    OutputUpdateModel,
    RuntimeStateModel,
    SensorModel,
    StrikeTriggerResponse,
)

limiter: Limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["v1"])


def get_strike_service(request: Request) -> StrikeService:
    """Retrieve the configured StrikeService from the application state."""

    service = getattr(request.app.state, "strike_service", None)
    if not isinstance(service, StrikeService):  # pragma: no cover - defensive guard
        raise RuntimeError("Strike service not initialised")
    return service


@router.get("/inputs")
@limiter.limit("120/minute")
def list_inputs(
    request: Request, user=Depends(get_authenticated_user)
) -> dict:  # noqa: ARG001
    runtime = GLOBAL_STATE.read()
    return runtime.inputs


@router.get("/outputs")
@limiter.limit("120/minute")
def list_outputs(
    request: Request, user=Depends(get_authenticated_user)
) -> dict:  # noqa: ARG001
    runtime = GLOBAL_STATE.read()
    return runtime.outputs


@router.post("/outputs")
@limiter.limit("30/minute")
def set_output(
    request: Request,
    payload: OutputUpdateModel,
    user=Depends(require_role("technik")),
) -> dict:
    state = GLOBAL_STATE.read()
    if payload.name not in LOGICAL_OUTPUTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown output '{payload.name}'",
        )
    overrides = dict(state.manual_overrides)
    overrides[payload.name] = payload.state
    GLOBAL_STATE.update(manual_overrides=overrides, manual_mode=True)
    return overrides


@router.get("/sensors")
@limiter.limit("120/minute")
def get_sensors(
    request: Request, user=Depends(get_authenticated_user)
) -> SensorModel:  # noqa: ARG001
    runtime = GLOBAL_STATE.read()
    return SensorModel(**runtime.sensors.__dict__)


@router.post("/manual-mode")
@limiter.limit("30/minute")
def set_manual_mode(
    request: Request,
    payload: ManualModeModel,
    user=Depends(require_role("technik")),
):
    GLOBAL_STATE.update(manual_mode=payload.enabled)
    return {"manual_mode": payload.enabled}


@router.get("/strike/{strike_id}/trigger", response_model=StrikeTriggerResponse)
@limiter.limit("10/15seconds")
def trigger_strike(
    request: Request,
    strike_id: str,
    service: StrikeService = Depends(get_strike_service),
    user=Depends(require_role("operator")),
):
    outcome = service.trigger(strike_id)
    if not outcome.success:
        if outcome.error == "not_configured":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strike not configured",
            )
        if outcome.error == "transistor_unavailable":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Strike transistor unavailable",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Strike trigger failed",
        )
    runtime = GLOBAL_STATE.read()
    return StrikeTriggerResponse(
        triggered=True, strike=strike_id, active_until=runtime.strike_active_until
    )
