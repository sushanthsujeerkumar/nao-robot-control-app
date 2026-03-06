from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import asyncio
import json
import base64
import io
import socket
import paramiko
import threading
import time

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="NAO Robot Control Bridge")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== Models ====================

class RobotConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    ip_address: str
    port: int = 9559
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_connected: Optional[datetime] = None

class RobotConfigCreate(BaseModel):
    name: str
    ip_address: str
    port: int = 9559

class RobotConnection(BaseModel):
    ip_address: str
    port: int = 9559
    username: str = "nao"
    password: str = "nao"

class MoveCommand(BaseModel):
    x: float
    y: float
    theta: float

class SpeechCommand(BaseModel):
    text: str
    language: str = "en"
    volume: float = 1.0

class GestureCommand(BaseModel):
    gesture_name: str
    speed: float = 1.0

class RobotStatus(BaseModel):
    connected: bool
    ip_address: Optional[str] = None
    battery_level: int = 0
    temperature: float = 0.0
    robot_name: str = "NAO"
    uptime: int = 0
    posture: str = "Unknown"
    connection_mode: str = "none"

class SensorData(BaseModel):
    head_touch_front: bool = False
    head_touch_middle: bool = False
    head_touch_rear: bool = False
    left_hand_touch: bool = False
    right_hand_touch: bool = False
    sonar_left: float = 0.0
    sonar_right: float = 0.0
    battery_level: int = 100
    head_yaw: float = 0.0
    head_pitch: float = 0.0
    left_shoulder_pitch: float = 0.0
    right_shoulder_pitch: float = 0.0
    temperature_cpu: float = 40.0
    temperature_battery: float = 35.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ==================== NAO Robot Controller via SSH ====================

class NAORobotSSHController:
    """Controls a real NAO robot via SSH and NAOqi Python commands"""
    
    def __init__(self):
        self.connected = False
        self.ip_address = None
        self.port = 9559
        self.ssh_client = None
        self.username = "nao"
        self.password = "nao"
        self._start_time = None
        self.connection_mode = "none"
        self._cache = {}
        self._cache_time = {}
        
    def _check_robot_reachable(self, ip: str, port: int, timeout: float = 3.0) -> bool:
        """Check if robot is reachable on the network"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.error(f"Network check failed: {e}")
            return False
    
    def _check_ssh_reachable(self, ip: str, timeout: float = 3.0) -> bool:
        """Check if SSH port is reachable"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, 22))
            sock.close()
            return result == 0
        except Exception as e:
            logger.error(f"SSH check failed: {e}")
            return False
    
    def _execute_on_robot(self, python_code: str, timeout: float = 10.0) -> tuple:
        """Execute Python code on the NAO robot via SSH"""
        if not self.ssh_client:
            return None, "Not connected"
        
        # Wrap code in a Python command
        full_code = f'''python2 << 'NAOCODE'
# -*- coding: utf-8 -*-
from naoqi import ALProxy
import json

robot_ip = "127.0.0.1"
port = 9559

try:
{self._indent_code(python_code)}
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
NAOCODE'''
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(full_code, timeout=timeout)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            return output, error
        except Exception as e:
            logger.error(f"SSH command failed: {e}")
            return None, str(e)
    
    def _indent_code(self, code: str, spaces: int = 4) -> str:
        """Indent code for embedding in try block"""
        return '\n'.join(' ' * spaces + line for line in code.split('\n'))
    
    def connect(self, ip_address: str, port: int, username: str = "nao", password: str = "nao") -> dict:
        """Connect to the NAO robot via SSH"""
        self.ip_address = ip_address
        self.port = port
        self.username = username
        self.password = password
        
        logger.info(f"Attempting to connect to NAO at {ip_address}...")
        
        # Check NAOqi port
        if not self._check_robot_reachable(ip_address, port):
            return {
                "success": False,
                "message": f"Cannot reach NAOqi at {ip_address}:{port}. Please check:\n"
                           "1. Robot is powered on\n"
                           "2. Robot and this device are on the same network\n"
                           "3. IP address is correct (press NAO's chest button to hear IP)",
                "connected": False
            }
        
        logger.info(f"NAOqi port {port} is reachable")
        
        # Check SSH port
        if not self._check_ssh_reachable(ip_address):
            return {
                "success": False,
                "message": f"Cannot reach SSH at {ip_address}:22. SSH access is required.",
                "connected": False
            }
        
        logger.info("SSH port 22 is reachable")
        
        # Try SSH connection
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                ip_address, 
                port=22, 
                username=username, 
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            logger.info("SSH connection established")
            
            # Test NAOqi connection
            test_code = '''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
print(json.dumps({"success": True, "message": "Connected"}))
'''
            output, error = self._execute_on_robot(test_code)
            
            if output and "success" in output:
                self.connected = True
                self._start_time = datetime.utcnow()
                self.connection_mode = "ssh"
                
                # Make robot say connected
                self._execute_on_robot('''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.say("Connected to remote control")
''')
                
                return {
                    "success": True,
                    "message": f"Successfully connected to NAO at {ip_address}",
                    "connected": True,
                    "mode": "ssh"
                }
            else:
                self.ssh_client.close()
                self.ssh_client = None
                return {
                    "success": False,
                    "message": f"SSH connected but NAOqi test failed: {error or output}",
                    "connected": False
                }
                
        except paramiko.AuthenticationException:
            return {
                "success": False,
                "message": f"SSH authentication failed. Default credentials are nao/nao. "
                           "Check if password was changed.",
                "connected": False
            }
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "connected": False
            }
    
    def disconnect(self):
        """Disconnect from the robot"""
        if self.ssh_client:
            try:
                self._execute_on_robot('''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.say("Disconnecting")
''')
                self.ssh_client.close()
            except:
                pass
        self.connected = False
        self.ssh_client = None
        self.connection_mode = "none"
        self._cache = {}
        logger.info("Disconnected from NAO robot")
    
    def get_status(self) -> RobotStatus:
        """Get current robot status"""
        if not self.connected:
            return RobotStatus(connected=False, connection_mode="none")
        
        uptime = 0
        if self._start_time:
            uptime = int((datetime.utcnow() - self._start_time).total_seconds())
        
        # Get battery and posture (with caching)
        battery_level = 100
        posture = "Unknown"
        temperature = 40.0
        
        try:
            code = '''
battery = ALProxy("ALBattery", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)

battery_level = battery.getBatteryCharge()
current_posture = posture.getPostureFamily()
try:
    temp = memory.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value")
except:
    temp = 40.0

print(json.dumps({
    "battery": battery_level,
    "posture": current_posture,
    "temperature": temp
}))
'''
            output, error = self._execute_on_robot(code)
            if output:
                try:
                    data = json.loads(output)
                    battery_level = data.get("battery", 100)
                    posture = data.get("posture", "Unknown")
                    temperature = data.get("temperature", 40.0)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error getting status: {e}")
        
        return RobotStatus(
            connected=True,
            ip_address=self.ip_address,
            battery_level=battery_level,
            temperature=temperature,
            robot_name="NAO V5",
            uptime=uptime,
            posture=posture,
            connection_mode=self.connection_mode
        )
    
    def get_sensors(self) -> SensorData:
        """Get sensor data from the robot"""
        if not self.connected:
            return SensorData()
        
        try:
            code = '''
memory = ALProxy("ALMemory", robot_ip, port)
battery = ALProxy("ALBattery", robot_ip, port)

data = {
    "head_touch_front": bool(memory.getData("Device/SubDeviceList/Head/Touch/Front/Sensor/Value")),
    "head_touch_middle": bool(memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")),
    "head_touch_rear": bool(memory.getData("Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")),
    "left_hand_touch": bool(memory.getData("Device/SubDeviceList/LHand/Touch/Back/Sensor/Value")),
    "right_hand_touch": bool(memory.getData("Device/SubDeviceList/RHand/Touch/Back/Sensor/Value")),
    "sonar_left": float(memory.getData("Device/SubDeviceList/US/Left/Sensor/Value") or 0),
    "sonar_right": float(memory.getData("Device/SubDeviceList/US/Right/Sensor/Value") or 0),
    "battery_level": int(battery.getBatteryCharge()),
    "head_yaw": float(memory.getData("Device/SubDeviceList/HeadYaw/Position/Sensor/Value") or 0),
    "head_pitch": float(memory.getData("Device/SubDeviceList/HeadPitch/Position/Sensor/Value") or 0),
    "left_shoulder_pitch": float(memory.getData("Device/SubDeviceList/LShoulderPitch/Position/Sensor/Value") or 0),
    "right_shoulder_pitch": float(memory.getData("Device/SubDeviceList/RShoulderPitch/Position/Sensor/Value") or 0),
}

try:
    data["temperature_cpu"] = float(memory.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value") or 40)
except:
    data["temperature_cpu"] = 40.0

try:
    data["temperature_battery"] = float(memory.getData("Device/SubDeviceList/Battery/Temperature/Sensor/Value") or 35)
except:
    data["temperature_battery"] = 35.0

print(json.dumps(data))
'''
            output, error = self._execute_on_robot(code)
            if output:
                try:
                    data = json.loads(output)
                    return SensorData(**data)
                except Exception as e:
                    logger.error(f"Error parsing sensor data: {e}")
        except Exception as e:
            logger.error(f"Error getting sensors: {e}")
        
        return SensorData()
    
    def move(self, x: float, y: float, theta: float) -> dict:
        """Send movement command to robot"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        try:
            code = f'''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.moveToward({x}, {y}, {theta})
print(json.dumps({{"success": True}}))
'''
            output, error = self._execute_on_robot(code)
            
            direction = "stopped"
            if abs(x) > 0.1:
                direction = "forward" if x > 0 else "backward"
            elif abs(theta) > 0.1:
                direction = "turning left" if theta > 0 else "turning right"
            elif abs(y) > 0.1:
                direction = "strafing left" if y > 0 else "strafing right"
            
            if output and "success" in output:
                return {"success": True, "message": f"Robot {direction}", "direction": direction}
            else:
                return {"success": False, "message": f"Move failed: {error or output}"}
                
        except Exception as e:
            logger.error(f"Move error: {e}")
            return {"success": False, "message": f"Movement failed: {str(e)}"}
    
    def stop(self) -> dict:
        """Stop robot movement"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        try:
            code = '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.stopMove()
print(json.dumps({"success": True}))
'''
            output, error = self._execute_on_robot(code)
            if output and "success" in output:
                return {"success": True, "message": "Robot stopped"}
            return {"success": False, "message": f"Stop failed: {error or output}"}
        except Exception as e:
            return {"success": False, "message": f"Stop failed: {str(e)}"}
    
    def speak(self, text: str, language: str = "en", volume: float = 1.0) -> dict:
        """Make the robot speak"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        # Escape quotes in text
        text = text.replace('"', '\\"').replace("'", "\\'")
        
        try:
            code = f'''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
audio = ALProxy("ALAudioDevice", robot_ip, port)
audio.setOutputVolume({int(volume * 100)})
tts.say("{text}")
print(json.dumps({{"success": True}}))
'''
            output, error = self._execute_on_robot(code, timeout=30)
            if output and "success" in output:
                return {"success": True, "message": f"Speaking: {text}"}
            return {"success": False, "message": f"Speech failed: {error or output}"}
        except Exception as e:
            return {"success": False, "message": f"Speech failed: {str(e)}"}
    
    def execute_gesture(self, gesture_name: str, speed: float = 1.0) -> dict:
        """Execute a gesture/behavior"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        gesture_name_lower = gesture_name.lower()
        
        try:
            if gesture_name_lower == "sit":
                code = f'''
posture = ALProxy("ALRobotPosture", robot_ip, port)
posture.goToPosture("Sit", {speed})
print(json.dumps({{"success": True, "gesture": "sit"}}))
'''
            elif gesture_name_lower == "stand":
                code = f'''
posture = ALProxy("ALRobotPosture", robot_ip, port)
posture.goToPosture("Stand", {speed})
print(json.dumps({{"success": True, "gesture": "stand"}}))
'''
            elif gesture_name_lower == "wave":
                code = '''
behavior = ALProxy("ALBehaviorManager", robot_ip, port)
if behavior.isBehaviorInstalled("animations/Stand/Gestures/Hey_1"):
    behavior.runBehavior("animations/Stand/Gestures/Hey_1")
else:
    # Fallback: manual wave
    motion = ALProxy("ALMotion", robot_ip, port)
    motion.wakeUp()
    names = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]
    angles = [-0.5, -0.3, 1.0, 0.5, 0.0]
    times = [1.0, 1.0, 1.0, 1.0, 1.0]
    motion.angleInterpolation(names, angles, times, True)
    import time
    time.sleep(0.5)
    # Wave motion
    for i in range(3):
        motion.setAngles("RWristYaw", 1.0, 0.3)
        time.sleep(0.3)
        motion.setAngles("RWristYaw", -1.0, 0.3)
        time.sleep(0.3)
    # Return to rest
    motion.setAngles(names, [1.5, 0.1, 1.2, 0.5, 0.0], 0.2)
print(json.dumps({"success": True, "gesture": "wave"}))
'''
            elif gesture_name_lower == "dance":
                code = '''
behavior = ALProxy("ALBehaviorManager", robot_ip, port)
behaviors = behavior.getInstalledBehaviors()
dance_behaviors = [b for b in behaviors if "dance" in b.lower()]
if dance_behaviors:
    behavior.runBehavior(dance_behaviors[0])
elif behavior.isBehaviorInstalled("animations/Stand/Gestures/Excited_1"):
    behavior.runBehavior("animations/Stand/Gestures/Excited_1")
else:
    tts = ALProxy("ALTextToSpeech", robot_ip, port)
    tts.say("Dancing!")
print(json.dumps({"success": True, "gesture": "dance"}))
'''
            elif gesture_name_lower == "bow":
                code = '''
behavior = ALProxy("ALBehaviorManager", robot_ip, port)
if behavior.isBehaviorInstalled("animations/Stand/Gestures/BowShort_1"):
    behavior.runBehavior("animations/Stand/Gestures/BowShort_1")
else:
    motion = ALProxy("ALMotion", robot_ip, port)
    motion.wakeUp()
    motion.setAngles("HeadPitch", 0.5, 0.2)
    import time
    time.sleep(1)
    motion.setAngles("HeadPitch", 0.0, 0.2)
print(json.dumps({"success": True, "gesture": "bow"}))
'''
            elif gesture_name_lower == "yes":
                code = '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
for i in range(3):
    motion.setAngles("HeadPitch", 0.3, 0.3)
    time.sleep(0.3)
    motion.setAngles("HeadPitch", -0.1, 0.3)
    time.sleep(0.3)
motion.setAngles("HeadPitch", 0.0, 0.2)
print(json.dumps({"success": True, "gesture": "yes"}))
'''
            elif gesture_name_lower == "no":
                code = '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
for i in range(3):
    motion.setAngles("HeadYaw", 0.5, 0.3)
    time.sleep(0.3)
    motion.setAngles("HeadYaw", -0.5, 0.3)
    time.sleep(0.3)
motion.setAngles("HeadYaw", 0.0, 0.2)
print(json.dumps({"success": True, "gesture": "no"}))
'''
            elif gesture_name_lower == "think":
                code = '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
# Put hand on chin thinking pose
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], 
                 [0.5, -0.2, 0.0, 1.5], 0.2)
motion.setAngles("HeadPitch", 0.2, 0.2)
import time
time.sleep(2)
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], 
                 [1.5, 0.1, 1.2, 0.5], 0.2)
motion.setAngles("HeadPitch", 0.0, 0.2)
print(json.dumps({"success": True, "gesture": "think"}))
'''
            elif gesture_name_lower == "handshake":
                code = '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
# Extend right arm for handshake
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"], 
                 [0.3, -0.3, 0.5, 0.2, 0.0], 0.2)
motion.openHand("RHand")
print(json.dumps({"success": True, "gesture": "handshake"}))
'''
            elif gesture_name_lower == "celebrate":
                code = '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
# Raise both arms
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.0, -1.0], 0.3)
time.sleep(0.5)
# Wave them
for i in range(3):
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.5, -0.5], 0.3)
    time.sleep(0.3)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.5, 0.5], 0.3)
    time.sleep(0.3)
# Return to normal
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], 
                 [1.5, 1.5, 0.1, -0.1], 0.2)
print(json.dumps({"success": True, "gesture": "celebrate"}))
'''
            else:
                return {"success": False, "message": f"Unknown gesture: {gesture_name}"}
            
            output, error = self._execute_on_robot(code, timeout=30)
            if output and "success" in output:
                return {"success": True, "message": f"Executing {gesture_name}", "gesture": gesture_name}
            return {"success": False, "message": f"Gesture failed: {error or output}"}
            
        except Exception as e:
            logger.error(f"Gesture error: {e}")
            return {"success": False, "message": f"Gesture failed: {str(e)}"}
    
    def get_camera_frame(self) -> Optional[bytes]:
        """Get a frame from the robot's camera"""
        if not self.connected:
            return None
        
        try:
            # Get image from robot and encode as base64
            code = '''
import base64
video = ALProxy("ALVideoDevice", robot_ip, port)
subscriber_id = video.subscribeCamera("nao_ctrl", 0, 1, 11, 10)
try:
    nao_image = video.getImageRemote(subscriber_id)
    if nao_image:
        width = nao_image[0]
        height = nao_image[1]
        array = nao_image[6]
        
        # Create PPM format (simple, no PIL needed)
        header = "P6\\n{} {}\\n255\\n".format(width, height)
        ppm_data = header.encode() + bytes(bytearray(array))
        b64 = base64.b64encode(ppm_data).decode()
        print(json.dumps({"image": b64, "width": width, "height": height}))
    else:
        print(json.dumps({"error": "No image"}))
finally:
    video.unsubscribe(subscriber_id)
'''
            output, error = self._execute_on_robot(code, timeout=15)
            
            if output:
                try:
                    data = json.loads(output)
                    if "image" in data:
                        # Decode and convert PPM to JPEG
                        ppm_data = base64.b64decode(data["image"])
                        from PIL import Image
                        img = Image.open(io.BytesIO(ppm_data))
                        
                        jpeg_buffer = io.BytesIO()
                        img.save(jpeg_buffer, format='JPEG', quality=70)
                        return jpeg_buffer.getvalue()
                except Exception as e:
                    logger.error(f"Error processing camera frame: {e}")
        except Exception as e:
            logger.error(f"Camera error: {e}")
        
        return None


# Global robot controller instance
robot = NAORobotSSHController()

# ==================== API Endpoints ====================

@api_router.get("/")
async def root():
    return {
        "message": "NAO Robot Control Bridge API",
        "version": "2.0.0",
        "status": "operational",
        "connection_method": "SSH + NAOqi",
        "note": "Connects to NAO robot via SSH to execute NAOqi commands"
    }

@api_router.get("/sdk-status")
async def get_sdk_status():
    """Check connection method status"""
    return {
        "sdk_available": True,  # SSH method is always available
        "connection_method": "SSH",
        "description": "Uses SSH to execute NAOqi Python commands on the robot"
    }

# Robot Configuration Endpoints
@api_router.post("/robots", response_model=RobotConfig)
async def save_robot(config: RobotConfigCreate):
    """Save a new robot configuration"""
    robot_config = RobotConfig(**config.dict())
    await db.robots.insert_one(robot_config.dict())
    logger.info(f"Saved robot config: {robot_config.name} at {robot_config.ip_address}")
    return robot_config

@api_router.get("/robots", response_model=List[RobotConfig])
async def get_robots():
    """Get all saved robot configurations"""
    robots = await db.robots.find().to_list(100)
    return [RobotConfig(**r) for r in robots]

@api_router.delete("/robots/{robot_id}")
async def delete_robot(robot_id: str):
    """Delete a saved robot configuration"""
    result = await db.robots.delete_one({"id": robot_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Robot not found")
    return {"message": "Robot deleted", "id": robot_id}

# Connection Endpoints
@api_router.post("/robot/connect")
async def connect_robot(connection: RobotConnection):
    """Connect to a NAO robot"""
    result = robot.connect(
        connection.ip_address, 
        connection.port,
        connection.username,
        connection.password
    )
    
    if result.get("success"):
        await db.robots.update_one(
            {"ip_address": connection.ip_address},
            {"$set": {"last_connected": datetime.utcnow()}}
        )
        
        return {
            "success": True,
            "message": result["message"],
            "status": robot.get_status().dict()
        }
    
    return {
        "success": False,
        "message": result["message"]
    }

@api_router.post("/robot/disconnect")
async def disconnect_robot():
    """Disconnect from the robot"""
    robot.disconnect()
    return {"success": True, "message": "Disconnected from robot"}

@api_router.get("/robot/status", response_model=RobotStatus)
async def get_robot_status():
    """Get current robot status"""
    return robot.get_status()

# Movement Endpoints
@api_router.post("/robot/move")
async def move_robot(command: MoveCommand):
    """Send movement command to robot"""
    return robot.move(command.x, command.y, command.theta)

@api_router.post("/robot/stop")
async def stop_robot():
    """Stop all robot movement"""
    return robot.stop()

# Speech Endpoints
@api_router.post("/robot/speak")
async def robot_speak(command: SpeechCommand):
    """Make the robot speak"""
    return robot.speak(command.text, command.language, command.volume)

# Gesture Endpoints
@api_router.post("/robot/gesture")
async def execute_gesture(command: GestureCommand):
    """Execute a gesture/animation"""
    return robot.execute_gesture(command.gesture_name, command.speed)

@api_router.get("/robot/gestures")
async def get_available_gestures():
    """Get list of available gestures"""
    return {
        "gestures": [
            {"name": "wave", "description": "Wave hand", "icon": "hand-wave"},
            {"name": "sit", "description": "Sit down", "icon": "seat"},
            {"name": "stand", "description": "Stand up", "icon": "human"},
            {"name": "bow", "description": "Bow", "icon": "human-greeting"},
            {"name": "dance", "description": "Dance", "icon": "music"},
            {"name": "handshake", "description": "Handshake", "icon": "handshake"},
            {"name": "yes", "description": "Nod yes", "icon": "check"},
            {"name": "no", "description": "Shake head no", "icon": "close"},
            {"name": "think", "description": "Thinking pose", "icon": "brain"},
            {"name": "celebrate", "description": "Celebrate", "icon": "party-popper"}
        ]
    }

# Sensor Endpoints
@api_router.get("/robot/sensors", response_model=SensorData)
async def get_sensors():
    """Get current sensor readings"""
    return robot.get_sensors()

# Camera Endpoints
@api_router.get("/robot/camera/frame")
async def get_camera_frame():
    """Get a single camera frame as base64"""
    if not robot.connected:
        raise HTTPException(status_code=400, detail="Robot not connected")
    
    frame_bytes = robot.get_camera_frame()
    
    if frame_bytes:
        frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')
        return {"frame": f"data:image/jpeg;base64,{frame_base64}", "timestamp": datetime.utcnow().isoformat()}
    
    raise HTTPException(status_code=500, detail="Could not capture camera frame")

# WebSocket for real-time sensor data
@api_router.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established for sensors")
    try:
        while True:
            if robot.connected:
                sensor_data = robot.get_sensors()
                await websocket.send_json(sensor_data.dict())
            else:
                await websocket.send_json({"connected": False, "message": "Robot not connected"})
            await asyncio.sleep(1)  # Update every 1 second (SSH has more latency)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    robot.disconnect()
    client.close()
