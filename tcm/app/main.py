"""FastAPI application entry point."""
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api import api_router
from .rate_limit import limiter

app = FastAPI(title="TCM API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(api_router, prefix="/api")


@app.get("/ping")
async def ping() -> dict[str, str]:
    """Simple ping endpoint to verify the service is alive."""
    return {"status": "ok"}
