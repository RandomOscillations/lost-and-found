from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from packages.common.schemas.auth import LoginRequest, SignUpRequest, TokenResponse, UserProfile
from .service import AuthService
from .dependencies import get_auth_service, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignUpRequest, service: AuthService = Depends(get_auth_service)) -> UserProfile:
    try:
        user = await service.register_user(payload.email, payload.password, payload.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserProfile(id=str(user.id), email=user.email, display_name=user.display_name, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    try:
        user, token = await service.authenticate(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfile)
async def me(current_user = Depends(get_current_user)) -> UserProfile:  # type: ignore[override]
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
    )
