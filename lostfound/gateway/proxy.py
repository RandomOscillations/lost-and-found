from __future__ import annotations

from typing import Iterable

import httpx
from fastapi import Request, Response


def _filtered_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    allowed = {"content-type", "set-cookie"}
    return {k: v for k, v in headers if k.lower() in allowed}


async def forward_request(request: Request, *, base_url: str, path: str) -> Response:
    url = f"{base_url.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            content=await request.body(),
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
        )
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=_filtered_headers(response.headers.items()),
        media_type=response.headers.get("content-type"),
    )
