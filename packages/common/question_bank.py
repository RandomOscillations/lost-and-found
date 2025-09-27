from __future__ import annotations

import json
import pathlib
import random
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from .models import QuestionBank


class QuestionBankService:
    def __init__(self, engine: AsyncEngine, seed_path: pathlib.Path) -> None:
        self._engine = engine
        self._seed_path = seed_path
        self._cache: dict[str, list[str]] = {}

    async def seed_from_file(self) -> None:
        if not self._seed_path.exists():
            return
        data = json.loads(self._seed_path.read_text())
        async with AsyncSession(self._engine) as session:
            for entry in data:
                category = entry.get("category", "other")
                prompt = entry.get("prompt")
                keywords = entry.get("keywords", [])
                if not prompt:
                    continue
                stmt = (
                    insert(QuestionBank)
                    .values(category=category, prompt=prompt, keywords=keywords, active=True)
                    .on_conflict_do_nothing(index_elements=[QuestionBank.prompt])
                )
                await session.execute(stmt)
            await session.commit()

    async def refresh_cache(self) -> None:
        async with AsyncSession(self._engine) as session:
            stmt = select(QuestionBank).where(QuestionBank.active.is_(True))
            result = await session.execute(stmt)
            rows = result.scalars().all()
        cache: dict[str, list[str]] = {}
        for row in rows:
            cache.setdefault(row.category, []).append(row.prompt)
        self._cache = cache

    def get_prompts_for_category(self, category: str, limit: int = 2) -> list[str]:
        prompts = self._cache.get(category) or self._cache.get("other", [])
        if not prompts:
            return []
        if len(prompts) <= limit:
            return list(prompts)
        return random.sample(prompts, k=limit)

    def available_categories(self) -> Sequence[str]:
        return tuple(self._cache.keys())

    async def reload(self) -> None:
        await self.refresh_cache()

    async def warm(self) -> None:
        await self.seed_from_file()
        await self.refresh_cache()
