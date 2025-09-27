from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Awaitable, Dict, List, Protocol

from .config import get_settings

logger = logging.getLogger("events")


class Handler(Protocol):
    async def __call__(self, payload: dict) -> None: ...


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)
        self._settings = get_settings()
        self._nats_url = str(self._settings.nats_url) if self._settings.nats_url else None
        self._subject_prefix = self._settings.nats_subject_prefix.rstrip(".") + "."
        self._nats_client = None
        self._nats_subscriptions: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _full_subject(self, event: str) -> str:
        return f"{self._subject_prefix}{event}" if self._nats_url else event

    async def _ensure_nats(self):
        if not self._nats_url:
            return None
        if self._nats_client is not None and self._nats_client.is_connected:
            return self._nats_client
        try:
            from nats.aio.client import Client as NATS
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError("nats-py is required when NATS_URL is configured") from exc

        if self._nats_client is None:
            self._nats_client = NATS()
        await self._nats_client.connect(self._nats_url, name=self._settings.app_name)
        return self._nats_client

    async def _dispatch_local(self, event: str, payload: dict) -> None:
        handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            await handler(payload)

    async def _register_remote_subscription(self, event: str) -> None:
        if not self._nats_url:
            return
        subject = self._full_subject(event)
        async with self._lock:
            if subject in self._nats_subscriptions:
                return
            client = await self._ensure_nats()
            if client is None:
                return

            async def _callback(message):
                try:
                    payload = json.loads(message.data.decode())
                except json.JSONDecodeError:
                    logger.warning("Discarding malformed event payload on %s", subject)
                    return
                await self._dispatch_local(event, payload)

            sid = await client.subscribe(subject, cb=_callback)
            self._nats_subscriptions[subject] = sid

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)
        if self._nats_url:
            asyncio.create_task(self._register_remote_subscription(event))

    async def publish(self, event: str, payload: dict) -> None:
        if self._nats_url:
            client = await self._ensure_nats()
            if client is not None:
                await client.publish(self._full_subject(event), json.dumps(payload).encode())
        await self._dispatch_local(event, payload)

    def publish_background(self, event: str, payload: dict) -> Awaitable[None]:
        return asyncio.create_task(self.publish(event, payload))


bus = EventBus()
