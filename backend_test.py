"""
Comprehensive backend API testing for SafeWay Bern app.
Tests all endpoints including new ORS-based routing system.
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

class SafeWayAPITester:
    def __init__(self, base_url="https://safesteps-bern.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_data = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.session = requests.Session()
        
    def log_result(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name} - {details}")
        else:
            print(f"❌ {test_name} - {details}")
        
        self.test_results.append({
            "test": test_name,
            "passed": success,
            "details": details,
            "response_data": response_data
        })
    
    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if headers:
            test_headers.update(headers)
        if self.token and not headers:
            test_headers['Authorization'] = f'Bearer {self.token}'
            
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers)
            else:
                self.log_result(name, False, f"Unsupported method: {method}")
                return False, {}
            
            success = response.status_code == expected_status
            response_json = response.json() if response.content else {}
            
            self.log_result(
                name, success, 
                f"Status: {response.status_code} (expected {expected_status})",
                response_json if success else {"error": response.text[:200]}
            )
            
            return success, response_json
            
        except requests.exceptions.RequestException as e:
            self.log_result(name, False, f"Request error: {str(e)}")
            return False, {}
        except json.JSONDecodeError as e:
            self.log_result(name, False, f"JSON decode error: {str(e)}, Response: {response.text[:200]}")
            return False, {}
        except Exception as e:
            self.log_result(name, False, f"Unexpected error: {str(e)}")
            return False, {}
    
    def test_auth_register(self) -> bool:
        """Test user registration"""
        timestamp = datetime.now().strftime("%H%M%S")
        test_email = f"testuser_{timestamp}@safeway.ch"
        test_password = "TestPass123!"
        test_name = f"TestUser_{timestamp}"
        
        success, response = self.run_test(
            "User Registration",
            "POST", 
            "auth/register",
            200,
            {"email": test_email, "password": test_password, "name": test_name}
        )
        
        if success and 'token' in response and 'user' in response:
            self.token = response['token']
            self.user_data = response['user']
            return True
        return False
    
    def test_auth_login(self) -> bool:
        """Test existing user login"""
        success, response = self.run_test(
            "User Login (existing)",
            "POST",
            "auth/login", 
            200,
            {"email": "test2@safeway.ch", "password": "test123"}
        )
        
        if success and 'token' in response:
            # Keep registration token for new user tests, just verify login works
            return True
        return False
    
    def test_auth_me(self) -> bool:
        """Test getting current user info"""
        if not self.token:
            self.log_result("Get Current User", False, "No auth token available")
            return False
            
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        
        return success and 'id' in response and 'email' in response
    
    def test_get_schools(self) -> list:
        """Test getting schools list"""
        success, response = self.run_test(
            "Get Schools",
            "GET",
            "schools",
            200
        )
        
        if success and isinstance(response, list):
            school_count = len(response)
            self.log_result("Schools Count Check", school_count == 15, f"Got {school_count} schools (expected 15)")
            
            # Validate school structure
            if response:
                sample_school = response[0]
                required_fields = ['id', 'name', 'address', 'lat', 'lng', 'type']
                has_all_fields = all(field in sample_school for field in required_fields)
                self.log_result("School Data Structure", has_all_fields, "All required fields present")
                
            return response if success else []
        
        return []
    
    def test_get_environment(self) -> bool:
        """Test environment status endpoint"""
        success, response = self.run_test(
            "Get Environment Status",
            "GET",
            "environment/status",
            200
        )
        
        if success:
            # Check expected structure
            expected_keys = ['weather', 'air_quality', 'aare', 'flood', 'warnings', 'warning_level']
            has_structure = all(key in response for key in expected_keys)
            self.log_result("Environment Data Structure", has_structure, "All expected sections present")
            
            # Check for mocked data sources (as per requirements)
            weather_source = response.get('weather', {}).get('source', 'unknown')
            air_source = response.get('air_quality', {}).get('source', 'unknown') 
            aare_source = response.get('aare', {}).get('source', 'unknown')
            
            mocked_apis = []
            if weather_source == 'demo':
                mocked_apis.append('Weather')
            if air_source == 'demo':
                mocked_apis.append('AirQuality')  
            if aare_source == 'demo':
                mocked_apis.append('Aare')
                
            if mocked_apis:
                self.log_result("Mocked APIs Detection", True, f"Detected mocked: {', '.join(mocked_apis)}")
            
        return success
    
    def test_route_alternatives(self, schools: list) -> bool:
        """Test new ORS-based route alternatives endpoint"""
        if not schools:
            self.log_result("Route Alternatives", False, "No schools available for testing")
            return False
            
        # Use Bern center as start, first school as destination
        start = {"lat": 46.9480, "lng": 7.4474}
        dest = {"lat": schools[0]["lat"], "lng": schools[0]["lng"]}
        
        success, response = self.run_test(
            "Route Alternatives (ORS)",
            "POST",
            "route/alternatives",
            200,
            {"start": start, "dest": dest}
        )
        
        if success and 'routes' in response:
            routes = response['routes']
            route_count = len(routes)
            self.log_result("Route Count Check", route_count <= 3, f"Got {route_count} routes (max 3 expected)")
            
            if routes:
                # Check route structure
                sample_route = routes[0]
                required_fields = ['id', 'distance_m', 'duration_s', 'geometry', 'safety_score', 'is_safest', 'risk_details', 'danger_zones']
                has_structure = all(field in sample_route for field in required_fields)
                self.log_result("Route Data Structure", has_structure, "All required route fields present")
                
                # Check that exactly one route is marked as safest
                safest_count = sum(1 for r in routes if r.get('is_safest', False))
                self.log_result("Safest Route Flag", safest_count == 1, f"Found {safest_count} routes marked as safest")
                
                # Check safety scores are within range
                valid_scores = all(0 <= r.get('safety_score', -1) <= 100 for r in routes)
                self.log_result("Safety Score Range", valid_scores, "All safety scores within 0-100 range")
                
        return success
    
    def test_route_safest(self, schools: list) -> bool:
        """Test safest route endpoint"""
        if not schools:
            self.log_result("Route Safest", False, "No schools available for testing") 
            return False
            
        start = {"lat": 46.9480, "lng": 7.4474}
        dest = {"lat": schools[0]["lat"], "lng": schools[0]["lng"]}
        
        success, response = self.run_test(
            "Route Safest Only",
            "POST", 
            "route/safest",
            200,
            {"start": start, "dest": dest}
        )
        
        if success:
            # Should be a single route object, not a list
            is_route_object = 'id' in response and 'safety_score' in response
            self.log_result("Safest Route Structure", is_route_object, "Single route object returned")
            
            # Should be marked as safest
            is_safest = response.get('is_safest', False)
            self.log_result("Safest Route Flag", is_safest, "Route marked as safest")
            
        return success
    
    def test_legacy_route_calculate(self, schools: list) -> bool:
        """Test legacy routes/calculate endpoint with school_id"""
        if not schools:
            self.log_result("Legacy Route Calculate", False, "No schools available for testing")
            return False
            
        success, response = self.run_test(
            "Legacy Route Calculate",
            "POST",
            "routes/calculate", 
            200,
            {
                "start_lat": 46.9480,
                "start_lng": 7.4474, 
                "school_id": schools[0]["id"],
                "departure_time": "07:30"
            }
        )
        
        if success:
            # Check legacy response structure
            expected_keys = ['routes', 'school', 'start', 'routing_source', 'data_sources']
            has_structure = all(key in response for key in expected_keys)
            self.log_result("Legacy Response Structure", has_structure, "All expected legacy fields present")
            
            # Check routes have legacy fields
            routes = response.get('routes', [])
            if routes:
                sample_route = routes[0] 
                has_legacy_fields = 'duration_minutes' in sample_route and 'eta' in sample_route
                self.log_result("Legacy Route Fields", has_legacy_fields, "duration_minutes and eta fields present")
                
                # Check routing source indicates ORS
                routing_source = response.get('routing_source', '')
                is_ors = 'ors' in routing_source.lower()
                self.log_result("ORS Source Check", is_ors, f"Routing source: {routing_source}")
        
        return success
    
    def test_save_and_manage_routes(self) -> bool:
        """Test saving and managing routes (requires auth)"""
        if not self.token:
            self.log_result("Save Route", False, "No auth token available")
            return False
            
        # Save a test route
        test_route_data = {
            "id": "test_route_123",
            "distance_m": 1500,
            "duration_s": 900,
            "safety_score": 85,
            "geometry": {"type": "LineString", "coordinates": [[7.4474, 46.9480], [7.4489, 46.9555]]}
        }
        
        success, response = self.run_test(
            "Save Route",
            "POST",
            "routes/save",
            200,
            {"route_name": "Test Saved Route", "route_data": test_route_data}
        )
        
        saved_route_id = None
        if success and 'id' in response:
            saved_route_id = response['id']
            
        # Get saved routes
        success2, response2 = self.run_test(
            "Get Saved Routes",
            "GET", 
            "routes/saved",
            200
        )
        
        found_route = False
        if success2 and isinstance(response2, list):
            found_route = any(r.get('id') == saved_route_id for r in response2)
            self.log_result("Find Saved Route", found_route, f"Saved route found in list")
        
        # Delete saved route
        if saved_route_id:
            success3, _ = self.run_test(
                "Delete Saved Route",
                "DELETE",
                f"routes/saved/{saved_route_id}",
                200
            )
            
            return success and success2 and success3
        
        return success and success2
    
    def test_invalid_requests(self) -> bool:
        """Test error handling for invalid requests"""
        # Test invalid route coordinates  
        success1, _ = self.run_test(
            "Invalid Route Coordinates",
            "POST",
            "route/alternatives",
            400,  # Expect client error
            {"start": {"lat": "invalid"}, "dest": {"lat": 46.9555, "lng": 7.4489}}
        )
        
        # Test non-existent school
        success2, _ = self.run_test(
            "Non-existent School",
            "POST", 
            "routes/calculate",
            404,
            {
                "start_lat": 46.9480,
                "start_lng": 7.4474,
                "school_id": "non_existent_school", 
                "departure_time": "07:30"
            }
        )
        
        # Test unauthorized access to protected endpoint
        temp_token = self.token
        self.token = None
        success3, _ = self.run_test(
            "Unauthorized Route Save",
            "POST",
            "routes/save", 
            401,
            {"route_name": "Test", "route_data": {}}
        )
        self.token = temp_token  # Restore token
        
        return success1 and success2 and success3
    
    def run_all_tests(self) -> dict:
        """Run comprehensive test suite"""
        print("🚀 Starting SafeWay Bern API Testing...")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        start_time = time.time()
        
        # Authentication tests
        print("\n📋 Authentication Tests")
        self.test_auth_register()
        self.test_auth_login() 
        self.test_auth_me()
        
        # Core data tests
        print("\n📋 Core Data Tests") 
        schools = self.test_get_schools()
        self.test_get_environment()
        
        # Route calculation tests (new ORS-based)
        print("\n📋 Route Calculation Tests (ORS)")
        self.test_route_alternatives(schools)
        self.test_route_safest(schools)
        self.test_legacy_route_calculate(schools)
        
        # Route management tests
        print("\n📋 Route Management Tests")
        self.test_save_and_manage_routes()
        
        # Error handling tests
        print("\n📋 Error Handling Tests")
        self.test_invalid_requests()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results Summary")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print(f"Duration: {duration:.2f} seconds")
        
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed, 
            "failed_tests": self.tests_run - self.tests_passed,
            "success_rate": self.tests_passed / self.tests_run * 100 if self.tests_run > 0 else 0,
            "duration_seconds": duration,
            "detailed_results": self.test_results
        }

def main():
    """Main test execution"""
    tester = SafeWayAPITester("https://safesteps-bern.preview.emergentagent.com")
    results = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if results["failed_tests"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())