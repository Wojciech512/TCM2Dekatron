"""API routers for the TCM application."""
from fastapi import APIRouter

from . import state, v1

api_router = APIRouter()
api_router.include_router(state.router, prefix="/state", tags=["state"])
api_router.include_router(v1.router, prefix="/v1", tags=["v1"])

__all__ = ["api_router"]
