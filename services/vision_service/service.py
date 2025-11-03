from __future__ import annotations

import math
import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.models import Item, ItemStatus, ItemType
from packages.common.schemas.item import MatchCandidate, MatchExplanation
from .models import Embedding
import random


class VisionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_matches(self, item_id: uuid.UUID, limit: int = 5) -> list[MatchCandidate]:
        target_stmt = select(Item).where(Item.id == item_id)
        target_result = await self.session.execute(target_stmt)
        target_item = target_result.scalar_one_or_none()
        if not target_item:
            raise LookupError("Item not found")

        if target_item.type == ItemType.FOUND:
            counterpart_type = ItemType.LOST
        else:
            counterpart_type = ItemType.FOUND

        stmt = (
            select(Item)
            .where(
                Item.type == counterpart_type,
                Item.status == ItemStatus.ACTIVE,
                Item.id != target_item.id,
            )
        )
        result = await self.session.execute(stmt)
        candidates = result.scalars().all()

        # If embeddings are present, use vector similarity; otherwise fall back to heuristics
        use_vectors = await self._ensure_embeddings([target_item] + candidates)
        if use_vectors:
            # Query nearest neighbors by cosine distance using pgvector operator <=>
            q = text(
                """
                SELECT e2.item_id AS candidate_id,
                       1 - (e1.vec <=> e2.vec) AS score
                FROM embeddings e1
                JOIN embeddings e2
                  ON e2.modality = e1.modality
                WHERE e1.item_id = :target
                  AND e2.item_id <> :target
                ORDER BY e1.vec <=> e2.vec
                LIMIT :k
                """
            )
            res = await self.session.execute(q, {"target": str(target_item.id), "k": limit})
            rows = res.fetchall()
            by_id = {str(it.id): it for it in candidates}
            out: list[MatchCandidate] = []
            for candidate_id, score in rows:
                cand = by_id.get(str(candidate_id))
                if not cand:
                    continue
                out.append(
                    MatchCandidate(
                        itemId=str(target_item.id),
                        candidateId=str(cand.id),
                        score=round(float(score), 4),
                        explanation=MatchExplanation(tags=list(set(target_item.tags or []).intersection(set(cand.tags or []))), aspects=["vector"]),
                    )
                )
            return out
        else:
            scored: list[tuple[float, Item, MatchExplanation]] = []
            for candidate in candidates:
                score, explanation = self._score_pair(target_item, candidate)
                if score > 0:
                    scored.append((score, candidate, explanation))

            scored.sort(key=lambda item: item[0], reverse=True)
            limited = scored[:limit]
            response: list[MatchCandidate] = []
            for score, candidate, explanation in limited:
                response.append(
                    MatchCandidate(
                        itemId=str(target_item.id),
                        candidateId=str(candidate.id),
                        score=round(score, 4),
                        explanation=explanation,
                    )
                )
            return response

    async def _ensure_embeddings(self, items: list[Item]) -> bool:
        """Seed deterministic embeddings for given items if missing.

        Returns True if embeddings are present/seeded and can be used.
        """
        # Check if table exists and at least one row can be fetched
        try:
            existing = await self.session.execute(select(Embedding.item_id).limit(1))
        except Exception:
            return False

        present_any = existing.first() is not None
        # Seed missing embeddings for provided items (modality='text')
        for it in items:
            got = await self.session.get(Embedding, {"item_id": it.id, "modality": "text"})
            if got:
                continue
            # Deterministic 512-dim pseudo vector seeded by item id + tags
            rnd = random.Random(str(it.id) + "/" + ",".join(it.tags or []))
            vec = [rnd.random() for _ in range(512)]
            self.session.add(Embedding(item_id=it.id, modality="text", vec=vec))
        if items:
            await self.session.flush()
        return True

    def _score_pair(self, left: Item, right: Item) -> tuple[float, MatchExplanation]:
        tags_left = set(left.tags or [])
        tags_right = set(right.tags or [])
        intersect = tags_left.intersection(tags_right)
        union = tags_left.union(tags_right) or {"__placeholder__"}
        tag_score = len(intersect) / len(union)

        category_score = 0.2 if left.category and left.category == right.category else 0.0
        zone_score = 0.1 if left.zone and left.zone == right.zone else 0.0

        time_score = 0.0
        if left.when and right.when:
            delta = abs((left.when - right.when).total_seconds())
            if delta <= 3600:
                time_score = 0.2
            elif delta <= 6 * 3600:
                time_score = 0.1

        description_overlap = self._description_overlap(left.description, right.description)

        score = min(0.99, tag_score * 0.5 + category_score + zone_score + time_score + description_overlap * 0.2)
        explanation = MatchExplanation(tags=list(intersect), aspects=[])
        if category_score:
            explanation.aspects.append("category")
        if zone_score:
            explanation.aspects.append("zone")
        if time_score:
            explanation.aspects.append("time")
        if description_overlap > 0:
            explanation.aspects.append("description")
        return score, explanation

    def _description_overlap(self, left: str, right: str) -> float:
        left_tokens = set(word.lower() for word in left.split())
        right_tokens = set(word.lower() for word in right.split())
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = left_tokens.intersection(right_tokens)
        union = left_tokens.union(right_tokens)
        return len(overlap) / len(union)
