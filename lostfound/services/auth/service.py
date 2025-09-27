from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core import security
from ...core.jwt import encode_jwt
from ...models import User, UserRole


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register_user(self, email: str, password: str, display_name: str | None = None) -> User:
        hashed = security.hash_password(password)
        user = User(email=email.lower(), password_hash=hashed, display_name=display_name)
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ValueError("Email already registered") from exc
        return user

    async def authenticate(self, email: str, password: str) -> tuple[User, str]:
        stmt = select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not security.verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        token = encode_jwt(str(user.id), {"role": user.role})
        return user, token

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def ensure_moderator(self, user: User) -> None:
        if user.role != UserRole.MODERATOR:
            raise PermissionError("Moderator privileges required")
