import logging
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pythonjsonlogger.json import JsonFormatter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from sentinel_common.config import Settings


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw_id = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = UUID(raw_id) if raw_id else uuid4()
        except ValueError:
            correlation_id = uuid4()
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(correlation_id)
        response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
        return response


class CookieCSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self._cookie_name = settings.session_cookie_name
        self._allowed_origins = {str(item).rstrip("/") for item in settings.cors_origins}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and self._cookie_name in request.cookies
        ):
            origin = request.headers.get("origin")
            if origin:
                candidate = origin.rstrip("/")
            else:
                referer = request.headers.get("referer")
                parsed = urlparse(referer) if referer else None
                candidate = f"{parsed.scheme}://{parsed.netloc}" if parsed and parsed.netloc else ""
            if candidate not in self._allowed_origins:
                return JSONResponse(
                    {"detail": "Cross-site request rejected"},
                    status_code=403,
                )
        return await call_next(request)


def create_app(settings: Settings, engine: AsyncEngine) -> FastAPI:
    configure_logging(settings)
    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(CookieCSRFMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "X-Correlation-ID",
        ],
    )

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> JSONResponse:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return JSONResponse({"status": "ready"})
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    @app.get("/version", tags=["health"])
    async def version() -> dict[str, str]:
        return {
            "service": settings.service_name,
            "version": settings.service_version,
            "environment": settings.environment,
        }

    return app
