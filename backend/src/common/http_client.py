# backend/src/common/http_client.py
"""Audited, rate-limited async HTTP client. Prevents accidental DoS and records
every outbound request as JSON to stdout (captured by CloudWatch)."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

logger = logging.getLogger("tier2.http")
logger.setLevel(logging.INFO)


class AuditedClient:
    def __init__(self, scan_id: str, max_concurrency: int = 4,
                 min_interval_s: float = 0.1, timeout_s: float = 20.0) -> None:
        self.scan_id = scan_id
        self._sem = asyncio.Semaphore(max_concurrency)
        self._min_interval = min_interval_s
        self._last = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=timeout_s, follow_redirects=False,
                                         verify=False)

    async def __aenter__(self) -> "AuditedClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        async with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._sem:
            await self._throttle()
            try:
                resp = await self._client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                logger.info(json.dumps({"scan_id": self.scan_id, "method": method,
                                        "url": url, "error": str(exc)}))
                raise
            logger.info(json.dumps({"scan_id": self.scan_id, "method": method,
                                    "url": url, "status": resp.status_code,
                                    "len": len(resp.content)}))
            return resp
