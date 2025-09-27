from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ClaimAnswerInput(BaseModel):
    question: str
    answer: str


class ClaimCreate(BaseModel):
    itemId: str = Field(description="Lost item id (the claimant's)")
    candidateId: str = Field(description="Found item id being claimed")
    answers: List[ClaimAnswerInput]


class Claim(BaseModel):
    id: str
    itemId: str
    candidateId: str
    claimantId: str
    finderId: str
    status: str
    createdAt: datetime
    updatedAt: datetime


class ClaimUpdate(BaseModel):
    action: str = Field(description="Action finder/moderator is taking", pattern="^(verify|reject|close)$")
    reason: Optional[str] = None


class Message(BaseModel):
    id: str
    threadId: str
    senderId: str
    body: str
    createdAt: datetime


class MessageCreate(BaseModel):
    body: str


class Thread(BaseModel):
    id: str
    claimId: str
    participants: List[str] = Field(default_factory=list)
    lastMessageAt: Optional[datetime] = None
