"""Endpoints exposing overall application state."""
from fastapi import APIRouter, Depends, Request

from ..dependencies import get_manual_overrides, get_runtime_state
from ..rate_limit import limiter

router = APIRouter()


@router.get("", name="get_state")
@limiter.limit("10/second")
async def get_state(
    request: Request,
    runtime_state=Depends(get_runtime_state),
    manual_overrides=Depends(get_manual_overrides),
):
    """Return a combined snapshot of the runtime state and manual overrides."""
    return {
        "runtime": runtime_state,
        "manual": manual_overrides,
    }
