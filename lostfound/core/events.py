from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List, Protocol


class Handler(Protocol):
    async def __call__(self, payload: dict) -> None: ...


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    async def publish(self, event: str, payload: dict) -> None:
        handlers = self._handlers.get(event, [])
        for handler in handlers:
            await handler(payload)

    def publish_background(self, event: str, payload: dict) -> Awaitable[None]:
        return asyncio.create_task(self.publish(event, payload))


bus = EventBus()
