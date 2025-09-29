"""FastAPI application factory for the TCM controller."""
# Konfiguracja narzędzi formatowania i lintowania znajduje się w plikach konfiguracyjnych projektu.
# TODO napisać testy jednostkowe
# TODO jakie zabezpieczenia/funkcjonalności stosuje się do aplikacji na rasberry pi które mają bardzo długo działać bez aktualizacji
# TODO czy przechowywanie sekretów w formie pliku tekstowego to dobry pomysł?
# TODO naprawić pobieranie logów w pdf
from __future__ import annotations

import os
import asyncio
import contextlib
import logging
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from fpdf import FPDF
from fontTools.ttLib import TTLibError

from .api import state as state_router
from .api import v1 as v1_router
from .core.config import AppConfig, load_secret_file
from .core.control_loop import ControlLoop
from .core.hardware import HardwareInterface, build_gpio_map
from .core.state import GLOBAL_STATE
from .security.auth import AuthManager, SESSION_USER_KEY, UserSession, get_current_user
from .services.logging import EVENT_TYPES, EventLogger
from .services.strike import StrikeService
from .services.users import UserStore

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

logger = logging.getLogger(__name__)


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

    def _int_from_env(var_name: str, fallback: int) -> int:
        raw = os.getenv(var_name)
        if not raw:
            return fallback
        try:
            value = int(raw)
        except ValueError:
            return fallback
        return value if value > 0 else fallback

    logs_page_size = _int_from_env("TCM_LOGS_PAGE_SIZE", config.logging.page_size)
    logs_max_records = _int_from_env("TCM_LOGS_MAX_RECORDS", config.logging.max_records)

    event_logger = EventLogger(
        db_path,
        config.logging.encrypted_fields,
        fernet_key,
        max_records=logs_max_records,
    )
    user_store = UserStore(db_path)
    if admin_hash:
        user_store.create_user_with_hash("admin", admin_hash, "serwis")

    try:
        tz_name = config.metadata.timezone if config and config.metadata else None
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except ZoneInfoNotFoundError:
        tz = timezone.utc

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
    app.state.logs_page_size = logs_page_size
    app.state.logs_timezone = tz

    app.include_router(state_router.router)
    app.include_router(v1_router.router)

    TOAST_SESSION_KEY = "_toast_message"

    def _store_toast(request: Request, message: str, level: str = "error", duration: int = 4000) -> None:
        request.session[TOAST_SESSION_KEY] = {
            "message": message,
            "type": level,
            "duration": duration,
        }

    def _pop_toast(request: Request):
        toast = request.session.get(TOAST_SESSION_KEY)
        if toast:
            request.session.pop(TOAST_SESSION_KEY, None)
        return toast

    def _localize_detail(status_code: int, detail: str | None) -> str:
        if detail:
            mapping = {
                "Invalid credentials": "Nieprawidłowa nazwa użytkownika lub hasło.",
                "Insufficient role": "Brak uprawnień do tej sekcji.",
                "Insufficient privileges": "Brak wymaganych uprawnień.",
                "Service DIP not enabled": "Aktywuj przełącznik serwisowy, aby otworzyć ten panel.",
            }
            if detail in mapping:
                return mapping[detail]
        defaults = {
            401: "Aby kontynuować, zaloguj się ponownie.",
            403: "Brak dostępu do żądanej sekcji.",
        }
        if detail and detail not in {"Unauthorized", "Forbidden"}:
            return detail
        return defaults.get(status_code, "Wystąpił błąd.")

    @app.on_event("startup")
    async def startup_event() -> None:
        if hasattr(control_loop, "initialize"):
            await control_loop.initialize()
        app.state.control_task = asyncio.create_task(control_loop.start())
        event_logger.log(
            "CFG",
            "System startup",
            {
                "fast_tick": config.loops.fast_tick_seconds,
                "logic_tick": config.loops.logic_tick_seconds,
            },
        )

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        task = getattr(app.state, "control_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if hasattr(control_loop, "stop"):
            await control_loop.stop()
        event_logger.log("CFG", "System shutdown", {})

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return templates.TemplateResponse(
            "429.html",
            {"request": request, "detail": "Too many requests", "toast": _pop_toast(request)},
            status_code=429,
        )

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        accept_header = request.headers.get("accept", "")
        expects_html = "text/html" in accept_header or "*/*" in accept_header
        if expects_html and exc.status_code in {401, 403}:
            user = get_current_user(request)
            message = _localize_detail(exc.status_code, exc.detail if isinstance(exc.detail, str) else None)
            _store_toast(request, message, level="error")
            target = request.url_for("login_get") if not user else request.url_for("dashboard")
            return RedirectResponse(url=target, status_code=303)
        return await fastapi_http_exception_handler(request, exc)

    # ------------------------------------------------------------------
    # Web views
    # ------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, user: Optional[UserSession] = Depends(get_current_user)):
        if not user:
            csrf = app.state.auth_manager.issue_csrf(request.session)
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "user": None,
                    "config": config,
                    "csrf_token": csrf,
                    "toast": _pop_toast(request),
                },
            )
        return RedirectResponse(url="/dashboard")

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        csrf = app.state.auth_manager.issue_csrf(request.session)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "csrf_token": csrf,
                "user": None,
                "config": config,
                "toast": _pop_toast(request),
            },
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
        # TODO do ustawienia przez zmienne środowiskowe?
        return {
            "request": request,
            "state": runtime.snapshot(),
            "config": config,
            "door_channels": [],
            "relay_channels": [],
            "sensor_channels": [],
            "toast": _pop_toast(request),
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

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_view(
        request: Request,
        user: UserSession = Depends(get_current_user),
        page: int = Query(1, ge=1),
        event_type: Optional[str] = Query(None),
    ):
        if user.role not in {"technik", "serwis"}:
            raise HTTPException(status_code=403, detail="Insufficient privileges")

        if event_type and event_type not in EVENT_TYPES:
            raise HTTPException(status_code=400, detail="Unknown event type")

        per_page: int = getattr(app.state, "logs_page_size", 10)
        total_events = event_logger.count_events(event_type=event_type)
        total_pages = max(1, math.ceil(total_events / per_page)) if total_events else 1
        page = min(page, total_pages)
        offset = (page - 1) * per_page
        records = event_logger.list_events(limit=per_page, offset=offset, event_type=event_type)
        tzinfo = getattr(app.state, "logs_timezone", timezone.utc)

        def _format_payload(payload: Dict[str, object]) -> List[Dict[str, str]]:
            items: List[Dict[str, str]] = []
            for key, value in payload.items():
                items.append({"key": str(key), "value": str(value)})
            return items

        events = [
            {
                "ts": datetime.fromtimestamp(record.ts, tzinfo).strftime("%Y-%m-%d %H:%M:%S"),
                "type": record.type,
                "message": record.message,
                "payload_items": _format_payload(record.payload),
            }
            for record in records
        ]

        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total_events,
            "pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }

        context = {
            "request": request,
            "user": user,
            "config": config,
            "events": events,
            "pagination": pagination,
            "selected_type": event_type,
            "event_types": sorted(EVENT_TYPES),
            "toast": _pop_toast(request),
        }

        return templates.TemplateResponse("logs.html", context)

    @app.get("/logs/export/pdf")
    async def logs_export_pdf(
        request: Request,
        user: UserSession = Depends(get_current_user),
        event_type: Optional[str] = Query(None),
    ):
        if user.role not in {"technik", "serwis"}:
            raise HTTPException(status_code=403, detail="Insufficient privileges")

        if event_type and event_type not in EVENT_TYPES:
            raise HTTPException(status_code=400, detail="Unknown event type")

        tzinfo = getattr(app.state, "logs_timezone", timezone.utc)
        font_path = STATIC_DIR / "fonts" / "DejaVuSansCondensed.ttf"
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        font_name = "Helvetica"
        if font_path.exists():
            try:
                pdf.add_font("DejaVu", "", str(font_path), uni=True)
                pdf.add_font("DejaVu", "B", str(font_path), uni=True)
                font_name = "DejaVu"
            except (RuntimeError, OSError, TTLibError) as exc:
                logger.warning(
                    "Failed to load unicode font from %s: %s. Falling back to Helvetica.",
                    font_path,
                    exc,
                )

        pdf.add_page()
        pdf.set_font(font_name, "B", 14)
        pdf.cell(0, 10, "Dziennik zdarzeń TCM", ln=1)
        pdf.set_font(font_name, "", 10)
        pdf.cell(0, 8, f"Wygenerowano: {datetime.now(tzinfo).strftime('%Y-%m-%d %H:%M:%S')}", ln=1)
        if event_type:
            pdf.cell(0, 8, f"Filtr typu: {event_type}", ln=1)
        pdf.ln(2)
        pdf.set_font(font_name, "B", 10)
        pdf.cell(40, 8, "Data", border=0)
        pdf.cell(25, 8, "Typ", border=0)
        pdf.cell(0, 8, "Szczegóły", ln=1)
        pdf.set_font(font_name, "", 10)

        for record in event_logger.iter_events(
            chunk_size=config.logging.export_chunk_size,
            event_type=event_type,
            order="asc",
        ):
            timestamp = datetime.fromtimestamp(record.ts, tzinfo).strftime("%Y-%m-%d %H:%M:%S")
            payload_text = ", ".join(f"{key}: {value}" for key, value in record.payload.items())
            message_line = record.message
            if payload_text:
                message_line = f"{message_line} ({payload_text})"
            pdf.cell(40, 6, timestamp)
            pdf.cell(25, 6, record.type)
            pdf.multi_cell(0, 6, message_line)

        pdf_bytes = pdf.output(dest="S").encode("latin1")
        filename = f"tcm_logs_{datetime.now(tzinfo).strftime('%Y%m%d_%H%M%S')}.pdf"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

    @app.get("/health", include_in_schema=False, response_class=PlainTextResponse)
    @limiter.exempt
    async def health():
        return "OK"

    return app

app = create_app()

