from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("lostfound.notify")


@dataclass
class Notification:
    subject: str
    body: str
    recipients: list[str]


async def send_notification(notification: Notification) -> None:
    logger.info("[notify] subject=%s recipients=%s", notification.subject, notification.recipients)


async def handle_match_event(payload: dict) -> None:
    logger.debug("match event: %s", payload)


async def handle_claim_updated(payload: dict) -> None:
    logger.debug("claim updated: %s", payload)
