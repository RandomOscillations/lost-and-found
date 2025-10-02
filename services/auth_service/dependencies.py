from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.common.db import get_db_session
from packages.common.jwt import decode_jwt
from packages.common.models import User
from .service import AuthService

_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


async def get_auth_service(session=Depends(get_db_session)) -> AuthService:
    return AuthService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session=Depends(get_db_session),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = decode_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid subject") from exc

    service = AuthService(session)
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_moderator(user: User = Depends(get_current_user)) -> User:
    if user.role != "moderator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Moderator privileges required")
    return user
