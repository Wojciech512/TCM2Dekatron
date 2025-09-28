"""State endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..core.state import GLOBAL_STATE
from ..security.auth import get_authenticated_user
from .models import RuntimeStateModel, SensorModel

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api", tags=["state"])


@router.get("/state", response_model=RuntimeStateModel)
@limiter.limit("60/minute")
def get_state(user=Depends(get_authenticated_user)) -> RuntimeStateModel:
    runtime = GLOBAL_STATE.read()
    return RuntimeStateModel(
        inputs=runtime.inputs,
        sensors=SensorModel(**runtime.sensors.__dict__),
        outputs=runtime.outputs,
        alarm_reason=runtime.alarm_reason,
        buzzer_muted=runtime.buzzer_muted,
        strike_active_until=runtime.strike_active_until,
        last_updated=runtime.last_updated,
        error=runtime.error,
        manual_mode=runtime.manual_mode,
        manual_overrides=runtime.manual_overrides,
    )

