import uuid

import unittest
from unittest.mock import AsyncMock

from sqlalchemy.exc import NoResultFound

from packages.common.models import Item, ItemType, PromptSource, Subscription
from services.intake_service.service import IntakeService


class StubSession:
    def __init__(self):
        self.added = []
        self.flush = AsyncMock()
        self.execute = AsyncMock()
        self.delete = AsyncMock()
        self.rollback = AsyncMock()
        self.commit = AsyncMock()

    def add(self, obj):
        self.added.append(obj)


class StubQueryResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


class FakeQuestionBank:
    def get_prompts_for_category(self, category: str, limit: int = 2):
        return ["Curated A", "Curated B"]


class IntakeServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_create_found_item_builds_prompts(self):
        session = StubSession()
        question_bank = FakeQuestionBank()
        service = IntakeService(session, question_bank)

        finder_id = uuid.uuid4()
        item = await service.create_item(
            type_=ItemType.FOUND,
            title="Blue Bottle",
            description="Blue Hydroflask",
            tags=["HydroFlask", "Blue"],
            location={"zone": "Library"},
            when=None,
            photos=[{"url": "http://example.com/photo.jpg", "thumbnails": [], "safety": {}}],
            category=None,
            prompts=["Custom question"],
            owner_id=None,
            finder_id=finder_id,
        )

        self.assertIsInstance(item, Item)
        self.assertEqual(item.category, "water_bottle")
        self.assertEqual(len(item.media), 1)
        self.assertEqual(len(item.prompts), 3)
        sources = {prompt.source for prompt in item.prompts}
        self.assertIn(PromptSource.CURATED, sources)
        self.assertIn(PromptSource.CUSTOM, sources)
        session.flush.assert_awaited()

    async def test_get_item_not_found(self):
        session = StubSession()
        session.execute.return_value = StubQueryResult(None)
        question_bank = FakeQuestionBank()
        service = IntakeService(session, question_bank)

        with self.assertRaises(NoResultFound):
            await service.get_item(uuid.uuid4())

    async def test_subscription_workflow(self):
        session = StubSession()
        question_bank = FakeQuestionBank()
        service = IntakeService(session, question_bank)

        subscription = await service.create_subscription(uuid.uuid4(), "tech", "campus")
        self.assertIsInstance(subscription, Subscription)
        session.flush.assert_awaited()

        stub_result = StubQueryResult(subscription)
        session.execute.return_value = stub_result
        await service.delete_subscription(subscription.id, subscription.user_id)
        session.delete.assert_awaited()


if __name__ == "__main__":
    unittest.main()
