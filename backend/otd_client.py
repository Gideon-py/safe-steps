"""
OTD (Open Transport Data Switzerland) client for real-time traffic data.

Provides:
- Road traffic counter data (vehicle counts per measurement site)
- Traffic situation data (incidents, road works, etc.)

Uses Bearer token auth via OTD_API_KEY from environment.
Falls back to mock data if API is unavailable.
"""

import hashlib
import logging
import math
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# API endpoints - OTD uses SOAP/DATEX2 protocol
COUNTERS_URL = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/Pull/v2/trafficdata"
SITUATIONS_URL = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/Pull/v2/trafficsituation"


def _otd_key() -> str:
    return os.environ.get("OTD_API_KEY", "")


class _OTDCache:
    """5-minute TTL cache for OTD data."""

    def __init__(self, ttl: int = 300):
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


def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class OTDClient:
    """Client for OTD real-time traffic APIs with fallback to realistic mock data."""

    def __init__(self):
        self.cache = _OTDCache(ttl=300)  # 5 min
        self._api_available = None  # None = unknown, True/False after first call

    async def get_traffic_near_route(
        self, route_coords: list, corridor_m: float = 200
    ) -> dict:
        """
        Get traffic data near a route.
        route_coords: list of [lng, lat] (GeoJSON order)
        Returns: { vehicles_per_hour: float, level: str, sites: [...], incidents: [...] }
        """
        if not route_coords:
            return self._empty_traffic()

        # Sample route points for bounding box
        lats = [c[1] for c in route_coords]
        lngs = [c[0] for c in route_coords]
        bbox = {
            "south": min(lats) - 0.005,
            "north": max(lats) + 0.005,
            "west": min(lngs) - 0.005,
            "east": max(lngs) + 0.005,
        }

        cache_key = f"traffic:{bbox['south']:.3f},{bbox['west']:.3f},{bbox['north']:.3f},{bbox['east']:.3f}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Try live API first
        result = await self._fetch_live_traffic(bbox, route_coords, corridor_m)
        self.cache.put(cache_key, result)
        return result

    async def get_incidents_near_route(
        self, route_coords: list, corridor_m: float = 300
    ) -> list:
        """Get traffic incidents/situations near a route."""
        if not route_coords:
            return []

        lats = [c[1] for c in route_coords]
        lngs = [c[0] for c in route_coords]
        bbox = {
            "south": min(lats) - 0.005,
            "north": max(lats) + 0.005,
            "west": min(lngs) - 0.005,
            "east": max(lngs) + 0.005,
        }

        cache_key = f"incidents:{bbox['south']:.3f},{bbox['west']:.3f},{bbox['north']:.3f},{bbox['east']:.3f}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        incidents = await self._fetch_live_incidents(bbox, route_coords, corridor_m)
        self.cache.put(cache_key, incidents)
        return incidents

    # ── Internal API calls ────────────────────────────────────

    async def _fetch_live_traffic(self, bbox, route_coords, corridor_m) -> dict:
        """Try fetching live traffic data via SOAP; fall back to time-based estimate."""
        key = _otd_key()
        if not key or self._api_available is False:
            return self._mock_traffic(route_coords)

        try:
            # OTD uses SOAP/DATEX2 protocol
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <d2p:d2LogicalModel xmlns:d2p="http://datex2.eu/schema/2/2_0" modelBaseVersion="2">
      <d2p:exchange>
        <d2p:supplierIdentification>
          <d2p:country>ch</d2p:country>
          <d2p:nationalIdentifier>SafeStepsBern</d2p:nationalIdentifier>
        </d2p:supplierIdentification>
      </d2p:exchange>
    </d2p:d2LogicalModel>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullMeasuredData",
            }
            async with httpx.AsyncClient(timeout=8.0) as c:
                resp = await c.post(COUNTERS_URL, content=soap_body, headers=headers)
                if resp.status_code == 200:
                    self._api_available = True
                    # Parse SOAP/XML response would go here
                    # For now, use the response to confirm connectivity
                    logger.info("OTD traffic API responded OK")
                    return self._parse_soap_traffic(resp.text, route_coords, corridor_m)
                else:
                    logger.warning("OTD traffic API returned %s", resp.status_code)
                    self._api_available = False
        except Exception as e:
            logger.warning("OTD traffic API failed: %s", e)
            self._api_available = False

        return self._mock_traffic(route_coords)

    async def _fetch_live_incidents(self, bbox, route_coords, corridor_m) -> list:
        """Try fetching live incidents via SOAP; fall back to empty."""
        key = _otd_key()
        if not key or self._api_available is False:
            return self._mock_incidents(route_coords)

        try:
            soap_body = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <d2p:d2LogicalModel xmlns:d2p="http://datex2.eu/schema/2/2_0" modelBaseVersion="2">
      <d2p:exchange>
        <d2p:supplierIdentification>
          <d2p:country>ch</d2p:country>
          <d2p:nationalIdentifier>SafeStepsBern</d2p:nationalIdentifier>
        </d2p:supplierIdentification>
      </d2p:exchange>
    </d2p:d2LogicalModel>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullSituationData",
            }
            async with httpx.AsyncClient(timeout=8.0) as c:
                resp = await c.post(SITUATIONS_URL, content=soap_body, headers=headers)
                if resp.status_code == 200:
                    return self._parse_soap_incidents(resp.text, route_coords, corridor_m)
                else:
                    logger.warning("OTD situations API returned %s", resp.status_code)
        except Exception as e:
            logger.warning("OTD situations API failed: %s", e)

        return self._mock_incidents(route_coords)

    # ── SOAP parsing helpers ──────────────────────────────────

    def _parse_soap_traffic(self, xml_text, route_coords, corridor_m) -> dict:
        """Parse DATEX2 SOAP response for traffic measurement data."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            ns = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'd2': 'http://datex2.eu/schema/2/2_0',
            }

            sites = []
            total_vehicles = 0
            count = 0
            route_samples = [(c[1], c[0]) for c in route_coords[::10]]

            for sm in root.iter('{http://datex2.eu/schema/2/2_0}siteMeasurements'):
                # Extract location
                lat_el = sm.find('.//{http://datex2.eu/schema/2/2_0}latitude')
                lon_el = sm.find('.//{http://datex2.eu/schema/2/2_0}longitude')
                if lat_el is None or lon_el is None:
                    continue

                site_lat = float(lat_el.text)
                site_lng = float(lon_el.text)

                near = any(
                    haversine(pt[0], pt[1], site_lat, site_lng) <= corridor_m
                    for pt in route_samples
                )
                if not near:
                    continue

                # Extract vehicle flow rate
                vph = 0
                for vf in sm.iter('{http://datex2.eu/schema/2/2_0}vehicleFlowRate'):
                    try:
                        vph = int(float(vf.text))
                    except (ValueError, TypeError):
                        pass

                sites.append({"lat": site_lat, "lng": site_lng, "vehicles_per_hour": vph})
                total_vehicles += vph
                count += 1

            if count == 0:
                logger.info("OTD: No traffic sites found near route, using estimate")
                return self._mock_traffic(route_coords)

            avg_vph = total_vehicles / count
            level = "low" if avg_vph < 300 else "medium" if avg_vph < 600 else "high"

            return {
                "vehicles_per_hour": round(avg_vph),
                "level": level,
                "source": "live",
                "sites": sites,
                "site_count": count,
            }
        except Exception as e:
            logger.warning("Error parsing OTD SOAP traffic: %s", e)
            return self._mock_traffic(route_coords)

    def _parse_soap_incidents(self, xml_text, route_coords, corridor_m) -> list:
        """Parse DATEX2 SOAP response for traffic situation data."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            incidents = []
            route_samples = [(c[1], c[0]) for c in route_coords[::10]]

            for sr in root.iter('{http://datex2.eu/schema/2/2_0}situationRecord'):
                lat_el = sr.find('.//{http://datex2.eu/schema/2/2_0}latitude')
                lon_el = sr.find('.//{http://datex2.eu/schema/2/2_0}longitude')
                if lat_el is None or lon_el is None:
                    continue

                lat = float(lat_el.text)
                lng = float(lon_el.text)

                near = any(
                    haversine(pt[0], pt[1], lat, lng) <= corridor_m
                    for pt in route_samples
                )
                if not near:
                    continue

                severity_el = sr.find('{http://datex2.eu/schema/2/2_0}severity')
                severity = severity_el.text if severity_el is not None else "medium"

                incidents.append({
                    "lat": lat, "lng": lng,
                    "type": "traffic_situation",
                    "severity": severity,
                    "description": "Verkehrsstoerung",
                })

            return incidents
        except Exception as e:
            logger.warning("Error parsing OTD SOAP incidents: %s", e)
            return []

    # ── Mock data (realistic for Bern) ────────────────────────

    def _mock_traffic(self, route_coords) -> dict:
        """Generate realistic mock traffic data based on time of day and route location."""
        import datetime

        hour = datetime.datetime.now().hour

        # Rush hour patterns for Bern school routes
        base_patterns = {
            6: 180, 7: 450, 8: 620, 9: 380, 10: 250,
            11: 220, 12: 350, 13: 300, 14: 260, 15: 380,
            16: 520, 17: 650, 18: 480, 19: 300, 20: 180,
        }
        base_vph = base_patterns.get(hour, 150)

        # Check proximity to known busy areas in Bern
        busy_areas = [
            (46.9490, 7.4390, "Bahnhof Bern", 1.4),
            (46.9630, 7.4670, "Wankdorfplatz", 1.3),
            (46.9430, 7.4470, "Helvetiaplatz", 1.2),
            (46.9510, 7.4380, "Hirschengraben", 1.2),
            (46.9460, 7.4400, "Bundesplatz", 1.3),
        ]

        if route_coords:
            mid = route_coords[len(route_coords) // 2]
            mid_lat, mid_lng = mid[1], mid[0]
            multiplier = 1.0
            for blat, blng, _, factor in busy_areas:
                if haversine(mid_lat, mid_lng, blat, blng) < 500:
                    multiplier = max(multiplier, factor)
            base_vph = int(base_vph * multiplier)

        level = "low" if base_vph < 300 else "medium" if base_vph < 600 else "high"

        return {
            "vehicles_per_hour": base_vph,
            "level": level,
            "source": "estimated",
            "sites": [],
            "site_count": 0,
        }

    def _mock_incidents(self, route_coords) -> list:
        """Return empty incidents (no known incidents in mock mode)."""
        return []

    def _empty_traffic(self) -> dict:
        return {
            "vehicles_per_hour": 0,
            "level": "unknown",
            "source": "none",
            "sites": [],
            "site_count": 0,
        }
