from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.routes.active_learning import router as active_learning_router
from app.api.routes.corrections import router as corrections_router
from app.api.routes.data_controls import router as data_controls_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.identity import router as identity_router
from app.api.routes.learning import router as learning_router
from app.api.routes.lifecycle import router as lifecycle_router
from app.api.routes.memory import router as memory_router
from app.api.routes.memory_runs import router as memory_runs_router
from app.api.routes.privacy import router as privacy_router
from app.api.routes.providers import router as providers_router
from app.api.routes.system import router as system_router
from app.api.routes.uploads import router as uploads_router
from app.core.config import settings
from app.core.db import init_db
from app.middleware import RequestIDMiddleware
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(system_router)
app.include_router(uploads_router)
app.include_router(identity_router)
app.include_router(memory_router)
app.include_router(learning_router)
app.include_router(privacy_router)
app.include_router(providers_router)
app.include_router(lifecycle_router)
app.include_router(corrections_router)
app.include_router(active_learning_router)
app.include_router(memory_runs_router)
app.include_router(data_controls_router)
app.include_router(evaluation_router)
