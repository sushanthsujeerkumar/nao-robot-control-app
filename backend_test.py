#!/usr/bin/env python3
"""
NAO Robot Control Backend API Test Suite
Tests all backend API endpoints for the NAO Robot Control application
"""

import requests
import json
import time
import base64
from datetime import datetime
import sys

# Get backend URL from frontend/.env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('EXPO_PUBLIC_BACKEND_URL'):
                    url = line.split('=')[1].strip().strip('"')
                    return f"{url}/api"
    except:
        pass
    return "https://nao-bridge.preview.emergentagent.com/api"

BASE_URL = get_backend_url()
print(f"Testing NAO Robot Control API at: {BASE_URL}")

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")

def log_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}")

def log_info(message):
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")

def log_warning(message):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

# Global variables for test tracking
saved_robot_id = None
test_results = {
    'total_tests': 0,
    'passed_tests': 0,
    'failed_tests': 0,
    'critical_failures': []
}

def update_test_result(test_name, success, critical=False):
    """Update test results"""
    test_results['total_tests'] += 1
    if success:
        test_results['passed_tests'] += 1
        log_success(f"{test_name}")
    else:
        test_results['failed_tests'] += 1
        log_error(f"{test_name}")
        if critical:
            test_results['critical_failures'].append(test_name)

def test_health_check():
    """Test 1: Health Check - GET /api/"""
    log_info("=== Test 1: Health Check ===")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "NAO Robot Control Bridge API" in data.get("message", ""):
                update_test_result("Health check endpoint working", True)
                log_info(f"API Version: {data.get('version', 'N/A')}")
                log_info(f"Status: {data.get('status', 'N/A')}")
                return True
            else:
                update_test_result("Health check returned unexpected response", False, True)
                return False
        else:
            update_test_result(f"Health check failed with status {response.status_code}", False, True)
            return False
    except Exception as e:
        update_test_result(f"Health check failed with exception: {str(e)}", False, True)
        return False

def test_robot_config_crud():
    """Test 2: Robot Configuration CRUD operations"""
    global saved_robot_id
    log_info("=== Test 2: Robot Configuration CRUD ===")
    
    # Test POST /api/robots
    robot_data = {
        "name": "Test NAO Robot",
        "ip_address": "192.168.1.200", 
        "port": 9559
    }
    
    try:
        response = requests.post(f"{BASE_URL}/robots", json=robot_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            saved_robot_id = data.get("id")
            if saved_robot_id and data.get("name") == robot_data["name"]:
                update_test_result("Robot config creation (POST /robots)", True)
                log_info(f"Created robot with ID: {saved_robot_id}")
            else:
                update_test_result("Robot config creation returned invalid data", False, True)
                return False
        else:
            update_test_result(f"Robot config creation failed with status {response.status_code}", False, True)
            return False
    except Exception as e:
        update_test_result(f"Robot config creation failed: {str(e)}", False, True)
        return False
    
    # Test GET /api/robots
    try:
        response = requests.get(f"{BASE_URL}/robots", timeout=10)
        if response.status_code == 200:
            robots = response.json()
            if isinstance(robots, list) and len(robots) > 0:
                # Check if our robot is in the list
                found = any(robot.get("id") == saved_robot_id for robot in robots)
                if found:
                    update_test_result("Robot config retrieval (GET /robots)", True)
                    log_info(f"Retrieved {len(robots)} robot(s)")
                else:
                    update_test_result("Created robot not found in list", False)
            else:
                update_test_result("Robot config retrieval returned empty or invalid data", False)
        else:
            update_test_result(f"Robot config retrieval failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Robot config retrieval failed: {str(e)}", False, True)
    
    # Test DELETE /api/robots/{id} (we'll do this at the end)
    return True

def test_robot_connection():
    """Test 3: Robot Connection"""
    log_info("=== Test 3: Robot Connection ===")
    
    # Test POST /api/robot/connect
    connection_data = {
        "ip_address": "192.168.1.100",
        "port": 9559
    }
    
    try:
        response = requests.post(f"{BASE_URL}/robot/connect", json=connection_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "Connected to robot" in data.get("message", ""):
                update_test_result("Robot connection (POST /robot/connect)", True)
                log_info(f"Connected to robot at {connection_data['ip_address']}:{connection_data['port']}")
                
                # Check status data
                status = data.get("status", {})
                if status.get("connected"):
                    log_info(f"Battery: {status.get('battery_level', 'N/A')}%")
                    log_info(f"Temperature: {status.get('temperature', 'N/A')}°C")
                    log_info(f"Posture: {status.get('posture', 'N/A')}")
                return True
            else:
                update_test_result("Robot connection returned failure", False, True)
                return False
        else:
            update_test_result(f"Robot connection failed with status {response.status_code}", False, True)
            return False
    except Exception as e:
        update_test_result(f"Robot connection failed: {str(e)}", False, True)
        return False

def test_robot_status():
    """Test robot status endpoint"""
    log_info("=== Test: Robot Status ===")
    
    try:
        response = requests.get(f"{BASE_URL}/robot/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("connected") == True:
                update_test_result("Robot status check (GET /robot/status)", True)
                log_info(f"Robot Name: {data.get('robot_name', 'N/A')}")
                log_info(f"Battery: {data.get('battery_level', 'N/A')}%")
                log_info(f"Uptime: {data.get('uptime', 'N/A')} seconds")
                return True
            else:
                update_test_result("Robot status shows disconnected", False)
                return False
        else:
            update_test_result(f"Robot status failed with status {response.status_code}", False, True)
            return False
    except Exception as e:
        update_test_result(f"Robot status failed: {str(e)}", False, True)
        return False

def test_movement_control():
    """Test 4: Movement Control"""
    log_info("=== Test 4: Movement Control ===")
    
    # Test forward movement
    try:
        move_data = {"x": 0.5, "y": 0, "theta": 0}
        response = requests.post(f"{BASE_URL}/robot/move", json=move_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Forward movement (POST /robot/move)", True)
                log_info(f"Movement result: {data.get('message', 'N/A')}")
            else:
                update_test_result("Forward movement returned failure", False)
        else:
            update_test_result(f"Forward movement failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Forward movement failed: {str(e)}", False, True)
    
    # Test turning
    try:
        move_data = {"x": 0, "y": 0, "theta": 0.5}
        response = requests.post(f"{BASE_URL}/robot/move", json=move_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Turn movement (POST /robot/move)", True)
                log_info(f"Turn result: {data.get('message', 'N/A')}")
            else:
                update_test_result("Turn movement returned failure", False)
        else:
            update_test_result(f"Turn movement failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Turn movement failed: {str(e)}", False, True)
    
    # Test stop
    try:
        response = requests.post(f"{BASE_URL}/robot/stop", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Stop movement (POST /robot/stop)", True)
                log_info("Robot stopped successfully")
            else:
                update_test_result("Stop movement returned failure", False)
        else:
            update_test_result(f"Stop movement failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Stop movement failed: {str(e)}", False, True)

def test_speech_control():
    """Test 5: Speech Control"""
    log_info("=== Test 5: Speech Control ===")
    
    try:
        speech_data = {"text": "Hello world", "language": "en", "volume": 1.0}
        response = requests.post(f"{BASE_URL}/robot/speak", json=speech_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Speech synthesis (POST /robot/speak)", True)
                log_info(f"Speech result: {data.get('message', 'N/A')}")
                log_info(f"Duration: {data.get('duration', 'N/A')} seconds")
            else:
                update_test_result("Speech synthesis returned failure", False)
        else:
            update_test_result(f"Speech synthesis failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Speech synthesis failed: {str(e)}", False, True)

def test_gesture_control():
    """Test 6: Gesture Control"""
    log_info("=== Test 6: Gesture Control ===")
    
    # Test GET /api/robot/gestures
    try:
        response = requests.get(f"{BASE_URL}/robot/gestures", timeout=10)
        if response.status_code == 200:
            data = response.json()
            gestures = data.get("gestures", [])
            if gestures and len(gestures) > 0:
                update_test_result("Gesture list retrieval (GET /robot/gestures)", True)
                log_info(f"Available gestures: {len(gestures)}")
                for gesture in gestures[:3]:  # Show first 3
                    log_info(f"  - {gesture.get('name', 'N/A')}: {gesture.get('description', 'N/A')}")
            else:
                update_test_result("Gesture list returned empty", False)
        else:
            update_test_result(f"Gesture list failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Gesture list failed: {str(e)}", False, True)
    
    # Test wave gesture
    try:
        gesture_data = {"gesture_name": "wave", "speed": 1.0}
        response = requests.post(f"{BASE_URL}/robot/gesture", json=gesture_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Wave gesture execution (POST /robot/gesture)", True)
                log_info(f"Wave gesture: {data.get('message', 'N/A')}")
            else:
                update_test_result("Wave gesture returned failure", False)
        else:
            update_test_result(f"Wave gesture failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Wave gesture failed: {str(e)}", False, True)
    
    # Test sit gesture
    try:
        gesture_data = {"gesture_name": "sit", "speed": 1.0}
        response = requests.post(f"{BASE_URL}/robot/gesture", json=gesture_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Sit gesture execution (POST /robot/gesture)", True)
                log_info(f"Sit gesture: {data.get('message', 'N/A')}")
            else:
                update_test_result("Sit gesture returned failure", False)
        else:
            update_test_result(f"Sit gesture failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Sit gesture failed: {str(e)}", False, True)

def test_sensor_data():
    """Test 7: Sensor Data"""
    log_info("=== Test 7: Sensor Data ===")
    
    try:
        response = requests.get(f"{BASE_URL}/robot/sensors", timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Check if sensor data has expected fields
            expected_fields = ['battery_level', 'sonar_left', 'sonar_right', 'temperature_cpu']
            has_expected = all(field in data for field in expected_fields)
            
            if has_expected:
                update_test_result("Sensor data retrieval (GET /robot/sensors)", True)
                log_info(f"Battery: {data.get('battery_level', 'N/A')}%")
                log_info(f"Sonar L/R: {data.get('sonar_left', 'N/A')}/{data.get('sonar_right', 'N/A')} m")
                log_info(f"CPU Temp: {data.get('temperature_cpu', 'N/A')}°C")
                log_info(f"Head Touch: Front={data.get('head_touch_front', False)}")
            else:
                update_test_result("Sensor data missing expected fields", False, True)
        else:
            update_test_result(f"Sensor data failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Sensor data failed: {str(e)}", False, True)

def test_camera():
    """Test 8: Camera"""
    log_info("=== Test 8: Camera ===")
    
    try:
        response = requests.get(f"{BASE_URL}/robot/camera/frame", timeout=10)
        if response.status_code == 200:
            data = response.json()
            frame_data = data.get("frame", "")
            timestamp = data.get("timestamp", "")
            
            if frame_data and frame_data.startswith("data:image/jpeg;base64,"):
                # Try to decode the base64 to validate
                base64_data = frame_data.split(",")[1]
                try:
                    decoded = base64.b64decode(base64_data)
                    if len(decoded) > 0:
                        update_test_result("Camera frame retrieval (GET /robot/camera/frame)", True)
                        log_info(f"Frame size: {len(decoded)} bytes")
                        log_info(f"Timestamp: {timestamp}")
                    else:
                        update_test_result("Camera frame is empty", False)
                except:
                    update_test_result("Camera frame invalid base64", False, True)
            else:
                update_test_result("Camera frame missing or invalid format", False, True)
        else:
            update_test_result(f"Camera frame failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Camera frame failed: {str(e)}", False, True)

def test_disconnect():
    """Test 9: Disconnect"""
    log_info("=== Test 9: Disconnect ===")
    
    # Test POST /api/robot/disconnect
    try:
        response = requests.post(f"{BASE_URL}/robot/disconnect", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                update_test_result("Robot disconnect (POST /robot/disconnect)", True)
                log_info("Robot disconnected successfully")
            else:
                update_test_result("Robot disconnect returned failure", False)
        else:
            update_test_result(f"Robot disconnect failed with status {response.status_code}", False, True)
    except Exception as e:
        update_test_result(f"Robot disconnect failed: {str(e)}", False, True)
    
    # Verify disconnected state
    try:
        time.sleep(1)  # Brief pause
        response = requests.get(f"{BASE_URL}/robot/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("connected") == False:
                update_test_result("Disconnect verification (GET /robot/status)", True)
                log_info("Disconnect state verified")
            else:
                update_test_result("Robot still shows connected after disconnect", False)
        else:
            update_test_result(f"Disconnect verification failed with status {response.status_code}", False)
    except Exception as e:
        update_test_result(f"Disconnect verification failed: {str(e)}", False)

def cleanup_robot_config():
    """Cleanup: Delete saved robot configuration"""
    global saved_robot_id
    if saved_robot_id:
        log_info("=== Cleanup: Delete Robot Config ===")
        try:
            response = requests.delete(f"{BASE_URL}/robots/{saved_robot_id}", timeout=10)
            if response.status_code == 200:
                update_test_result("Robot config deletion (DELETE /robots/{id})", True)
                log_info(f"Deleted robot config: {saved_robot_id}")
            else:
                update_test_result(f"Robot config deletion failed with status {response.status_code}", False)
        except Exception as e:
            update_test_result(f"Robot config deletion failed: {str(e)}", False)

def print_test_summary():
    """Print final test summary"""
    print(f"\n{Colors.BOLD}=== NAO ROBOT CONTROL API TEST SUMMARY ==={Colors.ENDC}")
    print(f"Total Tests: {test_results['total_tests']}")
    print(f"{Colors.GREEN}Passed: {test_results['passed_tests']}{Colors.ENDC}")
    print(f"{Colors.RED}Failed: {test_results['failed_tests']}{Colors.ENDC}")
    
    if test_results['critical_failures']:
        print(f"\n{Colors.RED}{Colors.BOLD}Critical Failures:{Colors.ENDC}")
        for failure in test_results['critical_failures']:
            print(f"{Colors.RED}  - {failure}{Colors.ENDC}")
    
    success_rate = (test_results['passed_tests'] / test_results['total_tests'] * 100) if test_results['total_tests'] > 0 else 0
    print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.ENDC}")
    
    if test_results['critical_failures']:
        print(f"\n{Colors.RED}❌ BACKEND HAS CRITICAL ISSUES{Colors.ENDC}")
        return False
    elif test_results['failed_tests'] > 0:
        print(f"\n{Colors.YELLOW}⚠️  BACKEND HAS MINOR ISSUES{Colors.ENDC}")
        return True
    else:
        print(f"\n{Colors.GREEN}✅ ALL BACKEND TESTS PASSED{Colors.ENDC}")
        return True

def main():
    """Main test execution"""
    print(f"{Colors.BOLD}NAO Robot Control Backend API Test Suite{Colors.ENDC}")
    print(f"Testing backend at: {BASE_URL}")
    print("-" * 60)
    
    # Run tests in sequence as requested
    if not test_health_check():
        print(f"{Colors.RED}❌ Health check failed - aborting tests{Colors.ENDC}")
        return False
    
    # Robot Config CRUD
    test_robot_config_crud()
    
    # Robot Connection
    if test_robot_connection():
        test_robot_status()
        
        # Movement Control
        test_movement_control()
        
        # Speech Control
        test_speech_control()
        
        # Gesture Control
        test_gesture_control()
        
        # Sensor Data
        test_sensor_data()
        
        # Camera
        test_camera()
        
        # Disconnect
        test_disconnect()
    else:
        log_error("Robot connection failed - skipping dependent tests")
    
    # Cleanup
    cleanup_robot_config()
    
    # Print summary
    return print_test_summary()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)