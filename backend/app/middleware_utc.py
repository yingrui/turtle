"""把不带时区的时间戳统一标成 UTC。

数据库里存的是 naive UTC（Postgres 的 `timestamp` 不带时区），FastAPI 序列化成
`2026-11-04T03:34:22` —— 前端无法判断这是 UTC 还是本地时间，只能各自猜，于是有的页面早 8 小时。

在出口处一次标清楚，前端就不必每处补时区。只改 JSON 响应里的时间字面量。
"""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# "YYYY-MM-DDTHH:MM:SS[.ffffff]" 且不带时区后缀
NAIVE_ISO = re.compile(rb'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)"')


class UtcTimestampsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").split(";")[0] != "application/json":
            return response

        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode() for chunk in chunks)
        patched = NAIVE_ISO.sub(rb'"\1Z"', body)
        if patched == body:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        headers = dict(response.headers)
        headers["content-length"] = str(len(patched))
        headers.pop("content-encoding", None)
        return Response(
            content=patched,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
