"""XenoPulse API entrypoint.

An AI-native retail analytics service. All data served is SYNTHETIC.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .catalog import load_catalog
from .config import get_settings
from .db import close_pools, open_pools
from .routers import (
    ai,
    customers,
    dashboard,
    data_quality,
    meta,
    performance,
    recommendations,
    session,
    workspace,
)
from . import session as session_svc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("xenopulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pools()
    n = len(load_catalog())
    try:
        session_svc.ensure_tables()
        session_svc.prune_expired()
    except Exception:  # noqa: BLE001 - don't block startup on the session tables
        log.exception("session table setup failed")
    log.info("XenoPulse %s started. %d catalog queries loaded. AI=%s",
             __version__, n, get_settings().ai_enabled)
    try:
        yield
    finally:
        close_pools()


app = FastAPI(
    title="XenoPulse API",
    version=__version__,
    description=(
        "AI-native retail analytics. Synthetic data only. "
        "User-supplied SQL is validated and executed read-only."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,          # required for the session cookie to cross origins in dev
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):  # noqa: ANN001
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": f"{type(exc).__name__}: {exc}"},
    )


API = "/api"
for r in (meta, dashboard, workspace, performance, customers, ai,
          data_quality, recommendations, session):
    app.include_router(r.router, prefix=API)


@app.get("/")
def root() -> dict:
    return {
        "name": "XenoPulse API",
        "version": __version__,
        "docs": "/docs",
        "health": f"{API}/health",
        "data": "All data is synthetic.",
    }
