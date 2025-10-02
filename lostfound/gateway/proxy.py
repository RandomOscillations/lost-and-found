from __future__ import annotations

from typing import Any, Dict, Iterable

import httpx
from fastapi import Request, Response


def _filtered_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    allowed = {"content-type", "set-cookie"}
    return {k: v for k, v in headers if k.lower() in allowed}


async def forward_request(
    request: Request,
    *,
    base_url: str,
    path: str,
    json_body: Any | None = None,
    query_params: Dict[str, Any] | None = None,
) -> Response:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
    content = None
    json_payload = None
    if json_body is not None:
        if hasattr(json_body, "model_dump"):
            json_payload = json_body.model_dump(mode="json")  # type: ignore[attr-defined]
        else:
            json_payload = json_body
    else:
        body = await request.body()
        if body:
            content = body
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=request.method,
            url=url,
            params=query_params if query_params is not None else request.query_params,
            content=content,
            json=json_payload,
            headers=headers,
        )
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=_filtered_headers(response.headers.items()),
        media_type=response.headers.get("content-type"),
    )
