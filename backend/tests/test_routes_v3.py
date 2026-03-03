"""
Backend API Tests for SafeSteps Bern - v3 Update
Tests new features: OTD traffic integration, updated safety scoring, risk_details fields

Test Coverage:
- POST /api/routes/calculate - new risk_details fields (osm_risk, traffic_risk, crossing_risk, time_penalty, incident_risk)
- traffic_level and detour_pct fields in routes
- data_sources includes traffic source info
- POST /api/route/alternatives and /api/route/safest endpoints
- POST /api/auth/register and POST /api/auth/login
- GET /api/schools returns 15 schools
- GET /api/environment/status returns weather data
"""

import pytest
import requests
import os
from datetime import datetime
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_START_POINT = {"lat": 46.948, "lng": 7.447}  # Near Bern center
TEST_SCHOOL_ID = "school_01"  # Schulhaus Breitenrain
TEST_USER_EMAIL = f"test_iter3_{int(time.time())}@test.com"
TEST_USER_PASSWORD = "test1234"


@pytest.fixture(scope="module")
def api_session():
    """Create a session for API tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_session):
    """Register a new user and get auth token"""
    response = api_session.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "name": "Test User Iter3"
        }
    )
    if response.status_code == 200:
        return response.json().get("token")
    # If registration fails (user exists), try login with test credentials
    response = api_session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "test@test.com", "password": "test1234"}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Unable to get authentication token")


class TestAuthEndpoints:
    """Test authentication endpoints"""

    def test_register_new_user(self, api_session):
        """Test user registration with unique email"""
        unique_email = f"test_reg_{int(time.time())}@test.com"
        response = api_session.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "testpass123",
                "name": "Test Registration"
            }
        )
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        assert data["user"]["email"] == unique_email
        print(f"✓ User registration successful: {unique_email}")

    def test_login_with_test_user(self, api_session):
        """Test login with provided test credentials"""
        response = api_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test@test.com", "password": "test1234"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        print(f"✓ Login successful for test@test.com")


class TestSchoolsEndpoint:
    """Test schools data endpoint"""

    def test_get_schools_returns_15(self, api_session):
        """GET /api/schools should return exactly 15 schools"""
        response = api_session.get(f"{BASE_URL}/api/schools")
        assert response.status_code == 200
        schools = response.json()
        assert isinstance(schools, list), "Response should be a list"
        assert len(schools) == 15, f"Expected 15 schools, got {len(schools)}"
        print(f"✓ Got {len(schools)} schools")

    def test_school_data_structure(self, api_session):
        """Verify school data has required fields"""
        response = api_session.get(f"{BASE_URL}/api/schools")
        schools = response.json()
        required_fields = ["id", "name", "address", "lat", "lng", "type"]
        for school in schools:
            for field in required_fields:
                assert field in school, f"School missing field: {field}"
        print(f"✓ All schools have required fields")

    def test_school_01_exists(self, api_session):
        """Verify school_01 (Schulhaus Breitenrain) exists"""
        response = api_session.get(f"{BASE_URL}/api/schools")
        schools = response.json()
        school_01 = next((s for s in schools if s["id"] == "school_01"), None)
        assert school_01 is not None, "school_01 not found"
        assert "Breitenrain" in school_01["name"], f"Expected Breitenrain school, got {school_01['name']}"
        print(f"✓ school_01 found: {school_01['name']}")


class TestEnvironmentEndpoint:
    """Test environment status endpoint"""

    def test_environment_status_returns_weather(self, api_session):
        """GET /api/environment/status should return weather data"""
        response = api_session.get(f"{BASE_URL}/api/environment/status")
        assert response.status_code == 200
        data = response.json()
        assert "weather" in data, "Response missing weather"
        assert "warning_level" in data, "Response missing warning_level"
        assert "warnings" in data, "Response missing warnings"
        print(f"✓ Environment status OK, warning_level: {data.get('warning_level')}")

    def test_environment_has_all_sections(self, api_session):
        """Verify all environment data sections present"""
        response = api_session.get(f"{BASE_URL}/api/environment/status")
        data = response.json()
        expected_sections = ["weather", "air_quality", "aare", "flood", "timestamp"]
        for section in expected_sections:
            assert section in data, f"Missing section: {section}"
        print(f"✓ All environment sections present")


class TestRouteCalculateEndpoint:
    """Test POST /api/routes/calculate with new v3 fields"""

    def test_calculate_returns_routes(self, api_session):
        """Test route calculation returns routes array"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": TEST_SCHOOL_ID,
                "departure_time": "07:30"
            }
        )
        assert response.status_code == 200, f"Route calculation failed: {response.text}"
        data = response.json()
        assert "routes" in data, "Response missing routes"
        routes = data["routes"]
        assert len(routes) >= 1, "Expected at least 1 route"
        assert len(routes) <= 3, f"Expected max 3 routes, got {len(routes)}"
        print(f"✓ Got {len(routes)} routes")

    def test_routes_have_risk_details(self, api_session):
        """NEW v3: Each route should have risk_details with new fields"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": TEST_SCHOOL_ID,
                "departure_time": "07:30"
            }
        )
        data = response.json()
        routes = data["routes"]
        
        # New v3 risk_details fields
        expected_risk_fields = ["osm_risk", "traffic_risk", "crossing_risk", "time_penalty", "incident_risk"]
        
        for route in routes:
            assert "risk_details" in route, f"Route {route.get('id')} missing risk_details"
            risk_details = route["risk_details"]
            for field in expected_risk_fields:
                assert field in risk_details, f"risk_details missing {field}"
                assert isinstance(risk_details[field], (int, float)), f"{field} should be numeric"
            print(f"✓ Route {route.get('id')} has risk_details: osm={risk_details['osm_risk']}, traffic={risk_details['traffic_risk']}")

    def test_routes_have_traffic_level(self, api_session):
        """NEW v3: Each route should have traffic_level field"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": TEST_SCHOOL_ID,
                "departure_time": "07:30"
            }
        )
        data = response.json()
        routes = data["routes"]
        
        valid_traffic_levels = ["low", "medium", "high", "unknown"]
        
        for route in routes:
            assert "traffic_level" in route, f"Route {route.get('id')} missing traffic_level"
            assert route["traffic_level"] in valid_traffic_levels, f"Invalid traffic_level: {route['traffic_level']}"
            print(f"✓ Route {route.get('id')} traffic_level: {route['traffic_level']}")

    def test_routes_have_detour_pct(self, api_session):
        """NEW v3: Each route should have detour_pct field"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": TEST_SCHOOL_ID,
                "departure_time": "07:30"
            }
        )
        data = response.json()
        routes = data["routes"]
        
        for route in routes:
            assert "detour_pct" in route, f"Route {route.get('id')} missing detour_pct"
            assert isinstance(route["detour_pct"], (int, float)), "detour_pct should be numeric"
            assert route["detour_pct"] >= 0, "detour_pct should be >= 0"
            print(f"✓ Route {route.get('id')} detour_pct: {route['detour_pct']}%")

    def test_data_sources_includes_traffic(self, api_session):
        """NEW v3: data_sources should include traffic source info"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": TEST_SCHOOL_ID,
                "departure_time": "07:30"
            }
        )
        data = response.json()
        assert "data_sources" in data, "Response missing data_sources"
        data_sources = data["data_sources"]
        assert "traffic" in data_sources, "data_sources missing traffic"
        print(f"✓ data_sources traffic: {data_sources.get('traffic')}")

    def test_safest_route_flagged(self, api_session):
        """Verify exactly one route is marked as safest"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": TEST_SCHOOL_ID,
                "departure_time": "07:30"
            }
        )
        data = response.json()
        routes = data["routes"]
        safest_count = sum(1 for r in routes if r.get("is_safest", False))
        assert safest_count == 1, f"Expected 1 safest route, got {safest_count}"
        safest = next(r for r in routes if r.get("is_safest"))
        print(f"✓ Safest route: {safest['id']} with score {safest['safety_score']}")


class TestRouteAlternativesEndpoint:
    """Test POST /api/route/alternatives endpoint"""

    def test_alternatives_endpoint_works(self, api_session):
        """POST /api/route/alternatives returns routes"""
        # Get a school for destination
        schools_resp = api_session.get(f"{BASE_URL}/api/schools")
        school = schools_resp.json()[0]
        
        response = api_session.post(
            f"{BASE_URL}/api/route/alternatives",
            json={
                "start": TEST_START_POINT,
                "dest": {"lat": school["lat"], "lng": school["lng"]}
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "routes" in data
        print(f"✓ Route alternatives returned {len(data['routes'])} routes")

    def test_alternatives_have_new_fields(self, api_session):
        """Verify alternatives include new v3 fields"""
        schools_resp = api_session.get(f"{BASE_URL}/api/schools")
        school = schools_resp.json()[0]
        
        response = api_session.post(
            f"{BASE_URL}/api/route/alternatives",
            json={
                "start": TEST_START_POINT,
                "dest": {"lat": school["lat"], "lng": school["lng"]}
            }
        )
        data = response.json()
        routes = data["routes"]
        
        for route in routes:
            assert "risk_details" in route
            assert "traffic_level" in route
            assert "detour_pct" in route
        print(f"✓ All alternative routes have new v3 fields")


class TestRouteSafestEndpoint:
    """Test POST /api/route/safest endpoint"""

    def test_safest_endpoint_works(self, api_session):
        """POST /api/route/safest returns single safest route"""
        schools_resp = api_session.get(f"{BASE_URL}/api/schools")
        school = schools_resp.json()[0]
        
        response = api_session.post(
            f"{BASE_URL}/api/route/safest",
            json={
                "start": TEST_START_POINT,
                "dest": {"lat": school["lat"], "lng": school["lng"]}
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data, "Response should be a single route object"
        assert data.get("is_safest", False), "Route should be marked as safest"
        print(f"✓ Safest route endpoint works, score: {data.get('safety_score')}")


class TestInvalidSchool:
    """Test error handling for invalid school"""

    def test_nonexistent_school_returns_404(self, api_session):
        """Non-existent school_id should return 404"""
        response = api_session.post(
            f"{BASE_URL}/api/routes/calculate",
            json={
                "start_lat": TEST_START_POINT["lat"],
                "start_lng": TEST_START_POINT["lng"],
                "school_id": "nonexistent_school_xyz",
                "departure_time": "07:30"
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Non-existent school correctly returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
