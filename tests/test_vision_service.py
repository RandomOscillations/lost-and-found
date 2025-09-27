import uuid
from datetime import datetime, timezone

import unittest

from packages.common.models import Item, ItemStatus, ItemType
from services.vision_service.service import VisionService


class StubResult:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._scalars_list


class StubSession:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, stmt):  # pragma: no cover - simple stub
        if not self._results:
            raise RuntimeError("No more results configured")
        return self._results.pop(0)


def make_item(item_id: uuid.UUID, *, type_: ItemType, title: str, description: str, tags: list[str], category: str, zone: str = "Library", when: datetime | None = None) -> Item:
    item = Item(
        id=item_id,
        type=type_,
        title=title,
        description=description,
        tags=tags,
        category=category,
        zone=zone,
        status=ItemStatus.ACTIVE,
        when=when,
    )
    item.created_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    return item


class VisionServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_get_matches_returns_candidates(self):
        lost_id = uuid.uuid4()
        found_id = uuid.uuid4()
        lost_item = make_item(
            lost_id,
            type_=ItemType.LOST,
            title="Lost Bottle",
            description="blue bottle",
            tags=["blue"],
            category="water_bottle",
            when=datetime(2025, 9, 5, 13, tzinfo=timezone.utc),
        )
        found_item = make_item(
            found_id,
            type_=ItemType.FOUND,
            title="Found Bottle",
            description="blue bottle",
            tags=["blue"],
            category="water_bottle",
            when=datetime(2025, 9, 5, 14, tzinfo=timezone.utc),
        )

        session = StubSession([
            StubResult(scalar=lost_item),
            StubResult(scalars_list=[found_item]),
        ])
        service = VisionService(session)
        matches = await service.get_matches(lost_id, limit=5)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].candidateId, str(found_id))
        self.assertGreater(matches[0].score, 0)

    async def test_get_matches_item_missing(self):
        session = StubSession([StubResult(scalar=None)])
        service = VisionService(session)
        with self.assertRaises(LookupError):
            await service.get_matches(uuid.uuid4())


if __name__ == "__main__":
    unittest.main()
