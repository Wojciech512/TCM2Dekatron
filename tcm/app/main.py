"""FastAPI application factory for the TCM controller."""

from __future__ import annotations

import os
import asyncio
import contextlib

from pathlib import Path
from typing import Dict, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from .api import state as state_router
from .api import v1 as v1_router
from .core.config import AppConfig, load_secret_file
from .core.control_loop import ControlLoop
from .core.hardware import HardwareInterface, build_gpio_map
from .core.state import GLOBAL_STATE
from .security.auth import AuthManager, SESSION_USER_KEY, UserSession, get_current_user
from .services.logging import EventLogger
from .services.strike import StrikeService
from .services.users import UserStore

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def load_secret(key: str, file_path: Optional[Path]) -> Optional[str]:
    env_value = os.getenv(key)
    if env_value:
        return env_value
    if file_path:
        return load_secret_file(file_path)
    return None


def create_app(config_path: Path | None = None) -> FastAPI:
    config_path = config_path or Path(__file__).resolve().parents[1] / "config" / "app.yaml"
    config = AppConfig.from_yaml(config_path)

    secret_key = load_secret("TCM_SECRET_KEY", config.secrets.secret_key_file)
    if not secret_key:
        raise RuntimeError("Secret key not provided")

    fernet_key = load_secret("TCM_FERNET_KEY", config.secrets.fernet_key_file)
    admin_hash = load_secret("TCM_ADMIN_HASH", config.secrets.admin_hash_file)

    db_path = Path(os.getenv("TCM_DB_PATH", str(config.logging.sqlite_path)))
    event_logger = EventLogger(db_path, config.logging.encrypted_fields, fernet_key)
    user_store = UserStore(db_path)
    if admin_hash:
        user_store.create_user_with_hash("admin", admin_hash, "serwis")

    app = FastAPI(title="TCM 2.0 Controller", version="2.0.0")
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        https_only=True,
        same_site="strict",
        max_age=60 * 60,
        session_cookie="tcm_session",
    )

    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    gpio_map = build_gpio_map(
        config.outputs.relays.map,
        config.outputs.relays.active_low,
        config.outputs.transistors.map,
        config.outputs.transistors.active_low,
    )
    hardware = HardwareInterface(gpio_map)
    control_loop = ControlLoop(config, hardware, event_logger)
    strike_assignments = {name: value.transistor for name, value in config.strike.assignments.items() if value.transistor}
    strike_service = StrikeService(hardware, event_logger, config.strike.default_duration_seconds, strike_assignments)

    app.state.config = config
    app.state.logger = event_logger
    app.state.user_store = user_store
    app.state.control_loop = control_loop
    app.state.strike_service = strike_service
    app.state.auth_manager = AuthManager(secret_key)
    app.state.templates = templates
    limiter = v1_router.limiter
    app.state.limiter = limiter

    app.include_router(state_router.router)
    app.include_router(v1_router.router)

    @app.on_event("startup")
    async def startup_event() -> None:
        if hasattr(control_loop, "initialize"):
            await control_loop.initialize()
        app.state.control_task = asyncio.create_task(control_loop.start())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        task = getattr(app.state, "control_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if hasattr(control_loop, "stop"):
            await control_loop.stop()

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return templates.TemplateResponse(
            "429.html",
            {"request": request, "detail": "Too many requests"},
            status_code=429,
        )

    # ------------------------------------------------------------------
    # Web views
    # ------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, user: Optional[UserSession] = Depends(get_current_user)):
        if not user:
            csrf = app.state.auth_manager.issue_csrf(request.session)
            return templates.TemplateResponse("login.html", {
                "request": request, "user": None, "config": config, "csrf_token": csrf})
        return RedirectResponse(url="/dashboard")

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        csrf = app.state.auth_manager.issue_csrf(request.session)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": csrf, "user": None, "config": config},
        )

    @app.post("/login")
    async def login_post(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
        if not app.state.auth_manager.verify_csrf(request.session, csrf_token):
            raise HTTPException(status_code=400, detail="Invalid CSRF token")
        role = user_store.verify_credentials(username, password)
        if not role:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        request.session[SESSION_USER_KEY] = {"username": username, "role": role}
        event_logger.log("AUTH", "User login", {"username": username, "role": role})
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.get("/logout")
    async def logout(request: Request):
        user = request.session.get(SESSION_USER_KEY)
        request.session.clear()
        if user:
            event_logger.log("AUTH", "User logout", {"username": user.get("username")})
        return RedirectResponse(url="/login", status_code=302)

    def _panel_context(request: Request) -> Dict[str, object]:
        runtime = GLOBAL_STATE.read()
        return {
            "request": request,
            "state": runtime.snapshot(),
            "config": config,
        }

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request, user: UserSession = Depends(get_current_user)):
        context = _panel_context(request)
        context["user"] = user
        return templates.TemplateResponse("dashboard.html", context)

    @app.get("/panel/operator", response_class=HTMLResponse)
    async def panel_operator(request: Request, user: UserSession = Depends(get_current_user)):
        context = _panel_context(request)
        context["user"] = user
        return templates.TemplateResponse("panel_operator.html", context)

    @app.get("/panel/technik", response_class=HTMLResponse)
    async def panel_technik(request: Request, user: UserSession = Depends(get_current_user)):
        if user.role not in {"technik", "serwis"}:
            raise HTTPException(status_code=403, detail="Insufficient role")
        context = _panel_context(request)
        context["user"] = user
        return templates.TemplateResponse("panel_technik.html", context)

    @app.get("/panel/serwis", response_class=HTMLResponse)
    async def panel_serwis(request: Request, user: UserSession = Depends(get_current_user)):
        if user.role != "serwis":
            raise HTTPException(status_code=403, detail="Insufficient role")
        if config.ui.panels.serwis.require_dip_high:
            runtime = GLOBAL_STATE.read()
            if not runtime.inputs.get("dip_service", False):
                raise HTTPException(status_code=403, detail="Service DIP not enabled")
        context = _panel_context(request)
        context["user"] = user
        return templates.TemplateResponse("panel_serwis.html", context)

    @app.get("/health", include_in_schema=False, response_class=PlainTextResponse)
    @limiter.exempt
    async def health():
        return "OK"

    return app

app = create_app()

