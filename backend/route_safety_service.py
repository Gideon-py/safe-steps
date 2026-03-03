"""
Route safety scoring service v2.

New weighted cost formula:
  0.35 * time_penalty
  + 0.25 * osm_risk (road type analysis)
  + 0.25 * live_traffic (from OTD counters)
  + 0.10 * crossings
  + 0.05 * incidents

Routes with >800 Fzg/h on primary/secondary/trunk roads are discarded.
Detour limits: 20% time, 25% distance.
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

# New cost formula weights (safety-first)
W_TIME = 0.35
W_OSM_RISK = 0.25
W_LIVE_TRAFFIC = 0.25
W_CROSSING = 0.10
W_INCIDENTS = 0.05

# Detour limits (more generous to allow safer routes)
MAX_TIME_FACTOR = 1.20   # 20%
MAX_DIST_FACTOR = 1.25   # 25%

# Bridge bonus
BRIDGE_BONUS = 0.06

# Traffic discard threshold
MAX_VEHICLES_PER_HOUR = 800

SAMPLE_INTERVAL_M = 15
GRID_CELL_DEG = 0.0004  # ~44m at Bern latitude


# ── Geometry helpers ────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def sample_route(coords: list, interval_m: float = SAMPLE_INTERVAL_M) -> list:
    """Sample points along a route at regular intervals.
    coords: list of [lng, lat] (GeoJSON order). Returns list of (lat, lng) tuples."""
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
            frac = 1.0 - (accum / seg_dist) if seg_dist > 0 else 1.0
            s_lat = lat1 + (lat2 - lat1) * frac
            s_lng = lon1 + (lon2 - lon1) * frac
            samples.append((s_lat, s_lng))
    samples.append((coords[-1][1], coords[-1][0]))
    return samples


def within_radius(lat1, lon1, lat2, lon2, radius_m):
    return haversine(lat1, lon1, lat2, lon2) <= radius_m


# ── Spatial grid for fast lookups ──────────────────────────

def _cell(lat, lon):
    return (int(lat / GRID_CELL_DEG), int(lon / GRID_CELL_DEG))


def build_grid(osm):
    grid = {}
    way_store = {}

    for i, w in enumerate(osm.get("ways", [])):
        way_store[i] = w
        for g in w.get("geometry", []):
            c = _cell(g["lat"], g["lon"])
            bucket = grid.setdefault(c, {"wids": set(), "cross": [], "stat": []})
            bucket["wids"].add(i)

    for p in osm.get("crossings", []):
        c = _cell(p["lat"], p["lon"])
        grid.setdefault(c, {"wids": set(), "cross": [], "stat": []})["cross"].append(p)

    for p in osm.get("stations", []):
        c = _cell(p["lat"], p["lon"])
        grid.setdefault(c, {"wids": set(), "cross": [], "stat": []})["stat"].append(p)

    return grid, way_store


def _grid_nearby(pt, grid, way_store):
    lat, lng = pt
    c = _cell(lat, lng)
    wids = set()
    crosses = []
    stats = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            b = grid.get((c[0] + dx, c[1] + dy))
            if b:
                wids.update(b["wids"])
                crosses.extend(b["cross"])
                stats.extend(b["stat"])
    return [way_store[w] for w in wids if w in way_store], crosses, stats


# ── Scoring ────────────────────────────────────────────────

def _score_sample_osm(pt, ways, crosses, stats):
    """Return (risk_add, safe_sub, crossing_ids, has_major_road) for one sample."""
    risk = 0.0
    safe = 0.0
    cross_ids = set()
    has_major_road = False

    for w in ways:
        hw = w.get("tags", {}).get("highway", "")
        if hw == "trunk":
            risk += 1.5
            has_major_road = True
        elif hw == "primary":
            risk += 1.2
            has_major_road = True
        elif hw == "secondary":
            risk += 0.8
            has_major_road = True
        elif hw == "tertiary":
            risk += 0.4
        elif hw in ("footway", "pedestrian", "living_street"):
            safe += 0.8
        elif hw == "cycleway":
            safe += 0.3

    for s in stats:
        tags = s.get("tags", {})
        if tags.get("railway") == "station":
            risk += 1.0
        elif tags.get("amenity") == "bus_station":
            risk += 0.5

    for c in crosses:
        cid = f"{c['lat']:.5f},{c['lon']:.5f}"
        cross_ids.add(cid)

    return risk, safe, cross_ids, has_major_road


def _check_major_road_traffic(samples, grid, way_store, traffic_data):
    """Check if route passes through major roads with >800 veh/h. Returns True if should discard."""
    if not traffic_data or traffic_data.get("vehicles_per_hour", 0) == 0:
        return False

    vph = traffic_data.get("vehicles_per_hour", 0)
    major_road_samples = 0
    total_samples = max(len(samples), 1)

    for pt in samples:
        ways, _, _ = _grid_nearby(pt, grid, way_store)
        for w in ways:
            hw = w.get("tags", {}).get("highway", "")
            if hw in ("trunk", "primary", "secondary"):
                major_road_samples += 1
                break

    major_road_ratio = major_road_samples / total_samples

    # If >40% of route is on major roads AND traffic is above threshold
    if major_road_ratio > 0.4 and vph > MAX_VEHICLES_PER_HOUR:
        return True

    return False


def score_single_route(
    coords: list,
    distance_m: float,
    duration_s: float,
    osm: dict,
    min_duration: float,
    min_distance: float,
    bridge_bonus: bool = False,
    _grid_data=None,
    traffic_data=None,
    incidents=None,
) -> Optional[dict]:
    """Score one route. Returns None if it exceeds detour limit or has excessive traffic."""
    # Detour limit check
    if min_duration > 0 and min_distance > 0:
        over_time = duration_s > min_duration * MAX_TIME_FACTOR
        over_dist = distance_m > min_distance * MAX_DIST_FACTOR
        if over_time and over_dist:
            return None

    # Dynamic sample interval
    interval = SAMPLE_INTERVAL_M
    if distance_m > 5000:
        interval = 80
    elif distance_m > 2000:
        interval = 40

    samples = sample_route(coords, interval_m=interval)
    n = max(len(samples), 1)

    # Build or reuse spatial grid
    if _grid_data:
        grid, way_store = _grid_data
    else:
        grid, way_store = build_grid(osm)

    # Check if route should be discarded due to heavy traffic on major roads
    if traffic_data and _check_major_road_traffic(samples, grid, way_store, traffic_data):
        logger.info("Route discarded: heavy traffic (%d veh/h) on major roads",
                     traffic_data.get("vehicles_per_hour", 0))
        return None

    total_risk = 0.0
    total_safe = 0.0
    all_crossings = set()
    danger_zones: list = []
    major_road_count = 0

    for pt in samples:
        ways, crosses, stats = _grid_nearby(pt, grid, way_store)
        r, s, cids, has_major = _score_sample_osm(pt, ways, crosses, stats)
        total_risk += r
        total_safe += s
        all_crossings.update(cids)
        if has_major:
            major_road_count += 1
        if r >= 1.0:
            danger_zones.append({"lat": pt[0], "lng": pt[1], "risk": round(r, 1)})

    # === Normalize components to 0..1 ===

    # 1. Time penalty (0.35)
    if min_duration > 0:
        norm_time = max(0.0, min(1.0, (duration_s / min_duration - 1.0) / 0.20))
    else:
        norm_time = 0.5

    # 2. OSM road risk (0.25) - adjusted to penalize major roads more
    raw_osm = (total_risk - total_safe * 0.5) / n
    norm_osm = max(0.0, min(1.0, raw_osm / 1.5))

    # 3. Live traffic (0.25)
    if traffic_data and traffic_data.get("vehicles_per_hour", 0) > 0:
        vph = traffic_data["vehicles_per_hour"]
        # Normalize: 0 veh/h = 0.0, 800+ veh/h = 1.0
        norm_traffic = max(0.0, min(1.0, vph / MAX_VEHICLES_PER_HOUR))
        # Boost if route has many major road segments
        major_ratio = major_road_count / n
        norm_traffic = min(1.0, norm_traffic * (1.0 + major_ratio * 0.5))
        traffic_level = traffic_data.get("level", "unknown")
    else:
        norm_traffic = 0.3  # default moderate when no data
        traffic_level = "unknown"

    # 4. Crossings (0.10)
    route_km = max(0.1, distance_m / 1000)
    crossings_per_km = len(all_crossings) / route_km
    norm_crossing = min(1.0, crossings_per_km / 20.0)

    # 5. Incidents (0.05)
    incident_count = len(incidents) if incidents else 0
    norm_incidents = min(1.0, incident_count / 3.0)

    # === Total cost ===
    total_cost = (
        W_TIME * norm_time
        + W_OSM_RISK * norm_osm
        + W_LIVE_TRAFFIC * norm_traffic
        + W_CROSSING * norm_crossing
        + W_INCIDENTS * norm_incidents
    )

    if bridge_bonus:
        total_cost = max(0.0, total_cost - BRIDGE_BONUS)

    safety_pct = max(0, min(100, round(100 * (1.0 - total_cost))))

    # Merge danger zones
    merged = _merge_danger_zones(danger_zones, merge_radius_m=60)

    # Calculate detour percentage
    detour_pct = 0
    if min_duration > 0:
        detour_pct = round((duration_s / min_duration - 1.0) * 100)

    return {
        "total_cost": round(total_cost, 4),
        "safety_score": safety_pct,
        "risk_details": {
            "time_penalty": round(norm_time * 100),
            "osm_risk": round(norm_osm * 100),
            "traffic_risk": round(norm_traffic * 100),
            "crossing_risk": round(norm_crossing * 100),
            "incident_risk": round(norm_incidents * 100),
        },
        "traffic_level": traffic_level,
        "detour_pct": max(0, detour_pct),
        "danger_zones": merged,
    }


def _merge_danger_zones(zones, merge_radius_m=60):
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

def score_all_routes(
    ors_features: list,
    osm: dict,
    traffic_data_per_route: list = None,
    incidents_per_route: list = None,
) -> list:
    """Score a list of ORS GeoJSON features with optional traffic data."""
    if not ors_features:
        return []

    grid_data = build_grid(osm)
    min_dur = min(f["properties"]["summary"]["duration"] for f in ors_features)
    min_dist = min(f["properties"]["summary"]["distance"] for f in ors_features)

    scored = []
    for idx, feat in enumerate(ors_features):
        coords = feat["geometry"]["coordinates"]
        dist = feat["properties"]["summary"]["distance"]
        dur = feat["properties"]["summary"]["duration"]

        traffic = traffic_data_per_route[idx] if traffic_data_per_route and idx < len(traffic_data_per_route) else None
        incidents = incidents_per_route[idx] if incidents_per_route and idx < len(incidents_per_route) else None

        result = score_single_route(
            coords, dist, dur, osm, min_dur, min_dist,
            _grid_data=grid_data,
            traffic_data=traffic,
            incidents=incidents,
        )
        if result is None:
            continue

        scored.append({
            "id": f"route_{idx + 1}",
            "distance_m": round(dist),
            "duration_s": round(dur),
            "geometry": feat["geometry"],
            "safety_score": result["safety_score"],
            "total_cost": result["total_cost"],
            "is_safest": False,
            "risk_details": result["risk_details"],
            "traffic_level": result["traffic_level"],
            "detour_pct": result["detour_pct"],
            "danger_zones": result["danger_zones"],
        })

    scored.sort(key=lambda r: r["total_cost"])
    if scored:
        scored[0]["is_safest"] = True
    return scored


def score_bridge_route(
    ors_feature: dict,
    osm: dict,
    min_dur: float,
    min_dist: float,
    traffic_data=None,
    incidents=None,
) -> Optional[dict]:
    if not ors_feature:
        return None
    coords = ors_feature["geometry"]["coordinates"]
    dist = ors_feature["properties"]["summary"]["distance"]
    dur = ors_feature["properties"]["summary"]["duration"]

    result = score_single_route(
        coords, dist, dur, osm, min_dur, min_dist,
        bridge_bonus=True,
        traffic_data=traffic_data,
        incidents=incidents,
    )
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
        "traffic_level": result["traffic_level"],
        "detour_pct": result["detour_pct"],
        "danger_zones": result["danger_zones"],
        "via_bridge": True,
    }
