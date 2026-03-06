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
import random
import base64
import io
import numpy as np
from PIL import Image

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

# ==================== Robot State (Simulation) ====================

class RobotSimulator:
    """Simulates NAO robot state and behavior"""
    def __init__(self):
        self.connected = False
        self.ip_address = None
        self.port = 9559
        self.battery_level = 87
        self.posture = "Stand"
        self.is_speaking = False
        self.is_moving = False
        self.current_gesture = None
        self.uptime = 0
        self.sensors = {
            "head_touch_front": False,
            "head_touch_middle": False,
            "head_touch_rear": False,
            "left_hand_touch": False,
            "right_hand_touch": False,
            "sonar_left": 1.5,
            "sonar_right": 1.5,
            "head_yaw": 0.0,
            "head_pitch": 0.0,
            "left_shoulder_pitch": 1.57,
            "right_shoulder_pitch": 1.57,
            "temperature_cpu": 42.5,
            "temperature_battery": 36.0
        }
        self._start_time = datetime.utcnow()
    
    def connect(self, ip_address: str, port: int) -> bool:
        """Simulate connection to robot"""
        # Simulate connection delay
        self.ip_address = ip_address
        self.port = port
        self.connected = True
        self._start_time = datetime.utcnow()
        logger.info(f"Connected to NAO robot at {ip_address}:{port}")
        return True
    
    def disconnect(self):
        """Simulate disconnection"""
        self.connected = False
        self.ip_address = None
        logger.info("Disconnected from NAO robot")
    
    def get_status(self) -> RobotStatus:
        """Get current robot status"""
        if self.connected:
            self.uptime = int((datetime.utcnow() - self._start_time).total_seconds())
            # Slowly drain battery
            self.battery_level = max(10, 87 - (self.uptime // 60))
        
        return RobotStatus(
            connected=self.connected,
            ip_address=self.ip_address,
            battery_level=self.battery_level,
            temperature=self.sensors["temperature_cpu"],
            robot_name="NAO V5",
            uptime=self.uptime,
            posture=self.posture
        )
    
    def get_sensors(self) -> SensorData:
        """Get simulated sensor data with slight variations"""
        if self.connected:
            # Add realistic sensor noise
            self.sensors["sonar_left"] = round(1.5 + random.uniform(-0.3, 0.3), 2)
            self.sensors["sonar_right"] = round(1.5 + random.uniform(-0.3, 0.3), 2)
            self.sensors["temperature_cpu"] = round(42.5 + random.uniform(-2, 3), 1)
            self.sensors["temperature_battery"] = round(36.0 + random.uniform(-1, 2), 1)
            self.sensors["head_yaw"] = round(random.uniform(-0.1, 0.1), 3)
            self.sensors["head_pitch"] = round(random.uniform(-0.05, 0.05), 3)
        
        return SensorData(
            head_touch_front=self.sensors["head_touch_front"],
            head_touch_middle=self.sensors["head_touch_middle"],
            head_touch_rear=self.sensors["head_touch_rear"],
            left_hand_touch=self.sensors["left_hand_touch"],
            right_hand_touch=self.sensors["right_hand_touch"],
            sonar_left=self.sensors["sonar_left"],
            sonar_right=self.sensors["sonar_right"],
            battery_level=self.battery_level,
            head_yaw=self.sensors["head_yaw"],
            head_pitch=self.sensors["head_pitch"],
            left_shoulder_pitch=self.sensors["left_shoulder_pitch"],
            right_shoulder_pitch=self.sensors["right_shoulder_pitch"],
            temperature_cpu=self.sensors["temperature_cpu"],
            temperature_battery=self.sensors["temperature_battery"]
        )
    
    def move(self, x: float, y: float, theta: float) -> dict:
        """Simulate movement command"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        self.is_moving = True
        direction = "stopped"
        if abs(x) > 0.1:
            direction = "forward" if x > 0 else "backward"
        elif abs(theta) > 0.1:
            direction = "turning left" if theta > 0 else "turning right"
        elif abs(y) > 0.1:
            direction = "strafing left" if y > 0 else "strafing right"
        
        logger.info(f"Robot moving: {direction} (x={x}, y={y}, theta={theta})")
        return {"success": True, "message": f"Robot {direction}", "direction": direction}
    
    def speak(self, text: str, language: str = "en", volume: float = 1.0) -> dict:
        """Simulate text-to-speech"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        self.is_speaking = True
        logger.info(f"Robot speaking: '{text}' in {language}")
        # Simulate speaking duration based on text length
        duration = len(text) * 0.05
        return {"success": True, "message": f"Speaking: {text}", "duration": duration}
    
    def execute_gesture(self, gesture_name: str, speed: float = 1.0) -> dict:
        """Simulate gesture execution"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}
        
        gestures = {
            "wave": {"duration": 3, "description": "Waving hand"},
            "sit": {"duration": 4, "description": "Sitting down"},
            "stand": {"duration": 4, "description": "Standing up"},
            "bow": {"duration": 3, "description": "Bowing"},
            "dance": {"duration": 10, "description": "Dancing"},
            "handshake": {"duration": 5, "description": "Handshake gesture"},
            "yes": {"duration": 2, "description": "Nodding yes"},
            "no": {"duration": 2, "description": "Shaking head no"},
            "think": {"duration": 3, "description": "Thinking pose"},
            "celebrate": {"duration": 5, "description": "Celebration dance"}
        }
        
        if gesture_name.lower() not in gestures:
            return {"success": False, "message": f"Unknown gesture: {gesture_name}"}
        
        gesture = gestures[gesture_name.lower()]
        self.current_gesture = gesture_name
        
        # Update posture for sit/stand
        if gesture_name.lower() == "sit":
            self.posture = "Sit"
        elif gesture_name.lower() == "stand":
            self.posture = "Stand"
        
        logger.info(f"Executing gesture: {gesture['description']}")
        return {
            "success": True, 
            "message": gesture["description"], 
            "gesture": gesture_name,
            "duration": gesture["duration"] / speed
        }
    
    def generate_camera_frame(self) -> bytes:
        """Generate a simulated camera frame"""
        # Create a simple test pattern image
        width, height = 320, 240
        img = Image.new('RGB', (width, height), color=(20, 20, 30))
        
        # Add some visual elements
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        
        # Draw a grid pattern
        for i in range(0, width, 40):
            draw.line([(i, 0), (i, height)], fill=(0, 100, 200), width=1)
        for i in range(0, height, 40):
            draw.line([(0, i), (width, i)], fill=(0, 100, 200), width=1)
        
        # Add timestamp
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        draw.text((10, 10), f"NAO Camera - {timestamp}", fill=(0, 200, 255))
        draw.text((10, height - 30), f"Simulated Feed", fill=(100, 100, 100))
        
        # Add center crosshair
        cx, cy = width // 2, height // 2
        draw.line([(cx - 20, cy), (cx + 20, cy)], fill=(0, 255, 100), width=2)
        draw.line([(cx, cy - 20), (cx, cy + 20)], fill=(0, 255, 100), width=2)
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=70)
        return buffer.getvalue()

# Global robot simulator instance
robot = RobotSimulator()

# ==================== API Endpoints ====================

@api_router.get("/")
async def root():
    return {"message": "NAO Robot Control Bridge API", "version": "1.0.0", "status": "operational"}

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
    success = robot.connect(connection.ip_address, connection.port)
    
    # Update last_connected for saved robot
    await db.robots.update_one(
        {"ip_address": connection.ip_address},
        {"$set": {"last_connected": datetime.utcnow()}}
    )
    
    if success:
        return {
            "success": True, 
            "message": f"Connected to robot at {connection.ip_address}:{connection.port}",
            "status": robot.get_status().dict()
        }
    return {"success": False, "message": "Failed to connect to robot"}

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
    result = robot.move(0, 0, 0)
    robot.is_moving = False
    return {"success": True, "message": "Robot stopped"}

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
    
    frame_bytes = robot.generate_camera_frame()
    frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')
    return {"frame": f"data:image/jpeg;base64,{frame_base64}", "timestamp": datetime.utcnow().isoformat()}

@api_router.get("/robot/camera/stream")
async def camera_stream():
    """MJPEG camera stream"""
    async def generate():
        while robot.connected:
            frame = robot.generate_camera_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            await asyncio.sleep(0.066)  # ~15 FPS
    
    return StreamingResponse(
        generate(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

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
    client.close()
