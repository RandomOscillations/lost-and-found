from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.models import (
    Item,
    ItemMedia,
    ItemPrompt,
    ItemStatus,
    ItemType,
    PromptSource,
    Report,
    Subscription,
)
from packages.common.question_bank import QuestionBankService
from packages.common.utils.categories import infer_category


class IntakeService:
    def __init__(self, session: AsyncSession, question_bank: QuestionBankService) -> None:
        self.session = session
        self.question_bank = question_bank

    async def create_item(
        self,
        *,
        type_: str,
        title: str,
        description: str,
        tags: Sequence[str],
        location: dict | None,
        when,
        photos: Sequence[dict],
        category: str | None,
        prompts: Sequence[str],
        owner_id: uuid.UUID | None,
        finder_id: uuid.UUID | None,
    ) -> Item:
        normalized_tags = [tag.strip().lower() for tag in tags if tag.strip()]
        resolved_category = category or infer_category(title, description, tags=normalized_tags)

        item = Item(
            type=type_,
            title=title,
            description=description,
            tags=normalized_tags,
            owner_id=owner_id,
            finder_id=finder_id,
            category=resolved_category,
            zone=(location or {}).get("zone"),
            location_lat=(location or {}).get("lat"),
            location_lon=(location or {}).get("lon"),
            location_raw=location,
            when=when,
        )
        self.session.add(item)

        for photo in photos:
            media = ItemMedia(
                item_id=item.id,
                url=photo.get("url"),
                thumb_url=(photo.get("thumbnails") or [None])[0],
                faces_blurred=photo.get("safety", {}).get("facesBlurred", True),
                pii_redacted=photo.get("safety", {}).get("piiRedacted", True),
            )
            self.session.add(media)
            item.media.append(media)

        if type_ == ItemType.FOUND:
            curated_prompts = self.question_bank.get_prompts_for_category(resolved_category, limit=2)
            for idx, text in enumerate(curated_prompts):
                entry = ItemPrompt(
                    item_id=item.id,
                    prompt=text,
                    source=PromptSource.CURATED,
                    position=idx,
                )
                self.session.add(entry)
                item.prompts.append(entry)

            clean_custom = [text.strip() for text in prompts[:2] if text and text.strip()]
            for offset, text in enumerate(clean_custom):
                entry = ItemPrompt(
                    item_id=item.id,
                    prompt=text,
                    source=PromptSource.CUSTOM,
                    position=len(curated_prompts) + offset,
                )
                self.session.add(entry)
                item.prompts.append(entry)

        await self.session.flush()
        return item

    async def get_item(self, item_id: uuid.UUID) -> Item:
        stmt = select(Item).where(Item.id == item_id)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            raise NoResultFound
        return item

    async def search_items(
        self,
        *,
        type_: str | None = None,
        zone: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[Item]:
        stmt = select(Item)
        conditions = []
        if type_:
            conditions.append(Item.type == type_)
        if zone:
            conditions.append(Item.zone == zone)
        if status:
            conditions.append(Item.status == status)
        if category:
            conditions.append(Item.category == category)
        if tag:
            conditions.append(Item.tags.contains([tag.lower()]))
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Item.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_prompts_for_item(self, item_id: uuid.UUID) -> list[ItemPrompt]:
        stmt = select(ItemPrompt).where(ItemPrompt.item_id == item_id).order_by(ItemPrompt.position.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def record_report(self, reporter_id: uuid.UUID, target_id: uuid.UUID, reason: str) -> Report:
        report = Report(reporter_id=reporter_id, target_id=target_id, reason=reason)
        self.session.add(report)
        await self.session.flush()
        return report

    async def create_subscription(self, user_id: uuid.UUID, tag: str | None, zone: str | None) -> Subscription:
        subscription = Subscription(user_id=user_id, tag=tag, zone=zone)
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def delete_subscription(self, subscription_id: uuid.UUID, user_id: uuid.UUID) -> None:
        stmt = select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == user_id)
        result = await self.session.execute(stmt)
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise NoResultFound
        await self.session.delete(subscription)

    async def update_item_status(self, item_id: uuid.UUID, status: str) -> Item:
        item = await self.get_item(item_id)
        item.status = status
        await self.session.flush()
        return item
