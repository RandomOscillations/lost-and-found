from __future__ import annotations

from fastapi import APIRouter, Request

from packages.common.config import get_settings

from .proxy import forward_request

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(request: Request):
    settings = get_settings()
    return await forward_request(request, base_url=settings.auth_service_url, path="/auth/signup")


@router.post("/login")
async def login(request: Request):
    settings = get_settings()
    return await forward_request(request, base_url=settings.auth_service_url, path="/auth/login")


@router.get("/me")
async def me(request: Request):
    settings = get_settings()
    return await forward_request(request, base_url=settings.auth_service_url, path="/auth/me")
