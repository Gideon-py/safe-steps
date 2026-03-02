"""Unit tests for route_safety_service.py"""

import math
import pytest
from route_safety_service import (
    haversine,
    sample_route,
    score_single_route,
    hotspot_proximity,
    find_bridges_in_corridor,
    score_all_routes,
    _merge_danger_zones,
    SAMPLE_INTERVAL_M,
    MAX_TIME_FACTOR,
    MAX_DIST_FACTOR,
    BRIDGE_BONUS,
    W_TIME,
    W_TRAFFIC,
    W_CROSSING,
    W_HOTSPOT,
)


# ── Fixtures ────────────────────────────────────────────────

def _line(start_lng, start_lat, end_lng, end_lat, n=20):
    """Generate a straight-line coordinate list in GeoJSON [lng, lat] order."""
    return [
        [
            start_lng + (end_lng - start_lng) * i / n,
            start_lat + (end_lat - start_lat) * i / n,
        ]
        for i in range(n + 1)
    ]


BERN_START = [7.4474, 46.9480]  # Bern center
BERN_END = [7.4489, 46.9555]    # Breitenrain school
SHORT_ROUTE = _line(*BERN_START, *BERN_END, n=30)

EMPTY_OSM = {"ways": [], "crossings": [], "bridges": [], "stations": []}

# A "dangerous" OSM dataset with a trunk road along the route
DANGER_OSM = {
    "ways": [
        {
            "tags": {"highway": "trunk"},
            "geometry": [
                {"lat": 46.9500, "lon": 7.4480},
                {"lat": 46.9520, "lon": 7.4484},
            ],
        }
    ],
    "crossings": [{"lat": 46.9510, "lon": 7.4482, "tags": {"highway": "crossing"}}],
    "bridges": [],
    "stations": [{"lat": 46.9505, "lon": 7.4478, "tags": {"railway": "station"}}],
}

# Safe OSM data – footway only
SAFE_OSM = {
    "ways": [
        {
            "tags": {"highway": "footway"},
            "geometry": [
                {"lat": 46.9500, "lon": 7.4480},
                {"lat": 46.9520, "lon": 7.4484},
            ],
        }
    ],
    "crossings": [],
    "bridges": [],
    "stations": [],
}


# ── Tests ───────────────────────────────────────────────────

class TestHaversine:
    def test_zero_distance(self):
        assert haversine(46.95, 7.44, 46.95, 7.44) == 0.0

    def test_known_distance(self):
        # Bern Hbf to Bern Bundeshaus ~450 m
        d = haversine(46.9490, 7.4390, 46.9470, 7.4437)
        assert 200 < d < 600

    def test_symmetry(self):
        d1 = haversine(46.95, 7.44, 46.96, 7.45)
        d2 = haversine(46.96, 7.45, 46.95, 7.44)
        assert abs(d1 - d2) < 0.01


class TestSampleRoute:
    def test_minimum_points(self):
        samples = sample_route(SHORT_ROUTE)
        assert len(samples) >= 2  # at least start + end

    def test_includes_endpoints(self):
        samples = sample_route(SHORT_ROUTE)
        start_lat, start_lng = SHORT_ROUTE[0][1], SHORT_ROUTE[0][0]
        end_lat, end_lng = SHORT_ROUTE[-1][1], SHORT_ROUTE[-1][0]
        assert abs(samples[0][0] - start_lat) < 0.0001
        assert abs(samples[-1][0] - end_lat) < 0.0001

    def test_interval_approximate(self):
        samples = sample_route(SHORT_ROUTE, interval_m=50)
        for i in range(1, len(samples) - 1):
            d = haversine(samples[i][0], samples[i][1], samples[i - 1][0], samples[i - 1][1])
            # Allow up to 2x interval due to sampling
            assert d < 120, f"Gap too large: {d}"

    def test_empty_coords(self):
        assert sample_route([]) == []

    def test_single_point(self):
        assert sample_route([[7.44, 46.95]]) == []


class TestDetourLimit:
    def test_within_limit(self):
        """Route within 15% time should be scored."""
        result = score_single_route(
            SHORT_ROUTE, 1000, 700,
            EMPTY_OSM, min_duration=650, min_distance=900,
        )
        assert result is not None

    def test_exceeds_limit(self):
        """Route exceeding both 15% time AND 20% distance should be discarded."""
        result = score_single_route(
            SHORT_ROUTE, 1300, 800,
            EMPTY_OSM, min_duration=650, min_distance=900,
        )
        assert result is None

    def test_time_ok_distance_over(self):
        """Over distance but within time should pass (OR logic)."""
        result = score_single_route(
            SHORT_ROUTE, 1500, 700,
            EMPTY_OSM, min_duration=650, min_distance=900,
        )
        assert result is not None  # time is within 15%

    def test_distance_ok_time_over(self):
        """Over time but within distance should pass."""
        result = score_single_route(
            SHORT_ROUTE, 1000, 900,
            EMPTY_OSM, min_duration=650, min_distance=900,
        )
        assert result is not None  # distance within 20%


class TestRiskScoring:
    def test_empty_osm_baseline(self):
        """With no OSM data, score should be moderate-high (mainly hotspot proximity)."""
        result = score_single_route(SHORT_ROUTE, 1000, 600, EMPTY_OSM, 600, 1000)
        assert result is not None
        assert 50 <= result["safety_score"] <= 100

    def test_dangerous_road_lowers_score(self):
        """Trunk road + station should lower safety score."""
        safe_result = score_single_route(SHORT_ROUTE, 1000, 600, SAFE_OSM, 600, 1000)
        danger_result = score_single_route(SHORT_ROUTE, 1000, 600, DANGER_OSM, 600, 1000)
        assert safe_result is not None
        assert danger_result is not None
        assert danger_result["safety_score"] < safe_result["safety_score"]

    def test_safe_road_improves_score(self):
        """Footway should improve safety score vs. no data."""
        empty_result = score_single_route(SHORT_ROUTE, 1000, 600, EMPTY_OSM, 600, 1000)
        safe_result = score_single_route(SHORT_ROUTE, 1000, 600, SAFE_OSM, 600, 1000)
        assert safe_result is not None
        assert empty_result is not None
        assert safe_result["safety_score"] >= empty_result["safety_score"]


class TestSafetyFormula:
    def test_weights_sum_to_one(self):
        assert abs(W_TIME + W_TRAFFIC + W_CROSSING + W_HOTSPOT - 1.0) < 0.001

    def test_score_range(self):
        result = score_single_route(SHORT_ROUTE, 1000, 600, EMPTY_OSM, 600, 1000)
        assert 0 <= result["safety_score"] <= 100

    def test_fastest_has_zero_time_penalty(self):
        result = score_single_route(SHORT_ROUTE, 1000, 600, EMPTY_OSM, 600, 1000)
        assert result["risk_details"]["time_penalty"] == 0


class TestBridgeBonus:
    def test_bridge_improves_score(self):
        base = score_single_route(SHORT_ROUTE, 1000, 600, EMPTY_OSM, 600, 1000, bridge_bonus=False)
        bonus = score_single_route(SHORT_ROUTE, 1000, 600, EMPTY_OSM, 600, 1000, bridge_bonus=True)
        assert bonus["safety_score"] >= base["safety_score"]
        assert bonus["total_cost"] <= base["total_cost"]


class TestBridgeDetection:
    def test_no_bridges(self):
        found = find_bridges_in_corridor(SHORT_ROUTE, EMPTY_OSM, corridor_m=100)
        assert found == []

    def test_bridge_within_corridor(self):
        osm_with_bridge = {
            **EMPTY_OSM,
            "bridges": [
                {
                    "tags": {"highway": "footway", "bridge": "yes"},
                    "geometry": [
                        {"lat": 46.9510, "lon": 7.4480},
                        {"lat": 46.9515, "lon": 7.4485},
                    ],
                }
            ],
        }
        found = find_bridges_in_corridor(SHORT_ROUTE, osm_with_bridge, corridor_m=100)
        assert len(found) >= 1

    def test_bridge_outside_corridor(self):
        osm_far = {
            **EMPTY_OSM,
            "bridges": [
                {
                    "tags": {"highway": "footway", "bridge": "yes"},
                    "geometry": [
                        {"lat": 46.9800, "lon": 7.5000},
                        {"lat": 46.9810, "lon": 7.5010},
                    ],
                }
            ],
        }
        found = find_bridges_in_corridor(SHORT_ROUTE, osm_far, corridor_m=100)
        assert found == []


class TestMergeDangerZones:
    def test_empty(self):
        assert _merge_danger_zones([]) == []

    def test_no_merge_needed(self):
        zones = [
            {"lat": 46.95, "lng": 7.44, "risk": 1.5},
            {"lat": 46.96, "lng": 7.45, "risk": 1.0},
        ]
        merged = _merge_danger_zones(zones, merge_radius_m=60)
        assert len(merged) == 2

    def test_merge_close_zones(self):
        zones = [
            {"lat": 46.9500, "lng": 7.4480, "risk": 1.5},
            {"lat": 46.9501, "lng": 7.4481, "risk": 1.0},
        ]
        merged = _merge_danger_zones(zones, merge_radius_m=60)
        assert len(merged) == 1


class TestScoreAllRoutes:
    def test_empty(self):
        assert score_all_routes([], EMPTY_OSM) == []

    def test_safest_flagged(self):
        features = [
            {
                "geometry": {"type": "LineString", "coordinates": SHORT_ROUTE},
                "properties": {"summary": {"distance": 1000, "duration": 600}},
            },
            {
                "geometry": {"type": "LineString", "coordinates": SHORT_ROUTE},
                "properties": {"summary": {"distance": 1100, "duration": 660}},
            },
        ]
        scored = score_all_routes(features, EMPTY_OSM)
        assert len(scored) >= 1
        safest_count = sum(1 for r in scored if r["is_safest"])
        assert safest_count == 1


class TestHotspotProximity:
    def test_far_from_hotspots(self):
        # Points far away from Bern
        far = [(47.5, 8.0), (47.6, 8.1)]
        assert hotspot_proximity(far) < 0.1

    def test_near_hotspot(self):
        # Right at Bahnhof Bern
        near = [(46.9490, 7.4390)]
        assert hotspot_proximity(near) > 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
