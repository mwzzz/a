"""FastAPI 入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api import api_router
from app.config import settings
from app.errors import install_error_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.ensure_schema()
    if settings.using_dev_secret:
        logger.warning("JWT_SECRET 仍是开发默认值，生产环境必须在 .env 里替换")
    logger.info("服务启动，数据库 %s", settings.db_path)
    yield


app = FastAPI(
    title=settings.app_name,
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
)

install_error_handlers(app)

if settings.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)


@app.get("/api/health", tags=["运维"])
@app.get("/api/v1/health", tags=["运维"])
def health() -> dict:
    return {
        "ok": True,
        "version": VERSION,
        "db": "ok",
        "sqlite_version": db.sqlite_version(),
    }
