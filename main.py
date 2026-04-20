"""Lumi — capa conversacional Techapoli Loyalty (FastAPI)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.runtime import agent_runtime
from app.core.config import settings
from app.core.logging import configure_logging
from app.entrypoints.http.health import router as health_router
from app.entrypoints.webhooks.telegram import router as telegram_router
from app.entrypoints.webhooks.whatsapp import router as whatsapp_router
from app.infrastructure.loyalty_api.auth_manager import LoyaltyAuthManager
from app.infrastructure.loyalty_api.http_client import build_http_client
from app.shared.exceptions import LoyaltyAgentError

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.loyalty_auth = LoyaltyAuthManager(client_factory=build_http_client)
    async with agent_runtime() as runtime:
        app.state.agent_runtime = runtime
        logger.info("loyalty agent ready on %s:%s", settings.api_host, settings.api_port)
        yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(whatsapp_router)


@app.exception_handler(LoyaltyAgentError)
async def agent_error_handler(request: Request, exc: LoyaltyAgentError):
    logger.warning("agent error: %s", exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
