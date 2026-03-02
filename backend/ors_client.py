"""ORS (OpenRouteService) Directions API client with TTL cache."""

import hashlib
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class TTLCache:
    """Simple in-memory TTL cache."""

    def __init__(self, ttl: int = 600):
        self._store: dict = {}
        self._ttl = ttl

    def _key(self, raw: str) -> str:
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, raw_key: str):
        k = self._key(raw_key)
        if k in self._store:
            val, ts = self._store[k]
            if time.time() - ts < self._ttl:
                return val
            del self._store[k]
        return None

    def put(self, raw_key: str, value):
        self._store[self._key(raw_key)] = (value, time.time())

    def clear(self):
        self._store.clear()


def _ors_key() -> str:
    return os.environ.get("ORS_API_KEY", "")


class ORSClient:
    """Async client for ORS Directions foot-walking endpoint."""

    URL = "https://api.openrouteservice.org/v2/directions/foot-walking/geojson"

    def __init__(self):
        self.cache = TTLCache(ttl=600)  # 10 min

    # ── public ──────────────────────────────────────────────

    async def get_alternatives(
        self, start_lat: float, start_lng: float, end_lat: float, end_lng: float
    ) -> dict:
        """Return up to 3 alternative walking routes as GeoJSON FeatureCollection."""
        cache_key = f"alt:{start_lat:.5f},{start_lng:.5f}-{end_lat:.5f},{end_lng:.5f}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.info("ORS cache hit for alternatives")
            return cached

        body = {
            "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
            "alternative_routes": {
                "target_count": 3,
                "share_factor": 0.6,
                "weight_factor": 1.6,
            },
            "instructions": False,
            "geometry_simplify": False,
        }
        data = await self._post(body, cache_key)
        return data

    async def get_route_via(
        self,
        start_lat: float,
        start_lng: float,
        via_lat: float,
        via_lng: float,
        end_lat: float,
        end_lng: float,
    ) -> dict:
        """Single route through a via-point (e.g. a pedestrian bridge)."""
        cache_key = f"via:{start_lat:.5f},{start_lng:.5f}-{via_lat:.5f},{via_lng:.5f}-{end_lat:.5f},{end_lng:.5f}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        body = {
            "coordinates": [
                [start_lng, start_lat],
                [via_lng, via_lat],
                [end_lng, end_lat],
            ],
            "instructions": False,
            "geometry_simplify": False,
        }
        data = await self._post(body, cache_key)
        return data

    # ── internal ────────────────────────────────────────────

    async def _post(self, body: dict, cache_key: str) -> dict:
        key = _ors_key()
        if not key:
            raise RuntimeError("ORS_API_KEY not configured")

        headers = {"Authorization": key, "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                resp = await c.post(self.URL, json=body, headers=headers)

                if resp.status_code == 429:
                    cached = self.cache.get(cache_key)
                    if cached is not None:
                        logger.warning("ORS 429 – returning cached result")
                        return cached
                    raise ORSError(503, "Rate limit exceeded, try again later")

                if resp.status_code >= 500:
                    logger.error("ORS server error %s: %s", resp.status_code, resp.text[:200])
                    raise ORSError(502, f"ORS server error ({resp.status_code})")

                if resp.status_code >= 400:
                    logger.error("ORS client error %s: %s", resp.status_code, resp.text[:300])
                    raise ORSError(resp.status_code, f"ORS error: {resp.text[:200]}")

                data = resp.json()
                self.cache.put(cache_key, data)
                return data

        except httpx.TimeoutException:
            logger.error("ORS request timed out after 8 s")
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
            raise ORSError(504, "Route calculation timed out")


class ORSError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)
