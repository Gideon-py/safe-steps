"""
Route safety scoring service.

Scores ORS walking routes using OSM data (via Overpass).
Implements the weighted cost formula and pedestrian bridge bonus.
"""

import logging
import math
import uuid
from typing import List, Optional

logger = logging.getLogger(__name__)

# Known traffic hotspots in Bern (lat, lng, name)
BERN_HOTSPOTS = [
    (46.9490, 7.4390, "Bahnhof Bern"),
    (46.9630, 7.4670, "Wankdorfplatz"),
    (46.9430, 7.4470, "Helvetiaplatz"),
    (46.9510, 7.4380, "Hirschengraben"),
    (46.9460, 7.4400, "Bundesplatz"),
]

# Cost formula weights
W_TIME = 0.4
W_TRAFFIC = 0.3
W_CROSSING = 0.2
W_HOTSPOT = 0.1

# Detour limits
MAX_TIME_FACTOR = 1.15   # 15 %
MAX_DIST_FACTOR = 1.20   # 20 %

# Bridge bonus (subtracted from total cost)
BRIDGE_BONUS = 0.05

SAMPLE_INTERVAL_M = 15


# ── Geometry helpers ────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two points."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def sample_route(coords: list, interval_m: float = SAMPLE_INTERVAL_M) -> list:
    """
    Sample points along a route at regular intervals.
    coords: list of [lng, lat] (GeoJSON order).
    Returns list of (lat, lng) tuples.
    """
    if not coords or len(coords) < 2:
        return []
    samples = [(coords[0][1], coords[0][0])]
    accum = 0.0
    for i in range(1, len(coords)):
        lat1, lon1 = coords[i - 1][1], coords[i - 1][0]
        lat2, lon2 = coords[i][1], coords[i][0]
        seg_dist = haversine(lat1, lon1, lat2, lon2)
        accum += seg_dist
        while accum >= interval_m:
            accum -= interval_m
            # interpolate
            frac = 1.0 - (accum / seg_dist) if seg_dist > 0 else 1.0
            s_lat = lat1 + (lat2 - lat1) * frac
            s_lng = lon1 + (lon2 - lon1) * frac
            samples.append((s_lat, s_lng))
    # always include last point
    samples.append((coords[-1][1], coords[-1][0]))
    return samples


def within_radius(lat1, lon1, lat2, lon2, radius_m):
    return haversine(lat1, lon1, lat2, lon2) <= radius_m


# ── Feature proximity ──────────────────────────────────────

def _ways_near(pt, ways, radius_m=30):
    """Find ways whose geometry passes within radius_m of pt."""
    lat, lng = pt
    results = []
    for w in ways:
        for g in w.get("geometry", []):
            if within_radius(lat, lng, g["lat"], g["lon"], radius_m):
                results.append(w)
                break
    return results


def _points_near(pt, points, radius_m=30):
    lat, lng = pt
    return [p for p in points if within_radius(lat, lng, p["lat"], p["lon"], radius_m)]


# ── Scoring ────────────────────────────────────────────────

def _score_sample(pt, osm, radius_m=30):
    """Return (traffic_add, safe_sub, crossing_count) for one sample."""
    traffic = 0.0
    safe = 0.0
    crossings = 0

    for w in _ways_near(pt, osm.get("ways", []), radius_m):
        hw = w.get("tags", {}).get("highway", "")
        # High risk (+1.0)
        if hw in ("trunk", "primary", "secondary"):
            traffic += 1.0
        # Medium risk (+0.5)
        elif hw == "tertiary":
            traffic += 0.5
        # Safe (-0.5)
        elif hw in ("footway", "pedestrian", "living_street", "cycleway"):
            safe += 0.5

    # Stations / bus stops  (+1.0 / +0.5)
    for s in _points_near(pt, osm.get("stations", []), radius_m):
        tags = s.get("tags", {})
        if tags.get("railway") == "station":
            traffic += 1.0
        elif tags.get("amenity") == "bus_station":
            traffic += 0.5

    # Crossings
    crossings += len(_points_near(pt, osm.get("crossings", []), 20))

    return traffic, safe, crossings


def hotspot_proximity(samples) -> float:
    """Average inverse distance to known Bern hotspots (0..1)."""
    if not samples:
        return 0.0
    total = 0.0
    for lat, lng in samples:
        min_d = min(haversine(lat, lng, h[0], h[1]) for h in BERN_HOTSPOTS)
        # 0 at 0 m, ~0 at 500 m+
        total += max(0.0, 1.0 - min_d / 500.0)
    return total / len(samples)


def score_single_route(
    coords: list,
    distance_m: float,
    duration_s: float,
    osm: dict,
    min_duration: float,
    min_distance: float,
    bridge_bonus: bool = False,
) -> Optional[dict]:
    """
    Score one route.  Returns None if it exceeds the detour limit.
    coords: [lng, lat] GeoJSON order.
    """
    # Detour limit check
    if min_duration > 0 and min_distance > 0:
        over_time = duration_s > min_duration * MAX_TIME_FACTOR
        over_dist = distance_m > min_distance * MAX_DIST_FACTOR
        if over_time and over_dist:
            return None  # discard

    samples = sample_route(coords)
    n = max(len(samples), 1)

    total_traffic = 0.0
    total_safe = 0.0
    total_crossings = 0

    danger_zones: list = []

    for pt in samples:
        t, s, c = _score_sample(pt, osm)
        total_traffic += t
        total_safe += s
        total_crossings += c
        # Collect danger zones for high-risk samples
        if t >= 1.0:
            danger_zones.append({"lat": pt[0], "lng": pt[1], "risk": round(t, 1)})

    # Normalize components to 0..1
    raw_traffic = (total_traffic - total_safe) / n
    norm_traffic = max(0.0, min(1.0, raw_traffic / 2.0))

    norm_crossing = min(1.0, total_crossings / n / 1.5)

    if min_duration > 0:
        norm_time = max(0.0, min(1.0, (duration_s / min_duration - 1.0) / 0.15))
    else:
        norm_time = 0.5

    norm_hotspot = hotspot_proximity(samples)

    total_cost = (
        W_TIME * norm_time
        + W_TRAFFIC * norm_traffic
        + W_CROSSING * norm_crossing
        + W_HOTSPOT * norm_hotspot
    )

    if bridge_bonus:
        total_cost = max(0.0, total_cost - BRIDGE_BONUS)

    safety_pct = max(0, min(100, round(100 * (1.0 - total_cost))))

    # Aggregate danger zones (merge nearby ones)
    merged = _merge_danger_zones(danger_zones, merge_radius_m=60)

    return {
        "total_cost": round(total_cost, 4),
        "safety_score": safety_pct,
        "risk_details": {
            "time_penalty": round(norm_time * 100),
            "traffic_risk": round(norm_traffic * 100),
            "crossing_risk": round(norm_crossing * 100),
            "hotspot_risk": round(norm_hotspot * 100),
        },
        "danger_zones": merged,
    }


def _merge_danger_zones(zones, merge_radius_m=60):
    """Merge nearby danger zones into aggregated zones."""
    if not zones:
        return []
    merged = []
    used = set()
    for i, z in enumerate(zones):
        if i in used:
            continue
        cluster = [z]
        for j in range(i + 1, len(zones)):
            if j in used:
                continue
            if haversine(z["lat"], z["lng"], zones[j]["lat"], zones[j]["lng"]) < merge_radius_m:
                cluster.append(zones[j])
                used.add(j)
        avg_lat = sum(c["lat"] for c in cluster) / len(cluster)
        avg_lng = sum(c["lng"] for c in cluster) / len(cluster)
        max_risk = max(c["risk"] for c in cluster)
        merged.append({
            "lat": round(avg_lat, 6),
            "lng": round(avg_lng, 6),
            "radius": 40 + len(cluster) * 5,
            "level": "high" if max_risk >= 1.5 else "medium",
            "reason": "Hohes Verkehrsrisiko" if max_risk >= 1.5 else "Erhoehtes Verkehrsrisiko",
        })
    return merged


# ── Bridge detection ───────────────────────────────────────

def find_bridges_in_corridor(coords: list, osm: dict, corridor_m: float = 100) -> list:
    """
    Find pedestrian bridges within `corridor_m` of the route.
    Returns list of (lat, lng) bridge midpoints.
    """
    bridges = osm.get("bridges", [])
    if not bridges:
        return []

    route_samples = sample_route(coords, interval_m=50)
    found = []
    for br in bridges:
        geom = br.get("geometry", [])
        if len(geom) < 2:
            continue
        mid = geom[len(geom) // 2]
        blat, blng = mid["lat"], mid["lon"]
        for pt in route_samples:
            if within_radius(pt[0], pt[1], blat, blng, corridor_m):
                found.append((blat, blng))
                break
    return found


# ── Main scoring pipeline ──────────────────────────────────

def score_all_routes(ors_features: list, osm: dict) -> list:
    """
    Score a list of ORS GeoJSON features.
    Returns list of scored route dicts sorted by total_cost (safest first).
    """
    if not ors_features:
        return []

    # Determine fastest (min duration) and shortest (min distance)
    min_dur = min(f["properties"]["summary"]["duration"] for f in ors_features)
    min_dist = min(f["properties"]["summary"]["distance"] for f in ors_features)

    scored = []
    for idx, feat in enumerate(ors_features):
        coords = feat["geometry"]["coordinates"]
        dist = feat["properties"]["summary"]["distance"]
        dur = feat["properties"]["summary"]["duration"]

        result = score_single_route(coords, dist, dur, osm, min_dur, min_dist)
        if result is None:
            continue  # exceeds detour limit

        scored.append({
            "id": f"route_{idx + 1}",
            "distance_m": round(dist),
            "duration_s": round(dur),
            "geometry": feat["geometry"],
            "safety_score": result["safety_score"],
            "total_cost": result["total_cost"],
            "is_safest": False,
            "risk_details": result["risk_details"],
            "danger_zones": result["danger_zones"],
        })

    # Sort by total_cost ascending (safest first)
    scored.sort(key=lambda r: r["total_cost"])
    if scored:
        scored[0]["is_safest"] = True
    return scored


def score_bridge_route(ors_feature: dict, osm: dict, min_dur: float, min_dist: float) -> Optional[dict]:
    """Score a single via-bridge route with bridge bonus."""
    if not ors_feature:
        return None
    coords = ors_feature["geometry"]["coordinates"]
    dist = ors_feature["properties"]["summary"]["distance"]
    dur = ors_feature["properties"]["summary"]["duration"]

    result = score_single_route(coords, dist, dur, osm, min_dur, min_dist, bridge_bonus=True)
    if result is None:
        return None

    return {
        "id": f"route_bridge_{uuid.uuid4().hex[:6]}",
        "distance_m": round(dist),
        "duration_s": round(dur),
        "geometry": ors_feature["geometry"],
        "safety_score": result["safety_score"],
        "total_cost": result["total_cost"],
        "is_safest": False,
        "risk_details": result["risk_details"],
        "danger_zones": result["danger_zones"],
        "via_bridge": True,
    }
