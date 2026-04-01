#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAO Robot REST API Server with Fall Detection (Laptop-based Detection)
Run this on your laptop that's connected to the same WiFi as your NAO robot.

Detection runs on LAPTOP (using OpenCV) - Light on NAO robot!
NAO only captures camera frames, laptop does the heavy processing.

Requirements:
    pip install paramiko flask flask-cors opencv-python numpy

Usage:
    python nao.py

Then connect the mobile app to your laptop's IP address on port 5000.
"""

import json
import time
import sys
import socket
import threading
import base64
import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

# Check Python version
if sys.version_info[0] < 3:
    print("This script requires Python 3.")
    sys.exit(1)

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import paramiko
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("\nPlease install required packages:")
    print("  pip install paramiko flask flask-cors opencv-python numpy")
    sys.exit(1)

# Try to import OpenCV for laptop-based detection
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
    print("OpenCV loaded - Fall detection will run on laptop")
except ImportError:
    OPENCV_AVAILABLE = False
    print("WARNING: OpenCV not installed. Install with: pip install opencv-python numpy")
    print("Fall detection will use basic method.")

# ==================== Configuration ====================
NAO_IP = "172.18.16.35"  # Your NAO robot's IP address
NAO_PORT = 9559
SSH_USERNAME = "nao"
SSH_PASSWORD = "nao"
SERVER_PORT = 5000

# Email Configuration for Fall Detection Alerts
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "coldiot34@gmail.com"
SENDER_PASSWORD = "ldyl ufwa awox jwqu"
RECEIVER_EMAIL = "sushanthsujeerkumar@gmail.com"

# Fall Detection Configuration
HORIZONTAL_DETECTION_SECONDS = 12  # Time person must be horizontal before alert
VERBAL_RESPONSE_WAIT_SECONDS = 10  # Time to wait for verbal response
FINAL_ALERT_WAIT_SECONDS = 10  # Time after sound alert before email
DETECTION_CHECK_INTERVAL = 3  # Seconds between each camera check (lighter on NAO)

# ==================== Flask App ====================
app = Flask(__name__)
CORS(app)

# ==================== Fall Detection State ====================
class FallDetectionState:
    def __init__(self):
        self.is_active = False
        self.status = "idle"  # idle, monitoring, person_detected, checking, alert_sent
        self.message = "Fall detection not active"
        self.last_alert = None
        self.person_horizontal_since = None
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        self.last_frame = None  # Store last captured frame for debugging

fall_state = FallDetectionState()


# ==================== Laptop-Based Image Analysis ====================
class LaptopDetector:
    """
    Detects horizontal person using OpenCV on LAPTOP
    NAO only sends camera images - all processing happens here
    """
    
    def __init__(self):
        self.hog = None
        self.face_cascade = None
        if OPENCV_AVAILABLE:
            # Initialize HOG person detector
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            
            # Initialize face cascade
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            
            # Also try profile face for sideways detection
            self.profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_profileface.xml'
            )
    
    def ppm_to_cv2(self, ppm_data):
        """Convert PPM image data to OpenCV format"""
        try:
            # Decode base64
            raw_data = base64.b64decode(ppm_data)
            
            # Parse PPM header
            # Format: P6\nWIDTH\nHEIGHT\nMAXVAL\n<binary data>
            lines = raw_data.split(b'\n', 3)
            if len(lines) >= 4:
                width = int(lines[1])
                height = int(lines[2])
                # maxval = int(lines[3])  # Usually 255
                pixel_data = lines[3] if len(lines) > 3 else b''
                
                # Sometimes header is "WIDTH HEIGHT" on same line
                if b' ' in lines[1]:
                    parts = lines[1].split()
                    width = int(parts[0])
                    height = int(parts[1])
                    pixel_data = lines[2] if len(lines) > 2 else b''
                
                # Convert to numpy array
                if len(pixel_data) >= width * height * 3:
                    img_array = np.frombuffer(pixel_data[:width*height*3], dtype=np.uint8)
                    img_array = img_array.reshape((height, width, 3))
                    # Convert RGB to BGR for OpenCV
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    return img_bgr
        except Exception as e:
            print(f"PPM conversion error: {e}")
        return None
    
    def detect_horizontal_person(self, image_base64):
        """
        Analyze image to detect if a person is lying horizontal
        Returns: (is_horizontal, confidence, details)
        
        Detection methods:
        1. Detect person bounding box - if width > height, likely horizontal
        2. Detect face position - if face is at unusual angle or low position
        3. Body aspect ratio analysis
        """
        if not OPENCV_AVAILABLE or not image_base64:
            return False, 0.0, "OpenCV not available"
        
        try:
            # Convert image
            img = self.ppm_to_cv2(image_base64)
            if img is None:
                return False, 0.0, "Failed to decode image"
            
            # Store for debugging
            fall_state.last_frame = img
            
            # Resize for faster processing
            scale = 0.5
            small = cv2.resize(img, None, fx=scale, fy=scale)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            
            is_horizontal = False
            confidence = 0.0
            details = []
            
            # Method 1: HOG Person Detection
            persons, weights = self.hog.detectMultiScale(
                small, 
                winStride=(8, 8),
                padding=(4, 4),
                scale=1.05
            )
            
            for i, (x, y, w, h) in enumerate(persons):
                aspect_ratio = w / h if h > 0 else 0
                weight = weights[i] if i < len(weights) else 0
                
                details.append(f"Person {i+1}: aspect={aspect_ratio:.2f}, conf={weight:.2f}")
                
                # Normal standing person: width < height (aspect < 1)
                # Horizontal person: width > height (aspect > 1)
                if aspect_ratio > 1.2:  # Width significantly larger than height
                    is_horizontal = True
                    confidence = max(confidence, min(0.9, aspect_ratio / 2))
                    details.append(f"HORIZONTAL: aspect ratio {aspect_ratio:.2f} > 1.2")
                
                # Person detected very low in frame (bottom 40%)
                person_center_y = (y + h/2) / small.shape[0]
                if person_center_y > 0.6 and aspect_ratio > 0.8:
                    is_horizontal = True
                    confidence = max(confidence, 0.7)
                    details.append(f"LOW POSITION: y={person_center_y:.2f}")
            
            # Method 2: Face Detection
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(20, 20))
            profile_faces = self.profile_cascade.detectMultiScale(gray, 1.1, 4, minSize=(20, 20))
            
            all_faces = list(faces) + list(profile_faces)
            
            for (x, y, w, h) in all_faces:
                face_center_y = (y + h/2) / small.shape[0]
                face_aspect = w / h if h > 0 else 1
                
                details.append(f"Face at y={face_center_y:.2f}, aspect={face_aspect:.2f}")
                
                # Face in lower half of image might indicate fallen person
                if face_center_y > 0.65:
                    confidence = max(confidence, 0.6)
                    details.append("Face in lower region")
                
                # Face aspect ratio > 1.3 might indicate sideways/horizontal head
                if face_aspect > 1.3 or face_aspect < 0.7:
                    confidence = max(confidence, 0.5)
                    details.append(f"Unusual face aspect: {face_aspect:.2f}")
            
            # Method 3: Motion/Stillness detection could be added here
            # (would need previous frame comparison)
            
            # Determine final result
            if confidence > 0.5:
                is_horizontal = True
            
            detail_str = " | ".join(details) if details else "No person detected"
            return is_horizontal, confidence, detail_str
            
        except Exception as e:
            return False, 0.0, f"Detection error: {str(e)}"


# Global detector instance (runs on laptop)
laptop_detector = LaptopDetector()


# ==================== SSH Connection ====================
class NAOController:
    def __init__(self):
        self.ssh = None
        self.connected = False
        self.nao_ip = NAO_IP
        self.start_time = None
        
    def _execute_naoqi(self, code, timeout=30):
        """Execute Python code on NAO via SSH"""
        if not self.ssh:
            return None, "Not connected to NAO"
        
        full_script = f'''python2 << 'NAOCODE'
# -*- coding: utf-8 -*-
from naoqi import ALProxy
import json

robot_ip = "127.0.0.1"
port = 9559

try:
{self._indent(code)}
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
NAOCODE'''
        
        try:
            stdin, stdout, stderr = self.ssh.exec_command(full_script, timeout=timeout)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            return output, error
        except Exception as e:
            return None, str(e)
    
    def _indent(self, code, spaces=4):
        return '\n'.join(' ' * spaces + line for line in code.split('\n'))
    
    def connect(self, ip, username="nao", password="nao"):
        """Connect to NAO via SSH"""
        self.nao_ip = ip
        
        print(f"Checking if NAO is reachable at {ip}...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, 22))
            sock.close()
            if result != 0:
                return {"success": False, "message": f"Cannot reach NAO at {ip}. Check IP address and WiFi connection."}
        except Exception as e:
            return {"success": False, "message": f"Network error: {e}"}
        
        print(f"NAO is reachable. Connecting via SSH...")
        
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(ip, port=22, username=username, password=password, timeout=10)
            
            output, error = self._execute_naoqi('''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.say("Connected to remote control")
print(json.dumps({"success": True}))
''')
            
            if output and "success" in output:
                self.connected = True
                self.start_time = time.time()
                print(f"Connected to NAO at {ip}")
                return {"success": True, "message": f"Connected to NAO at {ip}"}
            else:
                self.ssh.close()
                self.ssh = None
                return {"success": False, "message": f"NAOqi test failed: {error or output}"}
                
        except paramiko.AuthenticationException:
            return {"success": False, "message": "SSH authentication failed. Default is nao/nao"}
        except Exception as e:
            return {"success": False, "message": f"Connection failed: {e}"}
    
    def disconnect(self):
        if self.ssh:
            try:
                self._execute_naoqi('ALProxy("ALTextToSpeech", robot_ip, port).say("Goodbye")')
                self.ssh.close()
            except:
                pass
        self.ssh = None
        self.connected = False
        print("Disconnected from NAO")
    
    def get_status(self):
        if not self.connected:
            return {"connected": False}
        
        output, _ = self._execute_naoqi('''
battery = ALProxy("ALBattery", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)

data = {
    "battery_level": battery.getBatteryCharge(),
    "posture": posture.getPostureFamily(),
    "temperature": 40.0
}
try:
    data["temperature"] = memory.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value")
except:
    pass

print(json.dumps(data))
''')
        
        try:
            data = json.loads(output) if output else {}
            uptime = int(time.time() - self.start_time) if self.start_time else 0
            return {
                "connected": True,
                "ip_address": self.nao_ip,
                "battery_level": data.get("battery_level", 0),
                "temperature": data.get("temperature", 40),
                "robot_name": "NAO V5",
                "posture": data.get("posture", "Unknown"),
                "uptime": uptime,
                "connection_mode": "ssh"
            }
        except:
            return {"connected": True, "ip_address": self.nao_ip, "robot_name": "NAO V5"}
    
    def get_sensors(self):
        if not self.connected:
            return {}
        
        output, _ = self._execute_naoqi('''
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
    "battery_level": battery.getBatteryCharge(),
    "head_yaw": float(memory.getData("Device/SubDeviceList/HeadYaw/Position/Sensor/Value") or 0),
    "head_pitch": float(memory.getData("Device/SubDeviceList/HeadPitch/Position/Sensor/Value") or 0),
    "left_shoulder_pitch": float(memory.getData("Device/SubDeviceList/LShoulderPitch/Position/Sensor/Value") or 0),
    "right_shoulder_pitch": float(memory.getData("Device/SubDeviceList/RShoulderPitch/Position/Sensor/Value") or 0),
    "temperature_cpu": 40.0,
    "temperature_battery": 35.0
}

try:
    data["temperature_cpu"] = float(memory.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value"))
except:
    pass

print(json.dumps(data))
''')
        
        try:
            return json.loads(output) if output else {}
        except:
            return {}
    
    def move(self, x, y, theta):
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        
        output, error = self._execute_naoqi(f'''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.moveToward({x}, {y}, {theta})
print(json.dumps({{"success": True}}))
''')
        
        direction = "stopped"
        if abs(x) > 0.1:
            direction = "forward" if x > 0 else "backward"
        elif abs(theta) > 0.1:
            direction = "turning left" if theta > 0 else "turning right"
        
        if output and "success" in output:
            return {"success": True, "message": f"Robot {direction}"}
        return {"success": False, "message": error or "Move failed"}
    
    def stop(self):
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        
        self._execute_naoqi('''
motion = ALProxy("ALMotion", robot_ip, port)
motion.stopMove()
print(json.dumps({"success": True}))
''')
        return {"success": True, "message": "Robot stopped"}
    
    def speak(self, text):
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        
        text = text.replace('"', '\\"').replace("'", "\\'")
        
        output, error = self._execute_naoqi(f'''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.say("{text}")
print(json.dumps({{"success": True}}))
''', timeout=60)
        
        if output and "success" in output:
            return {"success": True, "message": f"Speaking: {text}"}
        return {"success": False, "message": error or "Speech failed"}
    
    def gesture(self, name, speed=1.0):
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        
        gestures = {
            "sit": f'''
posture = ALProxy("ALRobotPosture", robot_ip, port)
posture.goToPosture("Sit", {speed})
print(json.dumps({{"success": True}}))
''',
            "stand": f'''
posture = ALProxy("ALRobotPosture", robot_ip, port)
posture.goToPosture("Stand", {speed})
print(json.dumps({{"success": True}}))
''',
            "wave": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
names = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"]
motion.setAngles(names, [-0.5, -0.3, 1.0, 0.5], 0.2)
time.sleep(0.5)
for i in range(3):
    motion.setAngles("RWristYaw", 1.0, 0.3)
    time.sleep(0.3)
    motion.setAngles("RWristYaw", -1.0, 0.3)
    time.sleep(0.3)
motion.setAngles(names + ["RWristYaw"], [1.5, 0.1, 1.2, 0.5, 0.0], 0.2)
print(json.dumps({"success": True}))
''',
            "bow": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
motion.setAngles("HeadPitch", 0.5, 0.2)
time.sleep(1)
motion.setAngles("HeadPitch", 0.0, 0.2)
print(json.dumps({"success": True}))
''',
            "yes": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
for i in range(3):
    motion.setAngles("HeadPitch", 0.3, 0.3)
    time.sleep(0.3)
    motion.setAngles("HeadPitch", -0.1, 0.3)
    time.sleep(0.3)
motion.setAngles("HeadPitch", 0.0, 0.2)
print(json.dumps({"success": True}))
''',
            "no": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
for i in range(3):
    motion.setAngles("HeadYaw", 0.5, 0.3)
    time.sleep(0.3)
    motion.setAngles("HeadYaw", -0.5, 0.3)
    time.sleep(0.3)
motion.setAngles("HeadYaw", 0.0, 0.2)
print(json.dumps({"success": True}))
''',
            "dance": '''
motion = ALProxy("ALMotion", robot_ip, port)
tts = ALProxy("ALTextToSpeech", robot_ip, port)
motion.wakeUp()
tts.say("Dancing!")
import time
for i in range(4):
    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.3)
    time.sleep(0.4)
    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.3)
    time.sleep(0.4)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.2)
print(json.dumps({"success": True}))
''',
            "celebrate": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.0, -1.0], 0.3)
time.sleep(0.5)
for i in range(3):
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.5, -0.5], 0.3)
    time.sleep(0.3)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.5, 0.5], 0.3)
    time.sleep(0.3)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], 
                 [1.5, 1.5, 0.1, -0.1], 0.2)
print(json.dumps({"success": True}))
''',
            "handshake": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"], 
                 [0.3, -0.3, 0.5, 0.2, 0.0], 0.2)
motion.openHand("RHand")
print(json.dumps({"success": True}))
''',
            "think": '''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
import time
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], 
                 [0.5, -0.2, 0.0, 1.5], 0.2)
motion.setAngles("HeadPitch", 0.2, 0.2)
time.sleep(2)
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "HeadPitch"], 
                 [1.5, 0.1, 1.2, 0.5, 0.0], 0.2)
print(json.dumps({"success": True}))
'''
        }
        
        code = gestures.get(name.lower())
        if not code:
            return {"success": False, "message": f"Unknown gesture: {name}"}
        
        output, error = self._execute_naoqi(code, timeout=60)
        
        if output and "success" in output:
            return {"success": True, "message": f"Executing {name}", "gesture": name}
        return {"success": False, "message": error or "Gesture failed"}
    
    def capture_camera_frame(self):
        """
        Capture a single frame from NAO's camera (LIGHT operation)
        Returns base64 encoded PPM image
        """
        if not self.connected:
            return None, "Not connected"
        
        output, error = self._execute_naoqi('''
import vision_definitions
import base64

video = ALProxy("ALVideoDevice", robot_ip, port)

# Use lower resolution for faster capture (QVGA = 320x240)
resolution = vision_definitions.kQVGA
colorSpace = vision_definitions.kRGBColorSpace
fps = 5

# Subscribe, capture, unsubscribe quickly
cam_id = "fall_cam_" + str(int(__import__('time').time() * 1000) % 10000)
camProxy = video.subscribeCamera(cam_id, 0, resolution, colorSpace, fps)

import time
time.sleep(0.3)

# Get single image
image = video.getImageRemote(camProxy)
video.unsubscribe(camProxy)

if image:
    width = image[0]
    height = image[1]
    array = image[6]
    
    # Create PPM format
    header = "P6\\n{}\\n{}\\n255\\n".format(width, height)
    img_data = header.encode() + array
    
    encoded = base64.b64encode(img_data).decode('utf-8')
    print(json.dumps({"success": True, "image": encoded, "width": width, "height": height}))
else:
    print(json.dumps({"success": False, "error": "Failed to capture"}))
''', timeout=15)
        
        try:
            if output:
                data = json.loads(output)
                if data.get("success"):
                    return data.get("image"), None
                return None, data.get("error", "Failed to capture")
        except:
            pass
        return None, error or "Failed to capture camera frame"
    
    def ask_are_you_okay(self):
        """NAO asks 'Are you okay? Please respond' """
        return self.speak("Are you okay? Please respond if you can hear me.")
    
    def listen_for_response(self, duration=10):
        """
        Use NAO's speech recognition to listen for any verbal response.
        Returns: (got_response, response_text)
        """
        if not self.connected:
            return False, ""
        
        output, error = self._execute_naoqi(f'''
import time

asr = ALProxy("ALSpeechRecognition", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)

# Set vocabulary - listen for any response
vocabulary = ["yes", "no", "help", "okay", "fine", "good", "here", "hello"]
asr.setVocabulary(vocabulary, False)

# Start listening
asr.subscribe("FallResponseListener")

start_time = time.time()
got_response = False
response_text = ""

while time.time() - start_time < {duration}:
    word_data = memory.getData("WordRecognized")
    if word_data and len(word_data) > 1:
        word = word_data[0]
        confidence = word_data[1]
        if confidence > 0.3 and word in vocabulary:
            got_response = True
            response_text = word
            break
    time.sleep(0.5)

asr.unsubscribe("FallResponseListener")
print(json.dumps({{"got_response": got_response, "response_text": response_text}}))
''', timeout=duration + 15)
        
        try:
            if output:
                data = json.loads(output)
                return data.get("got_response", False), data.get("response_text", "")
        except:
            pass
        return False, ""
    
    def play_alert_sound(self):
        """Play a loud alert sound on NAO"""
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        
        output, error = self._execute_naoqi('''
import time

audio = ALProxy("ALAudioPlayer", robot_ip, port)
tts = ALProxy("ALTextToSpeech", robot_ip, port)

# Increase volume
audio.setMasterVolume(1.0)

# Play alert sound or use TTS with loud voice
tts.setVolume(1.0)
tts.say("Alert! Alert! Emergency! Someone may have fallen!")

# Beep pattern
for i in range(3):
    tts.say("Beep")
    time.sleep(0.3)

print(json.dumps({"success": True}))
''', timeout=30)
        
        if output and "success" in output:
            return {"success": True, "message": "Alert sound played"}
        return {"success": False, "message": error or "Failed to play alert"}
    
    def move_closer(self):
        """Move NAO closer to the detected person"""
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        
        output, error = self._execute_naoqi('''
import time

motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()

# Move forward slowly
motion.moveTo(0.3, 0, 0)  # Move 30cm forward
time.sleep(2)
motion.stopMove()

# Look down to see person on ground
motion.setAngles("HeadPitch", 0.4, 0.2)  # Look down

print(json.dumps({"success": True}))
''', timeout=20)
        
        if output and "success" in output:
            return {"success": True, "message": "Moved closer"}
        return {"success": False, "message": error or "Failed to move"}


# Global controller
nao = NAOController()


# ==================== Email Functions ====================
def send_alert_email(image_cv2=None):
    """Send fall detection alert email with optional photo attachment"""
    global fall_state
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"FALL ALERT - NAO Robot Detection - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Email body
        body = f"""
FALL DETECTION ALERT

NAO Robot has detected a potential fall incident.

Details:
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Robot IP: {nao.nao_ip}
- Detection: Laptop-based OpenCV analysis
- Action Taken: NAO asked "Are you okay?" - No verbal response received
- Alert Sound: Played

IMMEDIATE ACTION REQUIRED

Please check on the person immediately or contact emergency services if needed.

---
This is an automated alert from NAO Fall Detection System.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach photo if available (OpenCV format)
        if image_cv2 is not None and OPENCV_AVAILABLE:
            try:
                # Encode as JPEG
                _, img_encoded = cv2.imencode('.jpg', image_cv2)
                image_data = img_encoded.tobytes()
                
                image = MIMEImage(image_data, name='fall_detection.jpg')
                image.add_header('Content-Disposition', 'attachment', filename='fall_detection_photo.jpg')
                msg.attach(image)
            except Exception as img_error:
                print(f"Failed to attach image: {img_error}")
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        fall_state.last_alert = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Alert email sent to {RECEIVER_EMAIL}")
        return True
        
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# ==================== Fall Detection Monitoring ====================
def fall_detection_loop():
    """
    Background thread for fall detection
    - NAO captures camera frames (light operation)
    - Laptop analyzes images using OpenCV (heavy operation)
    """
    global fall_state, nao, laptop_detector
    
    print("=" * 50)
    print("Fall detection started (Laptop-based detection)")
    print("NAO: Camera capture only (light)")
    print("Laptop: OpenCV analysis (heavy processing)")
    print("=" * 50)
    
    fall_state.status = "monitoring"
    fall_state.message = "Monitoring... (detection on laptop)"
    
    horizontal_start_time = None
    
    while not fall_state.stop_event.is_set():
        try:
            if not nao.connected:
                fall_state.status = "error"
                fall_state.message = "Robot disconnected"
                time.sleep(2)
                continue
            
            # Step 1: Capture frame from NAO (LIGHT on robot)
            print("Capturing frame from NAO camera...")
            image_base64, error = nao.capture_camera_frame()
            
            if not image_base64:
                print(f"Camera capture failed: {error}")
                time.sleep(DETECTION_CHECK_INTERVAL)
                continue
            
            # Step 2: Analyze on LAPTOP using OpenCV (HEAVY on laptop, not robot!)
            print("Analyzing image on laptop...")
            is_horizontal, confidence, details = laptop_detector.detect_horizontal_person(image_base64)
            
            print(f"Detection result: horizontal={is_horizontal}, confidence={confidence:.2f}")
            print(f"Details: {details}")
            
            if is_horizontal and confidence > 0.5:
                if horizontal_start_time is None:
                    horizontal_start_time = time.time()
                    fall_state.status = "person_detected"
                    fall_state.message = f"Person may be horizontal (conf: {confidence:.0%})"
                    fall_state.person_horizontal_since = horizontal_start_time
                    print(">>> Person detected horizontal - starting timer")
                
                # Check if horizontal for too long
                elapsed = time.time() - horizontal_start_time
                fall_state.message = f"Person horizontal for {elapsed:.0f}s (threshold: {HORIZONTAL_DETECTION_SECONDS}s)"
                
                if elapsed >= HORIZONTAL_DETECTION_SECONDS:
                    print(f">>> Person horizontal for {elapsed:.1f}s - initiating alert!")
                    fall_state.status = "checking"
                    fall_state.message = "Checking on person..."
                    
                    # Step 3: Move closer
                    nao.move_closer()
                    time.sleep(1)
                    
                    # Step 4: Ask "Are you okay?"
                    nao.ask_are_you_okay()
                    fall_state.message = "Asked 'Are you okay?' - listening..."
                    
                    # Step 5: Listen for verbal response
                    got_response, response_text = nao.listen_for_response(VERBAL_RESPONSE_WAIT_SECONDS)
                    
                    if got_response:
                        print(f">>> Got response: {response_text}")
                        fall_state.status = "monitoring"
                        fall_state.message = f"Person responded: '{response_text}'"
                        nao.speak("Okay, I'm glad you're alright.")
                        horizontal_start_time = None
                    else:
                        print(">>> No response - playing alert!")
                        fall_state.message = "No response - alerting..."
                        
                        # Step 6: Play loud alert sound
                        nao.play_alert_sound()
                        
                        time.sleep(FINAL_ALERT_WAIT_SECONDS)
                        
                        # Step 7: Send email with photo
                        print(">>> Sending alert email...")
                        fall_state.message = "Sending email alert..."
                        
                        # Use the last analyzed frame
                        if send_alert_email(fall_state.last_frame):
                            fall_state.status = "alert_sent"
                            fall_state.message = f"Alert sent to {RECEIVER_EMAIL}"
                            nao.speak("I have sent an alert email to your caretaker.")
                        else:
                            fall_state.message = "Email failed, but alert was raised"
                        
                        horizontal_start_time = None
                        time.sleep(30)  # Cool down
                        fall_state.status = "monitoring"
                        fall_state.message = "Resuming monitoring..."
            else:
                # Person not horizontal
                if horizontal_start_time is not None:
                    print(">>> Person no longer horizontal - reset")
                    horizontal_start_time = None
                    fall_state.person_horizontal_since = None
                
                fall_state.status = "monitoring"
                fall_state.message = f"Monitoring... (last check: {details[:50]})"
            
            # Wait before next check
            time.sleep(DETECTION_CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Fall detection error: {e}")
            fall_state.status = "error"
            fall_state.message = f"Error: {str(e)}"
            time.sleep(5)
    
    print("Fall detection stopped")
    fall_state.status = "idle"
    fall_state.message = "Fall detection stopped"


# ==================== API Routes ====================

@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({
        "message": "NAO Robot REST API Server",
        "version": "2.1.0",
        "nao_ip": NAO_IP,
        "features": ["movement", "speech", "gestures", "sensors", "fall_detection"],
        "fall_detection_mode": "laptop-based (OpenCV)" if OPENCV_AVAILABLE else "basic"
    })

@app.route('/api/robot/connect', methods=['POST'])
def connect():
    data = request.get_json() or {}
    ip = data.get('ip_address', NAO_IP)
    username = data.get('username', SSH_USERNAME)
    password = data.get('password', SSH_PASSWORD)
    
    result = nao.connect(ip, username, password)
    
    if result.get('success'):
        return jsonify({
            "success": True,
            "message": result['message'],
            "status": nao.get_status()
        })
    return jsonify(result)

@app.route('/api/robot/disconnect', methods=['POST'])
def disconnect():
    # Stop fall detection if running
    if fall_state.is_active:
        fall_state.stop_event.set()
        if fall_state.monitoring_thread:
            fall_state.monitoring_thread.join(timeout=5)
        fall_state.is_active = False
    
    nao.disconnect()
    return jsonify({"success": True, "message": "Disconnected"})

@app.route('/api/robot/status', methods=['GET'])
def status():
    return jsonify(nao.get_status())

@app.route('/api/robot/sensors', methods=['GET'])
def sensors():
    return jsonify(nao.get_sensors())

@app.route('/api/robot/move', methods=['POST'])
def move():
    data = request.get_json() or {}
    x = float(data.get('x', 0))
    y = float(data.get('y', 0))
    theta = float(data.get('theta', 0))
    return jsonify(nao.move(x, y, theta))

@app.route('/api/robot/stop', methods=['POST'])
def stop():
    return jsonify(nao.stop())

@app.route('/api/robot/speak', methods=['POST'])
def speak():
    data = request.get_json() or {}
    text = data.get('text', '')
    return jsonify(nao.speak(text))

@app.route('/api/robot/gesture', methods=['POST'])
def gesture():
    data = request.get_json() or {}
    name = data.get('gesture_name', '')
    speed = float(data.get('speed', 1.0))
    return jsonify(nao.gesture(name, speed))

@app.route('/api/robot/gestures', methods=['GET'])
def gestures():
    return jsonify({
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
    })

@app.route('/api/robot/camera/frame', methods=['GET'])
def camera_frame():
    photo, error = nao.capture_camera_frame()
    if photo:
        return jsonify({"success": True, "frame": photo})
    return jsonify({"success": False, "error": error or "Camera not available"}), 501


# ==================== Fall Detection API Routes ====================

@app.route('/api/robot/fall_detection/start', methods=['POST'])
def start_fall_detection():
    global fall_state
    
    if not nao.connected:
        return jsonify({"success": False, "message": "Robot not connected"})
    
    if not OPENCV_AVAILABLE:
        return jsonify({
            "success": False, 
            "message": "OpenCV not installed on laptop. Run: pip install opencv-python numpy"
        })
    
    if fall_state.is_active:
        return jsonify({"success": True, "message": "Fall detection already active"})
    
    # Start monitoring thread
    fall_state.stop_event.clear()
    fall_state.is_active = True
    fall_state.monitoring_thread = threading.Thread(target=fall_detection_loop, daemon=True)
    fall_state.monitoring_thread.start()
    
    # Announce activation
    nao.speak("Fall detection activated. I will monitor using my camera.")
    
    return jsonify({
        "success": True,
        "message": "Fall detection started (laptop-based analysis)",
        "status": fall_state.status,
        "detection_mode": "OpenCV on laptop"
    })

@app.route('/api/robot/fall_detection/stop', methods=['POST'])
def stop_fall_detection():
    global fall_state
    
    if not fall_state.is_active:
        return jsonify({"success": True, "message": "Fall detection already stopped"})
    
    fall_state.stop_event.set()
    if fall_state.monitoring_thread:
        fall_state.monitoring_thread.join(timeout=5)
    
    fall_state.is_active = False
    fall_state.status = "idle"
    fall_state.message = "Fall detection stopped"
    
    if nao.connected:
        nao.speak("Fall detection deactivated.")
    
    return jsonify({
        "success": True,
        "message": "Fall detection stopped"
    })

@app.route('/api/robot/fall_detection/status', methods=['GET'])
def fall_detection_status():
    return jsonify({
        "active": fall_state.is_active,
        "status": fall_state.status,
        "message": fall_state.message,
        "last_alert": fall_state.last_alert,
        "person_horizontal_since": fall_state.person_horizontal_since,
        "opencv_available": OPENCV_AVAILABLE
    })

@app.route('/api/robot/fall_detection/test', methods=['POST'])
def test_fall_detection():
    """Test the fall detection alert system"""
    if not nao.connected:
        return jsonify({"success": False, "message": "Robot not connected"})
    
    results = []
    
    # Test 1: Camera capture
    nao.speak("Testing camera.")
    image, error = nao.capture_camera_frame()
    if image:
        results.append("Camera: OK")
    else:
        results.append(f"Camera: FAILED - {error}")
    
    # Test 2: OpenCV detection
    if OPENCV_AVAILABLE and image:
        is_h, conf, details = laptop_detector.detect_horizontal_person(image)
        results.append(f"OpenCV: OK (detected={is_h}, conf={conf:.2f})")
    else:
        results.append("OpenCV: Not available")
    
    # Test 3: Speech
    nao.speak("Testing speech. Are you okay?")
    results.append("Speech: OK")
    time.sleep(2)
    
    # Test 4: Alert sound
    nao.play_alert_sound()
    results.append("Alert Sound: OK")
    time.sleep(1)
    
    # Test 5: Email
    nao.speak("Testing email alert.")
    if send_alert_email(fall_state.last_frame):
        results.append(f"Email: Sent to {RECEIVER_EMAIL}")
    else:
        results.append("Email: FAILED")
    
    nao.speak("Test complete.")
    
    return jsonify({
        "success": True,
        "message": "Test complete",
        "results": results
    })


# ==================== Main ====================

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

if __name__ == '__main__':
    local_ip = get_local_ip()
    
    print("=" * 70)
    print("  NAO Robot REST API Server with Fall Detection")
    print("  Version 2.1 - Laptop-based Detection (Light on Robot)")
    print("=" * 70)
    print(f"\n  NAO Robot IP: {NAO_IP}")
    print(f"  Server running on: http://{local_ip}:{SERVER_PORT}")
    print(f"\n  In the mobile app, enter:")
    print(f"    IP Address: {local_ip}")
    print(f"    Port: {SERVER_PORT}")
    print(f"\n  Fall Detection:")
    print(f"    Mode: {'OpenCV on Laptop' if OPENCV_AVAILABLE else 'OPENCV NOT INSTALLED'}")
    print(f"    Camera: NAO (light capture only)")
    print(f"    Analysis: Laptop (heavy processing)")
    print(f"\n  Email Alerts:")
    print(f"    Sender: {SENDER_EMAIL}")
    print(f"    Receiver: {RECEIVER_EMAIL}")
    
    if not OPENCV_AVAILABLE:
        print("\n  ⚠️  WARNING: OpenCV not installed!")
        print("  Run: pip install opencv-python numpy")
    
    print("\n" + "=" * 70)
    print("  Press Ctrl+C to stop the server")
    print("=" * 70 + "\n")
    
    print("Connecting to NAO automatically...")
    result = nao.connect(NAO_IP)
    if result.get('success'):
        print(f"SUCCESS: {result['message']}")
    else:
        print(f"FAILED: {result['message']}")
        print("\nYou can still start the server - connect via the app later.")
    
    print(f"\nStarting server on http://0.0.0.0:{SERVER_PORT}...")
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)
