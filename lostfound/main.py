from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.db import AsyncSessionLocal, async_engine
from .core.events import bus
from .models import Base
from .schemas.common import APIMessage
from .services.auth.router import router as auth_router
from .services.claims.router import router as claims_router
from .services.claims.question_bank import QuestionBankService
from .services.intake.router import router as intake_router
from .services.notify import service as notify_service
from .services.vision.router import router as vision_router
from .services.vision.service import VisionService

settings = get_settings()
logger = logging.getLogger("lostfound")


async def _handle_item_created(payload: dict) -> None:
    item_id = payload.get("itemId")
    if not item_id:
        return
    try:
        item_uuid = uuid.UUID(item_id)
    except ValueError:
        logger.warning("Invalid itemId received in items.created event: %s", item_id)
        return
    async with AsyncSessionLocal() as session:
        vision = VisionService(session)
        matches = await vision.get_matches(item_uuid, limit=settings.default_match_limit)
    if matches:
        await bus.publish(
            "vision.matches.updated",
            {"itemId": item_id, "k": len(matches)},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    question_bank = QuestionBankService(async_engine, settings.question_bank_seed_path)
    await question_bank.warm()
    app.state.question_bank = question_bank

    bus.subscribe("items.created", _handle_item_created)
    bus.subscribe("claims.updated", notify_service.handle_claim_updated)
    bus.subscribe("vision.matches.updated", notify_service.handle_match_event)

    yield


app = FastAPI(
    title="Lost&Found Vision API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/healthz", response_class=JSONResponse)
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(intake_router)
app.include_router(vision_router)
app.include_router(claims_router)


@app.get("/readyz", response_model=APIMessage)
async def ready() -> APIMessage:
    return APIMessage(message="ready")
