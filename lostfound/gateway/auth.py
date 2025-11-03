from __future__ import annotations

from fastapi import APIRouter, Request

from packages.common.config import get_settings
from packages.common.schemas.auth import LoginRequest, SignUpRequest

from .proxy import forward_request
from .idempotency import ensure_idempotent

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(payload: SignUpRequest, request: Request):
    settings = get_settings()
    await ensure_idempotent(request, payload.model_dump(mode="json"))
    return await forward_request(
        request,
        base_url=settings.auth_service_url,
        path="/auth/signup",
        json_body=payload,
    )


@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    settings = get_settings()
    return await forward_request(
        request,
        base_url=settings.auth_service_url,
        path="/auth/login",
        json_body=payload,
    )


@router.get("/me")
async def me(request: Request):
    settings = get_settings()
    return await forward_request(request, base_url=settings.auth_service_url, path="/auth/me")
