from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Iterable, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.events import bus
from packages.common.models import (
    AnswerSource,
    Claim,
    ClaimAnswer,
    ClaimStatus,
    ClaimThread,
    Item,
    ItemPrompt,
    ItemStatus,
    ItemType,
    PromptSource,
    ThreadMessage,
)
from packages.common.schemas.claim import ClaimAnswerInput


class ClaimsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def open_claim(
        self,
        *,
        lost_item_id: uuid.UUID,
        candidate_item_id: uuid.UUID,
        claimant_id: uuid.UUID,
        answers: Sequence[ClaimAnswerInput],
    ) -> Claim:
        lost_item = await self._get_item(lost_item_id)
        candidate_item = await self._get_item(candidate_item_id)

        if lost_item.type != ItemType.LOST:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="itemId must be a lost item")
        if candidate_item.type != ItemType.FOUND:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidateId must refer to a found item",
            )
        if lost_item.owner_id != claimant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only claim your own lost item")
        if candidate_item.status != ItemStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Candidate is not available")

        prompts = await self._get_prompts(candidate_item_id)
        curated = [p for p in prompts if p.source == PromptSource.CURATED]
        custom = [p for p in prompts if p.source == PromptSource.CUSTOM]

        answers_by_question = {answer.question.strip(): answer.answer.strip() for answer in answers}
        missing_questions: list[str] = []
        required_prompts = curated[:2] if len(curated) >= 2 else curated
        for prompt in required_prompts + custom:
            if prompt.prompt.strip() not in answers_by_question or not answers_by_question[prompt.prompt.strip()]:
                missing_questions.append(prompt.prompt)
        if missing_questions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"missingAnswers": missing_questions},
            )

        if not candidate_item.finder_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate has no finder assigned",
            )

        claim = Claim(
            item_id=lost_item.id,
            candidate_id=candidate_item.id,
            claimant_id=claimant_id,
            finder_id=candidate_item.finder_id,
            status=ClaimStatus.PENDING,
        )
        self.session.add(claim)
        await self.session.flush()

        ordered_prompts = required_prompts + custom
        for position, prompt in enumerate(ordered_prompts):
            question_text = prompt.prompt.strip()
            answer_text = answers_by_question.get(question_text, "")
            answer = ClaimAnswer(
                claim_id=claim.id,
                question=question_text,
                answer=answer_text,
                source=AnswerSource.CURATED if prompt.source == PromptSource.CURATED else AnswerSource.CUSTOM,
                position=position,
            )
            self.session.add(answer)

        thread = ClaimThread(claim_id=claim.id)
        self.session.add(thread)

        await self.session.flush()
        await bus.publish(
            "claims.opened",
            {
                "claimId": str(claim.id),
                "itemId": str(claim.item_id),
                "candidateId": str(claim.candidate_id),
            },
        )
        return claim

    async def get_claim(self, claim_id: uuid.UUID) -> Claim:
        stmt = select(Claim).where(Claim.id == claim_id)
        result = await self.session.execute(stmt)
        claim = result.scalar_one_or_none()
        if not claim:
            raise NoResultFound
        return claim

    async def update_status(
        self,
        claim_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
    ) -> Claim:
        claim = await self.get_claim(claim_id)
        is_finder = claim.finder_id == actor_id
        if not is_finder:
            actor = await self._get_user(actor_id)
            if actor.role != "moderator":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

        if action == "verify":
            claim.status = ClaimStatus.VERIFIED
            await self._set_item_statuses(claim, ItemStatus.CLAIMED)
        elif action == "reject":
            claim.status = ClaimStatus.REJECTED
        elif action == "close":
            claim.status = ClaimStatus.CLOSED
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported action")

        await self.session.flush()
        await bus.publish(
            "claims.updated",
            {"claimId": str(claim.id), "status": claim.status},
        )
        return claim

    async def list_messages(
        self,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> tuple[list[ThreadMessage], int]:
        await self._ensure_can_view_thread(thread_id, user_id)
        base = select(ThreadMessage).where(ThreadMessage.thread_id == thread_id)
        total = (await self.session.execute(base.with_only_columns(ThreadMessage.id))).scalars().unique().count()
        stmt = base.order_by(ThreadMessage.created_at)
        if page and limit:
            offset = max(0, (page - 1) * limit)
            stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all(), int(total)

    async def post_message(self, thread_id: uuid.UUID, sender_id: uuid.UUID, body: str) -> ThreadMessage:
        await self._ensure_can_view_thread(thread_id, sender_id, touch=True)
        message = ThreadMessage(thread_id=thread_id, sender_id=sender_id, body=body)
        self.session.add(message)
        await self.session.flush()

        await bus.publish(
            "chat.message.posted",
            {"threadId": str(thread_id), "messageId": str(message.id)},
        )
        return message

    async def _get_item(self, item_id: uuid.UUID) -> Item:
        stmt = select(Item).where(Item.id == item_id)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item

    async def _get_prompts(self, item_id: uuid.UUID) -> list[ItemPrompt]:
        stmt = select(ItemPrompt).where(ItemPrompt.item_id == item_id).order_by(ItemPrompt.position)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def _get_user(self, user_id: uuid.UUID):
        from packages.common.models import User

        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def _ensure_can_view_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID, *, touch: bool = False) -> None:
        stmt = (
            select(ClaimThread)
            .where(ClaimThread.id == thread_id)
            .join(Claim, ClaimThread.claim_id == Claim.id)
        )
        result = await self.session.execute(stmt)
        thread = result.scalar_one_or_none()
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        claim = thread.claim
        if user_id not in {claim.claimant_id, claim.finder_id}:
            actor = await self._get_user(user_id)
            if actor.role != "moderator":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a thread participant")
        if touch:
            thread.last_message_at = datetime.now(UTC)

    async def _set_item_statuses(self, claim: Claim, status: str) -> None:
        lost_stmt = select(Item).where(Item.id == claim.item_id)
        found_stmt = select(Item).where(Item.id == claim.candidate_id)
        lost_result = await self.session.execute(lost_stmt)
        found_result = await self.session.execute(found_stmt)
        lost_item = lost_result.scalar_one_or_none()
        found_item = found_result.scalar_one_or_none()
        if lost_item:
            lost_item.status = status
        if found_item:
            found_item.status = status
