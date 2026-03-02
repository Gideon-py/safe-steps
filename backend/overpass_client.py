"""Overpass API client for OSM road/feature data with TTL cache."""

import logging
import math
import os
import time
import hashlib
from typing import List

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


class _OverpassCache:
    """30-minute TTL cache keyed by bounding-box string."""

    def __init__(self, ttl: int = 1800):
        self._store: dict = {}
        self._ttl = ttl

    def get(self, key: str):
        k = hashlib.md5(key.encode()).hexdigest()
        if k in self._store:
            val, ts = self._store[k]
            if time.time() - ts < self._ttl:
                return val
            del self._store[k]
        return None

    def put(self, key: str, value):
        self._store[hashlib.md5(key.encode()).hexdigest()] = (value, time.time())


class OverpassClient:
    """Fetch OSM features (roads, crossings, bridges, stations) in a bounding box."""

    def __init__(self):
        self.cache = _OverpassCache(ttl=1800)  # 30 min

    async def get_features(self, coords: list) -> dict:
        """
        coords: list of [lng, lat] (GeoJSON order).
        Returns dict with keys: ways, crossings, bridges, stations.
        """
        bbox = self._bbox(coords, padding_m=120)
        bbox_key = f"{bbox['south']:.4f},{bbox['west']:.4f},{bbox['north']:.4f},{bbox['east']:.4f}"

        cached = self.cache.get(bbox_key)
        if cached is not None:
            logger.info("Overpass cache hit")
            return cached

        query = self._build_query(bbox)
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                resp = await c.post(OVERPASS_URL, data={"data": query})
                if resp.status_code != 200:
                    logger.warning("Overpass returned %s", resp.status_code)
                    return self._empty()
                raw = resp.json()
        except Exception as e:
            logger.warning("Overpass query failed: %s", e)
            return self._empty()

        parsed = self._parse(raw.get("elements", []))
        self.cache.put(bbox_key, parsed)
        return parsed

    # ── internal ─────────────────────────────────────────────

    @staticmethod
    def _bbox(coords: list, padding_m: int = 120) -> dict:
        lats = [c[1] for c in coords]
        lngs = [c[0] for c in coords]
        pad_lat = padding_m / 111320
        pad_lng = padding_m / (111320 * math.cos(math.radians(sum(lats) / len(lats))))
        return {
            "south": min(lats) - pad_lat,
            "west": min(lngs) - pad_lng,
            "north": max(lats) + pad_lat,
            "east": max(lngs) + pad_lng,
        }

    @staticmethod
    def _build_query(bb: dict) -> str:
        b = f"{bb['south']},{bb['west']},{bb['north']},{bb['east']}"
        return f"""[out:json][timeout:12];
(
  way["highway"~"trunk|primary|secondary|tertiary|footway|pedestrian|living_street|cycleway"]({b});
  node["highway"="crossing"]({b});
  node["railway"="station"]({b});
  node["amenity"="bus_station"]({b});
  way["highway"="footway"]["bridge"="yes"]({b});
  way["man_made"="bridge"]["foot"~"yes|designated"]({b});
);
out body geom;"""

    @staticmethod
    def _parse(elements: list) -> dict:
        ways = []
        crossings = []
        bridges = []
        stations = []

        for el in elements:
            tags = el.get("tags", {})
            if el["type"] == "node":
                pt = {"lat": el["lat"], "lon": el["lon"], "tags": tags}
                if tags.get("highway") == "crossing":
                    crossings.append(pt)
                elif tags.get("railway") == "station" or tags.get("amenity") == "bus_station":
                    stations.append(pt)
            elif el["type"] == "way":
                geom = el.get("geometry", [])
                entry = {"tags": tags, "geometry": geom}
                hw = tags.get("highway", "")
                is_bridge = (
                    (tags.get("bridge") == "yes" and hw == "footway")
                    or (tags.get("man_made") == "bridge" and tags.get("foot") in ("yes", "designated"))
                )
                if is_bridge:
                    bridges.append(entry)
                elif hw:
                    ways.append(entry)

        return {
            "ways": ways,
            "crossings": crossings,
            "bridges": bridges,
            "stations": stations,
        }

    @staticmethod
    def _empty() -> dict:
        return {"ways": [], "crossings": [], "bridges": [], "stations": []}
