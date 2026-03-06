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

# ==================== NAOqi SDK Import ====================
# Try to import real NAOqi SDK
NAOQI_AVAILABLE = False
qi = None
naoqi = None

try:
    import qi
    NAOQI_AVAILABLE = True
    logger.info("qi library loaded successfully")
except ImportError:
    try:
        from naoqi import ALProxy
        naoqi = True
        NAOQI_AVAILABLE = True
        logger.info("naoqi library loaded successfully")
    except ImportError:
        logger.warning("NAOqi SDK not available - real robot connection disabled")
        logger.warning("To enable real robot connection, install the NAOqi SDK")

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

class MoveCommand(BaseModel):
    x: float  # Forward/backward velocity (-1 to 1)
    y: float  # Left/right velocity (-1 to 1)
    theta: float  # Rotation velocity (-1 to 1)

class SpeechCommand(BaseModel):
    text: str
    language: str = "en"
    volume: float = 1.0  # 0.0 to 1.0

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
    sdk_available: bool = False
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

# ==================== Real NAO Robot Controller ====================

class NAORobotController:
    """Controls a real NAO robot via NAOqi SDK"""
    
    def __init__(self):
        self.connected = False
        self.ip_address = None
        self.port = 9559
        self.session = None
        self._proxies = {}
        self._start_time = None
        self.connection_mode = "none"  # "real", "simulation", or "none"
        
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
    
    def connect(self, ip_address: str, port: int) -> dict:
        """Connect to the NAO robot"""
        self.ip_address = ip_address
        self.port = port
        
        # First check if robot is reachable
        logger.info(f"Checking if robot is reachable at {ip_address}:{port}...")
        
        if not self._check_robot_reachable(ip_address, port):
            return {
                "success": False,
                "message": f"Cannot reach robot at {ip_address}:{port}. Please check:\n"
                           "1. Robot is powered on\n"
                           "2. Robot and this device are on the same network\n"
                           "3. IP address is correct (press NAO's chest button to hear IP)\n"
                           "4. Port 9559 is not blocked by firewall",
                "connected": False
            }
        
        logger.info(f"Robot reachable at {ip_address}:{port}")
        
        # Try to connect using NAOqi SDK
        if NAOQI_AVAILABLE:
            try:
                if qi:
                    # Using modern qi library
                    self.session = qi.Session()
                    self.session.connect(f"tcp://{ip_address}:{port}")
                    self.connection_mode = "real"
                    logger.info(f"Connected to NAO robot using qi library")
                elif naoqi:
                    # Using legacy naoqi library - test with ALProxy
                    from naoqi import ALProxy
                    test_proxy = ALProxy("ALTextToSpeech", ip_address, port)
                    self.connection_mode = "real"
                    logger.info(f"Connected to NAO robot using naoqi library")
                
                self.connected = True
                self._start_time = datetime.utcnow()
                self._proxies = {}  # Clear old proxies
                
                return {
                    "success": True,
                    "message": f"Successfully connected to NAO robot at {ip_address}:{port}",
                    "connected": True,
                    "mode": "real"
                }
                
            except Exception as e:
                logger.error(f"NAOqi connection failed: {e}")
                return {
                    "success": False,
                    "message": f"NAOqi connection failed: {str(e)}. "
                               "Robot is reachable but NAOqi service may not be running.",
                    "connected": False
                }
        else:
            return {
                "success": False,
                "message": "NAOqi SDK is not installed. Please install the NAOqi Python SDK:\n"
                           "1. Download SDK from SoftBank Robotics\n"
                           "2. Extract and add to PYTHONPATH\n"
                           "3. Or install qi library: pip install qi",
                "connected": False,
                "sdk_required": True
            }
    
    def disconnect(self):
        """Disconnect from the robot"""
        if self.session and qi:
            try:
                self.session.close()
            except:
                pass
        self.connected = False
        self.session = None
        self._proxies = {}
        self.connection_mode = "none"
        logger.info("Disconnected from NAO robot")
    
    def _get_proxy(self, service_name: str):
        """Get or create a proxy for a NAOqi service"""
        if service_name not in self._proxies:
            if qi and self.session:
                self._proxies[service_name] = self.session.service(service_name)
            elif naoqi:
                from naoqi import ALProxy
                self._proxies[service_name] = ALProxy(service_name, self.ip_address, self.port)
        return self._proxies.get(service_name)
    
    def get_status(self) -> RobotStatus:
        """Get current robot status"""
        if not self.connected:
            return RobotStatus(
                connected=False,
                sdk_available=NAOQI_AVAILABLE,
                connection_mode=self.connection_mode
            )
        
        try:
            battery_level = 100
            temperature = 40.0
            posture = "Unknown"
            uptime = 0
            
            if self._start_time:
                uptime = int((datetime.utcnow() - self._start_time).total_seconds())
            
            # Try to get real data from robot
            try:
                battery_proxy = self._get_proxy("ALBattery")
                if battery_proxy:
                    battery_level = battery_proxy.getBatteryCharge()
            except Exception as e:
                logger.debug(f"Could not get battery: {e}")
            
            try:
                memory_proxy = self._get_proxy("ALMemory")
                if memory_proxy:
                    temperature = memory_proxy.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value")
            except Exception as e:
                logger.debug(f"Could not get temperature: {e}")
            
            try:
                posture_proxy = self._get_proxy("ALRobotPosture")
                if posture_proxy:
                    posture = posture_proxy.getPostureFamily()
            except Exception as e:
                logger.debug(f"Could not get posture: {e}")
            
            return RobotStatus(
                connected=True,
                ip_address=self.ip_address,
                battery_level=battery_level,
                temperature=temperature,
                robot_name="NAO V5",
                uptime=uptime,
                posture=posture,
                sdk_available=NAOQI_AVAILABLE,
                connection_mode=self.connection_mode
            )
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return RobotStatus(
                connected=self.connected,
                ip_address=self.ip_address,
                sdk_available=NAOQI_AVAILABLE,
                connection_mode=self.connection_mode
            )
    
    def get_sensors(self) -> SensorData:
        """Get sensor data from the robot"""
        if not self.connected:
            return SensorData()
        
        try:
            memory = self._get_proxy("ALMemory")
            
            if memory:
                return SensorData(
                    head_touch_front=bool(memory.getData("Device/SubDeviceList/Head/Touch/Front/Sensor/Value")),
                    head_touch_middle=bool(memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")),
                    head_touch_rear=bool(memory.getData("Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")),
                    left_hand_touch=bool(memory.getData("Device/SubDeviceList/LHand/Touch/Back/Sensor/Value")),
                    right_hand_touch=bool(memory.getData("Device/SubDeviceList/RHand/Touch/Back/Sensor/Value")),
                    sonar_left=float(memory.getData("Device/SubDeviceList/US/Left/Sensor/Value")),
                    sonar_right=float(memory.getData("Device/SubDeviceList/US/Right/Sensor/Value")),
                    battery_level=int(memory.getData("Device/SubDeviceList/Battery/Charge/Sensor/Value")),
                    head_yaw=float(memory.getData("Device/SubDeviceList/HeadYaw/Position/Sensor/Value")),
                    head_pitch=float(memory.getData("Device/SubDeviceList/HeadPitch/Position/Sensor/Value")),
                    left_shoulder_pitch=float(memory.getData("Device/SubDeviceList/LShoulderPitch/Position/Sensor/Value")),
                    right_shoulder_pitch=float(memory.getData("Device/SubDeviceList/RShoulderPitch/Position/Sensor/Value")),
                    temperature_cpu=float(memory.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value")),
                    temperature_battery=float(memory.getData("Device/SubDeviceList/Battery/Temperature/Sensor/Value")),
                )
        except Exception as e:
            logger.error(f"Error getting sensors: {e}")
        
        return SensorData()
    
    def move(self, x: float, y: float, theta: float) -> dict:
        """Send movement command to robot"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        try:
            motion = self._get_proxy("ALMotion")
            if motion:
                # Wake up robot if needed
                motion.wakeUp()
                # Send movement command
                motion.moveToward(x, y, theta)
                
                direction = "stopped"
                if abs(x) > 0.1:
                    direction = "forward" if x > 0 else "backward"
                elif abs(theta) > 0.1:
                    direction = "turning left" if theta > 0 else "turning right"
                elif abs(y) > 0.1:
                    direction = "strafing left" if y > 0 else "strafing right"
                
                return {"success": True, "message": f"Robot {direction}", "direction": direction}
        except Exception as e:
            logger.error(f"Move error: {e}")
            return {"success": False, "message": f"Movement failed: {str(e)}"}
        
        return {"success": False, "message": "Motion proxy not available"}
    
    def stop(self) -> dict:
        """Stop robot movement"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        try:
            motion = self._get_proxy("ALMotion")
            if motion:
                motion.stopMove()
                return {"success": True, "message": "Robot stopped"}
        except Exception as e:
            logger.error(f"Stop error: {e}")
            return {"success": False, "message": f"Stop failed: {str(e)}"}
        
        return {"success": False, "message": "Motion proxy not available"}
    
    def speak(self, text: str, language: str = "en", volume: float = 1.0) -> dict:
        """Make the robot speak"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        try:
            tts = self._get_proxy("ALTextToSpeech")
            if tts:
                # Set language if specified
                if language:
                    try:
                        tts.setLanguage(language.capitalize())
                    except:
                        pass
                
                # Set volume
                try:
                    audio = self._get_proxy("ALAudioDevice")
                    if audio:
                        audio.setOutputVolume(int(volume * 100))
                except:
                    pass
                
                # Speak the text
                tts.say(text)
                return {"success": True, "message": f"Speaking: {text}"}
        except Exception as e:
            logger.error(f"Speech error: {e}")
            return {"success": False, "message": f"Speech failed: {str(e)}"}
        
        return {"success": False, "message": "TTS proxy not available"}
    
    def execute_gesture(self, gesture_name: str, speed: float = 1.0) -> dict:
        """Execute a gesture/behavior"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        # Map gesture names to NAOqi behavior paths
        gesture_map = {
            "wave": "animations/Stand/Gestures/Hey_1",
            "sit": "animations/Stand/Emotions/Positive/Excited_1",
            "stand": "animations/Stand/Gestures/Enthusiastic_4",
            "bow": "animations/Stand/Gestures/BowShort_1",
            "dance": "animations/Stand/Gestures/Excited_1",
            "handshake": "animations/Stand/Gestures/Give_1",
            "yes": "animations/Stand/Gestures/Yes_1",
            "no": "animations/Stand/Gestures/No_1",
            "think": "animations/Stand/Gestures/Thinking_1",
            "celebrate": "animations/Stand/Gestures/Winner_1"
        }
        
        behavior_path = gesture_map.get(gesture_name.lower())
        if not behavior_path:
            return {"success": False, "message": f"Unknown gesture: {gesture_name}"}
        
        try:
            # First try posture for sit/stand
            if gesture_name.lower() == "sit":
                posture = self._get_proxy("ALRobotPosture")
                if posture:
                    posture.goToPosture("Sit", speed)
                    return {"success": True, "message": "Sitting down", "gesture": gesture_name}
            
            elif gesture_name.lower() == "stand":
                posture = self._get_proxy("ALRobotPosture")
                if posture:
                    posture.goToPosture("Stand", speed)
                    return {"success": True, "message": "Standing up", "gesture": gesture_name}
            
            # Try behavior manager for other gestures
            behavior = self._get_proxy("ALBehaviorManager")
            if behavior:
                if behavior.isBehaviorInstalled(behavior_path):
                    behavior.runBehavior(behavior_path)
                    return {"success": True, "message": f"Executing {gesture_name}", "gesture": gesture_name}
                else:
                    # Fallback: try animation
                    animation = self._get_proxy("ALAnimationPlayer")
                    if animation:
                        animation.run(behavior_path)
                        return {"success": True, "message": f"Playing animation {gesture_name}", "gesture": gesture_name}
            
            return {"success": False, "message": f"Gesture {gesture_name} not available on this robot"}
            
        except Exception as e:
            logger.error(f"Gesture error: {e}")
            return {"success": False, "message": f"Gesture failed: {str(e)}"}
    
    def get_camera_frame(self) -> Optional[bytes]:
        """Get a frame from the robot's camera"""
        if not self.connected:
            return None
        
        try:
            video = self._get_proxy("ALVideoDevice")
            if video:
                # Subscribe to camera
                resolution = 1  # 320x240
                colorspace = 11  # RGB
                fps = 15
                
                subscriber_id = video.subscribeCamera("nao_controller", 0, resolution, colorspace, fps)
                
                try:
                    # Get image
                    nao_image = video.getImageRemote(subscriber_id)
                    
                    if nao_image:
                        width = nao_image[0]
                        height = nao_image[1]
                        array = nao_image[6]
                        
                        # Convert to PIL Image
                        from PIL import Image
                        img = Image.frombytes("RGB", (width, height), bytes(array))
                        
                        # Convert to JPEG
                        buffer = io.BytesIO()
                        img.save(buffer, format='JPEG', quality=70)
                        return buffer.getvalue()
                finally:
                    video.unsubscribe(subscriber_id)
                    
        except Exception as e:
            logger.error(f"Camera error: {e}")
        
        return None


# Global robot controller instance
robot = NAORobotController()

# ==================== API Endpoints ====================

@api_router.get("/")
async def root():
    return {
        "message": "NAO Robot Control Bridge API",
        "version": "2.0.0",
        "status": "operational",
        "naoqi_sdk_available": NAOQI_AVAILABLE,
        "note": "This API requires NAOqi SDK for real robot connection"
    }

@api_router.get("/sdk-status")
async def get_sdk_status():
    """Check if NAOqi SDK is available"""
    return {
        "sdk_available": NAOQI_AVAILABLE,
        "qi_library": qi is not None,
        "naoqi_library": naoqi is not None,
        "instructions": "Install NAOqi SDK from SoftBank Robotics or run: pip install qi" if not NAOQI_AVAILABLE else None
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
    result = robot.connect(connection.ip_address, connection.port)
    
    if result.get("success"):
        # Update last_connected for saved robot
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
        "message": result["message"],
        "sdk_required": result.get("sdk_required", False)
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
    result = robot.move(command.x, command.y, command.theta)
    return result

@api_router.post("/robot/stop")
async def stop_robot():
    """Stop all robot movement"""
    return robot.stop()

# Speech Endpoints
@api_router.post("/robot/speak")
async def robot_speak(command: SpeechCommand):
    """Make the robot speak"""
    result = robot.speak(command.text, command.language, command.volume)
    return result

# Gesture Endpoints
@api_router.post("/robot/gesture")
async def execute_gesture(command: GestureCommand):
    """Execute a gesture/animation"""
    result = robot.execute_gesture(command.gesture_name, command.speed)
    return result

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
            await asyncio.sleep(0.5)  # Update every 500ms
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
