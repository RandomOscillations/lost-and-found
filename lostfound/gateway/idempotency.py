from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Tuple

from fastapi import HTTPException, Request, status


class _MemoryTTL:
    def __init__(self) -> None:
        self._store: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def add(self, key: str, ttl_seconds: int) -> bool:
        now = time.time()
        async with self._lock:
            # purge
            expired = [k for k, exp in self._store.items() if exp <= now]
            for k in expired:
                self._store.pop(k, None)
            if key in self._store:
                return False
            self._store[key] = now + ttl_seconds
            return True


_cache = _MemoryTTL()


def _make_key(request: Request, body: dict | None) -> str:
    payload = {
        "path": request.url.path,
        "query": str(request.url.query),
        "body": body or {},
        "sub": request.headers.get("X-Sub", ""),
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


async def ensure_idempotent(request: Request, body: dict | None, ttl_seconds: int = 300) -> None:
    idem = request.headers.get("Idempotency-Key")
    if not idem:
        return  # only enforce when client opts in
    key = idem + ":" + _make_key(request, body)
    added = await _cache.add(key, ttl_seconds)
    if not added:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate request (Idempotency-Key)")

