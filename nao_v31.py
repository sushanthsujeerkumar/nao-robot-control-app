#!/usr/bin/env python3
"""
NAO Robot REST API Server - Fall Detection + Exercise v3.1
With full gesture support and robot exercise demonstrations
"""

import json
import time
import sys
import socket
import threading
import base64
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

if sys.version_info[0] < 3:
    print("Python 3 required")
    sys.exit(1)

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import paramiko
except ImportError as e:
    print(f"Missing: {e}")
    print("Run: pip install paramiko flask flask-cors opencv-python numpy")
    sys.exit(1)

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
    print("OpenCV loaded")
except ImportError:
    OPENCV_AVAILABLE = False
    print("OpenCV not found")

# ==================== CONFIG ====================
NAO_IP = "172.18.16.35"
SSH_USERNAME = "nao"
SSH_PASSWORD = "nao"
SERVER_PORT = 5000

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "coldiot34@gmail.com"
SENDER_PASSWORD = "ldyl ufwa awox jwqu"
RECEIVER_EMAIL = "sushanthsujeerkumar@gmail.com"

HORIZONTAL_DETECTION_SECONDS = 12
VERBAL_RESPONSE_WAIT_SECONDS = 10
FINAL_ALERT_WAIT_SECONDS = 10
DETECTION_CHECK_INTERVAL = 3

SQUAT_REPS = 3
ARM_STRETCH_REPS = 3

LED_BLUE = 0x0000FF
LED_GREEN = 0x00FF00
LED_YELLOW = 0xFFFF00
LED_RED = 0xFF0000
LED_WHITE = 0xFFFFFF

app = Flask(__name__)
CORS(app)

class FallDetectionState:
    def __init__(self):
        self.is_active = False
        self.status = "idle"
        self.message = "Fall detection not active"
        self.last_alert = None
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        self.last_frame = None

fall_state = FallDetectionState()

class ExerciseState:
    def __init__(self):
        self.is_active = False
        self.current_state = "IDLE"
        self.status = "idle"
        self.message = "Exercise not started"
        self.current_exercise = ""
        self.waiting_for_response = False
        self.user_response = None
        self.response_event = threading.Event()
        self.exercise_thread = None
        self.stop_event = threading.Event()
        self.context = {"repeat_count": 0}

exercise_state = ExerciseState()

class LaptopDetector:
    def __init__(self):
        if OPENCV_AVAILABLE:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    def ppm_to_cv2(self, ppm_base64):
        try:
            raw = base64.b64decode(ppm_base64)
            parts = raw.split(b'\n', 3)
            if len(parts) >= 4:
                dims = parts[1].decode().split()
                width, height = int(dims[0]), int(dims[1])
                pixel_data = parts[3]
                if len(pixel_data) >= width * height * 3:
                    img = np.frombuffer(pixel_data[:width*height*3], dtype=np.uint8)
                    img = img.reshape((height, width, 3))
                    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except:
            pass
        return None
    
    def detect_horizontal_person(self, image_base64):
        if not OPENCV_AVAILABLE:
            return False, 0.0, "No OpenCV"
        try:
            img = self.ppm_to_cv2(image_base64)
            if img is None:
                return False, 0.0, "Decode failed"
            fall_state.last_frame = img
            small = cv2.resize(img, None, fx=0.5, fy=0.5)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            is_horizontal = False
            confidence = 0.0
            details = []
            persons, _ = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(4, 4), scale=1.05)
            for (x, y, w, h) in persons:
                aspect = w / h if h > 0 else 0
                if aspect > 1.2:
                    is_horizontal = True
                    confidence = max(confidence, min(0.9, aspect / 2))
                if (y + h/2) / small.shape[0] > 0.6:
                    confidence = max(confidence, 0.7)
                details.append(f"P:{aspect:.1f}")
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(20, 20))
            for (x, y, w, h) in faces:
                face_y = (y + h/2) / small.shape[0]
                if face_y > 0.65:
                    confidence = max(confidence, 0.6)
                details.append(f"F:{face_y:.1f}")
            if confidence > 0.5:
                is_horizontal = True
            return is_horizontal, confidence, " ".join(details) if details else "None"
        except Exception as e:
            return False, 0.0, str(e)

laptop_detector = LaptopDetector()

class NAOController:
    def __init__(self):
        self.ssh = None
        self.connected = False
        self.nao_ip = NAO_IP
        self.start_time = None
    
    def _execute_naoqi(self, code, timeout=30):
        if not self.ssh:
            return None, "Not connected"
        script = f'''python2 << 'NAOCODE'
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
            stdin, stdout, stderr = self.ssh.exec_command(script, timeout=timeout)
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            return out, err
        except Exception as e:
            return None, str(e)
    
    def _indent(self, code, spaces=4):
        return '\n'.join(' ' * spaces + line for line in code.split('\n'))
    
    def connect(self, ip, username="nao", password="nao"):
        self.nao_ip = ip
        print(f"Connecting to NAO at {ip}...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            if sock.connect_ex((ip, 22)) != 0:
                sock.close()
                return {"success": False, "message": f"Cannot reach {ip}"}
            sock.close()
        except Exception as e:
            return {"success": False, "message": str(e)}
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(ip, port=22, username=username, password=password, timeout=10)
            self._execute_naoqi('ALProxy("ALTextToSpeech", robot_ip, port).say("Connected")')
            self.connected = True
            self.start_time = time.time()
            return {"success": True, "message": f"Connected to NAO at {ip}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def disconnect(self):
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass
        self.ssh = None
        self.connected = False
    
    def get_status(self):
        if not self.connected:
            return {"connected": False}
        out, _ = self._execute_naoqi('''
battery = ALProxy("ALBattery", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)
print(json.dumps({"battery_level": battery.getBatteryCharge(), "posture": posture.getPostureFamily()}))
''')
        try:
            data = json.loads(out) if out else {}
            return {"connected": True, "ip_address": self.nao_ip, "battery_level": data.get("battery_level", 0), "temperature": 40, "robot_name": "NAO V5", "posture": data.get("posture", "Unknown"), "uptime": int(time.time() - self.start_time) if self.start_time else 0}
        except:
            return {"connected": True, "ip_address": self.nao_ip, "robot_name": "NAO V5"}
    
    def get_sensors(self):
        if not self.connected:
            return {}
        out, _ = self._execute_naoqi('''
memory = ALProxy("ALMemory", robot_ip, port)
battery = ALProxy("ALBattery", robot_ip, port)
print(json.dumps({"sonar_left": float(memory.getData("Device/SubDeviceList/US/Left/Sensor/Value") or 0), "sonar_right": float(memory.getData("Device/SubDeviceList/US/Right/Sensor/Value") or 0), "battery_level": battery.getBatteryCharge()}))
''')
        try:
            return json.loads(out) if out else {}
        except:
            return {}
    
    def move(self, x, y, theta):
        if not self.connected:
            return {"success": False}
        self._execute_naoqi(f'motion = ALProxy("ALMotion", robot_ip, port)\nmotion.wakeUp()\nmotion.moveToward({x}, {y}, {theta})')
        return {"success": True}
    
    def stop(self):
        if not self.connected:
            return {"success": False}
        self._execute_naoqi('ALProxy("ALMotion", robot_ip, port).stopMove()')
        return {"success": True}
    
    def speak(self, text):
        if not self.connected:
            return {"success": False}
        text = text.replace('"', '\\"').replace("'", "\\'")
        self._execute_naoqi(f'ALProxy("ALTextToSpeech", robot_ip, port).say("{text}")', timeout=60)
        return {"success": True}
    
    def gesture(self, name, speed=1.0):
        if not self.connected:
            return {"success": False}
        
        gestures = {
            "stand": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("Stand", {speed})',
            "sit": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("Sit", {speed})',
            "crouch": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("Crouch", {speed})',
            "standinit": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("StandInit", {speed})',
            "standzero": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("StandZero", {speed})',
            "lyingbelly": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("LyingBelly", {speed})',
            "lyingback": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("LyingBack", {speed})',
            "wave": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
names = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]
motion.setAngles(names, [-0.5, -0.3, 1.0, 0.5, 0.0], 0.2)
time.sleep(0.5)
for i in range(3):
    motion.setAngles("RWristYaw", 1.0, 0.4)
    time.sleep(0.25)
    motion.setAngles("RWristYaw", -1.0, 0.4)
    time.sleep(0.25)
motion.setAngles(names, [1.5, 0.1, 1.2, 0.5, 0.0], 0.2)
''',
            "bow": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadPitch", 0.5, 0.15)
time.sleep(1.5)
motion.setAngles("HeadPitch", 0.0, 0.15)
''',
            "yes": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
for i in range(3):
    motion.setAngles("HeadPitch", 0.3, 0.3)
    time.sleep(0.3)
    motion.setAngles("HeadPitch", -0.1, 0.3)
    time.sleep(0.3)
motion.setAngles("HeadPitch", 0.0, 0.2)
''',
            "no": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
for i in range(3):
    motion.setAngles("HeadYaw", 0.5, 0.3)
    time.sleep(0.3)
    motion.setAngles("HeadYaw", -0.5, 0.3)
    time.sleep(0.3)
motion.setAngles("HeadYaw", 0.0, 0.2)
''',
            "dance": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
tts = ALProxy("ALTextToSpeech", robot_ip, port)
motion.wakeUp()
tts.say("Dancing!")
for i in range(4):
    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.3)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.3, -0.3], 0.3)
    time.sleep(0.4)
    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.3)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.3, 0.3], 0.3)
    time.sleep(0.4)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], [1.5, 1.5, 0.1, -0.1], 0.2)
''',
            "celebrate": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.0, -1.0], 0.3)
time.sleep(0.5)
for i in range(3):
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.8, -0.8], 0.4)
    time.sleep(0.3)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.3, 0.3], 0.4)
    time.sleep(0.3)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], [1.5, 1.5, 0.1, -0.1], 0.2)
''',
            "handshake": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], [0.5, -0.2, 0.5, 0.5], 0.2)
motion.openHand("RHand")
time.sleep(2)
motion.closeHand("RHand")
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], [1.5, 0.1, 1.2, 0.5], 0.2)
''',
            "think": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], [0.3, 0.0, 1.5, 1.5], 0.15)
motion.setAngles("HeadPitch", 0.3, 0.15)
motion.setAngles("HeadYaw", 0.3, 0.15)
time.sleep(3)
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "HeadPitch", "HeadYaw"], [1.5, 0.1, 1.2, 0.5, 0.0, 0.0], 0.15)
''',
            "happy": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
tts = ALProxy("ALTextToSpeech", robot_ip, port)
motion.wakeUp()
tts.say("Yay!")
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.3)
for i in range(2):
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [1.0, -1.0], 0.5)
    time.sleep(0.3)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.0, 0.0], 0.5)
    time.sleep(0.3)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.2)
''',
            "sad": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadPitch", 0.4, 0.1)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.8, 1.8], 0.1)
time.sleep(2)
motion.setAngles(["HeadPitch", "LShoulderPitch", "RShoulderPitch"], [0.0, 1.5, 1.5], 0.1)
''',
            "angry": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.3)
motion.setAngles(["LElbowRoll", "RElbowRoll"], [-1.5, 1.5], 0.3)
time.sleep(0.5)
for i in range(2):
    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.3, 0.3], 0.4)
    time.sleep(0.2)
    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.7, 0.7], 0.4)
    time.sleep(0.2)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LElbowRoll", "RElbowRoll"], [1.5, 1.5, -0.5, 0.5], 0.2)
''',
            "surprised": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadPitch", -0.3, 0.3)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.3)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.5, -0.5], 0.3)
time.sleep(1.5)
motion.setAngles(["HeadPitch", "LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], [0.0, 1.5, 1.5, 0.1, -0.1], 0.2)
''',
            "clap": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.2)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.2, 0.2], 0.2)
time.sleep(0.3)
for i in range(4):
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.0, 0.0], 0.5)
    time.sleep(0.15)
    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.3, 0.3], 0.5)
    time.sleep(0.15)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], [1.5, 1.5, 0.1, -0.1], 0.2)
''',
            "kungfu": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
tts = ALProxy("ALTextToSpeech", robot_ip, port)
motion.wakeUp()
tts.say("Hiya!")
motion.setAngles(["LShoulderPitch", "LElbowRoll"], [0.5, -1.5], 0.3)
time.sleep(0.5)
motion.setAngles(["RShoulderPitch", "RElbowYaw", "RElbowRoll"], [0.0, 1.5, 1.0], 0.4)
time.sleep(0.5)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LElbowRoll", "RElbowYaw", "RElbowRoll"], [1.5, 1.5, -0.5, 1.2, 0.5], 0.2)
''',
            "stretch": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.5, -1.5], 0.15)
time.sleep(1)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [1.2, -1.2], 0.15)
time.sleep(1)
motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], [1.5, 1.5, 0.1, -0.1], 0.15)
''',
            "lookright": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadYaw", -0.8, 0.15)
time.sleep(1)
motion.setAngles("HeadYaw", 0.0, 0.15)
''',
            "lookleft": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadYaw", 0.8, 0.15)
time.sleep(1)
motion.setAngles("HeadYaw", 0.0, 0.15)
''',
            "lookup": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadPitch", -0.5, 0.15)
time.sleep(1)
motion.setAngles("HeadPitch", 0.0, 0.15)
''',
            "lookdown": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadPitch", 0.5, 0.15)
time.sleep(1)
motion.setAngles("HeadPitch", 0.0, 0.15)
''',
        }
        
        code = gestures.get(name.lower())
        if code:
            self._execute_naoqi(code, timeout=60)
            return {"success": True, "message": f"Executed {name}"}
        return {"success": False, "message": f"Unknown gesture: {name}"}
    
    def set_led(self, color):
        if not self.connected:
            return
        self._execute_naoqi(f'ALProxy("ALLeds", robot_ip, port).fadeRGB("FaceLeds", {color}, 0.2)')
    
    def wake_up(self):
        if not self.connected:
            return
        self._execute_naoqi('''
motion = ALProxy("ALMotion", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)
motion.wakeUp()
posture.goToPosture("StandInit", 0.5)
''')
    
    def rest(self):
        if not self.connected:
            return
        self._execute_naoqi('''
motion = ALProxy("ALMotion", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)
posture.goToPosture("Crouch", 0.5)
motion.rest()
''')
    
    def neutral_posture(self):
        if not self.connected:
            return
        self._execute_naoqi('ALProxy("ALRobotPosture", robot_ip, port).goToPosture("StandInit", 0.5)')
    
    # ==================== EXERCISE DEMONSTRATIONS ====================
    def demo_squat(self):
        """Robot demonstrates squat movement"""
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()

# Arms forward for balance
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.15)
time.sleep(0.5)

# Squat down (bend knees)
motion.setAngles(["LHipPitch", "RHipPitch"], [-0.5, -0.5], 0.1)
motion.setAngles(["LKneePitch", "RKneePitch"], [0.8, 0.8], 0.1)
motion.setAngles(["LAnklePitch", "RAnklePitch"], [-0.3, -0.3], 0.1)
time.sleep(1.5)

# Stand back up
motion.setAngles(["LHipPitch", "RHipPitch"], [0.0, 0.0], 0.1)
motion.setAngles(["LKneePitch", "RKneePitch"], [0.0, 0.0], 0.1)
motion.setAngles(["LAnklePitch", "RAnklePitch"], [0.0, 0.0], 0.1)
time.sleep(1)

# Arms back down
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.15)
''', timeout=30)
    
    def demo_arms_up(self):
        """Robot demonstrates arms up stretch"""
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()

# Raise arms slowly up
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.1)
time.sleep(0.5)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.1)
time.sleep(0.5)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.2, -1.2], 0.1)
time.sleep(1)

# Hold at top
time.sleep(1)

# Lower arms slowly
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.1)
time.sleep(0.5)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.1)
time.sleep(0.5)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.1)
''', timeout=30)
    
    def demo_side_stretch(self):
        """Robot demonstrates side stretch"""
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()

# Right arm up
motion.setAngles("RShoulderPitch", -1.5, 0.15)
motion.setAngles("RShoulderRoll", -0.3, 0.15)
time.sleep(1)

# Lean left
motion.setAngles("LHipRoll", 0.2, 0.1)
time.sleep(1.5)

# Back to center
motion.setAngles("LHipRoll", 0.0, 0.1)
motion.setAngles(["RShoulderPitch", "RShoulderRoll"], [1.5, -0.1], 0.15)
time.sleep(0.5)

# Left arm up
motion.setAngles("LShoulderPitch", -1.5, 0.15)
motion.setAngles("LShoulderRoll", 0.3, 0.15)
time.sleep(1)

# Lean right
motion.setAngles("RHipRoll", -0.2, 0.1)
time.sleep(1.5)

# Back to center
motion.setAngles("RHipRoll", 0.0, 0.1)
motion.setAngles(["LShoulderPitch", "LShoulderRoll"], [1.5, 0.1], 0.15)
''', timeout=40)
    
    def demo_breathing(self):
        """Robot demonstrates breathing exercise"""
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()

# Breathe in - expand chest, raise arms slightly
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.0, 1.0], 0.08)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.3, -0.3], 0.08)
time.sleep(3)

# Breathe out - relax
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.08)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.1, -0.1], 0.08)
time.sleep(3)
''', timeout=30)
    
    def capture_camera_frame(self):
        if not self.connected:
            return None, "Not connected"
        out, err = self._execute_naoqi('''
import base64
import time
video = ALProxy("ALVideoDevice", robot_ip, port)
resolution = 1
colorSpace = 11
fps = 10
cameraId = 0
subscriberName = "nao_cam_" + str(int(time.time() * 1000) % 100000)
try:
    clientId = video.subscribeCamera(subscriberName, cameraId, resolution, colorSpace, fps)
    time.sleep(0.5)
    naoImage = video.getImageRemote(clientId)
    video.unsubscribe(clientId)
    if naoImage is not None and len(naoImage) >= 7:
        imageWidth = naoImage[0]
        imageHeight = naoImage[1]
        imageData = naoImage[6]
        ppmHeader = "P6\\n" + str(imageWidth) + " " + str(imageHeight) + "\\n255\\n"
        ppmImage = ppmHeader + str(imageData)
        encoded = base64.b64encode(ppmImage).decode('utf-8')
        print(json.dumps({"success": True, "image": encoded, "width": imageWidth, "height": imageHeight}))
    else:
        print(json.dumps({"success": False, "error": "No image"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
''', timeout=20)
        try:
            if out:
                for line in out.split('\n'):
                    if line.strip().startswith('{'):
                        data = json.loads(line)
                        if data.get("success"):
                            return data.get("image"), None
                        return None, data.get("error")
        except:
            pass
        return None, err or "Camera failed"
    
    def listen_for_response(self, duration=10):
        """Listen for voice response with expanded vocabulary"""
        if not self.connected:
            return False, ""
        out, _ = self._execute_naoqi(f'''
import time
asr = ALProxy("ALSpeechRecognition", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)

# Expanded vocabulary for exercise
vocabulary = ["yes", "no", "help", "okay", "fine", "good", "start", "ready", "stop", "continue", "go", "please", "thank you", "more", "enough", "tired", "done", "next"]
asr.setVocabulary(vocabulary, False)
asr.subscribe("ExerciseListener")

start = time.time()
got = False
text = ""

while time.time() - start < {duration}:
    data = memory.getData("WordRecognized")
    if data and len(data) > 1 and data[1] > 0.25:
        word = data[0]
        conf = data[1]
        if word in vocabulary:
            got = True
            text = word
            break
    time.sleep(0.3)

asr.unsubscribe("ExerciseListener")
print(json.dumps({{"got": got, "text": text}}))
''', timeout=duration + 15)
        try:
            if out:
                for line in out.split('\n'):
                    if line.strip().startswith('{'):
                        data = json.loads(line)
                        return data.get("got", False), data.get("text", "")
        except:
            pass
        return False, ""
    
    def play_alert_sound(self):
        if not self.connected:
            return
        self._execute_naoqi('''
import time
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.setVolume(1.0)
tts.say("Alert! Emergency! Someone may have fallen!")
for i in range(3):
    tts.say("Beep")
    time.sleep(0.3)
''', timeout=30)
    
    def move_closer(self):
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.moveTo(0.3, 0, 0)
time.sleep(2)
motion.stopMove()
motion.setAngles("HeadPitch", 0.4, 0.2)
''', timeout=20)

nao = NAOController()

def send_alert_email(image=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"FALL ALERT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        body = f"FALL DETECTION ALERT\n\nTime: {datetime.now()}\nRobot: {nao.nao_ip}\n\nIMMEDIATE ACTION REQUIRED"
        msg.attach(MIMEText(body, 'plain'))
        if image is not None and OPENCV_AVAILABLE:
            try:
                _, enc = cv2.imencode('.jpg', image)
                img_attach = MIMEImage(enc.tobytes(), name='fall.jpg')
                msg.attach(img_attach)
            except:
                pass
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        fall_state.last_alert = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Email sent to {RECEIVER_EMAIL}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def fall_detection_loop():
    global fall_state
    print("Fall detection started")
    fall_state.status = "monitoring"
    fall_state.message = "Monitoring..."
    horizontal_start = None
    while not fall_state.stop_event.is_set():
        try:
            if not nao.connected:
                fall_state.status = "error"
                fall_state.message = "Disconnected"
                time.sleep(2)
                continue
            image, error = nao.capture_camera_frame()
            if not image:
                fall_state.message = f"Camera: {error}"
                time.sleep(DETECTION_CHECK_INTERVAL)
                continue
            is_horiz, conf, details = laptop_detector.detect_horizontal_person(image)
            if is_horiz and conf > 0.5:
                if horizontal_start is None:
                    horizontal_start = time.time()
                    fall_state.status = "person_detected"
                    fall_state.message = f"HORIZONTAL ({conf:.0%})"
                elapsed = time.time() - horizontal_start
                fall_state.message = f"Horizontal {elapsed:.0f}s / {HORIZONTAL_DETECTION_SECONDS}s"
                if elapsed >= HORIZONTAL_DETECTION_SECONDS:
                    fall_state.status = "checking"
                    nao.move_closer()
                    nao.speak("Are you okay? Please respond.")
                    fall_state.message = "Listening..."
                    got, text = nao.listen_for_response(VERBAL_RESPONSE_WAIT_SECONDS)
                    if got:
                        fall_state.status = "monitoring"
                        fall_state.message = f"Response: {text}"
                        nao.speak("Good, you are alright.")
                        horizontal_start = None
                    else:
                        nao.play_alert_sound()
                        time.sleep(FINAL_ALERT_WAIT_SECONDS)
                        send_alert_email(fall_state.last_frame)
                        fall_state.status = "alert_sent"
                        fall_state.message = f"Alert sent to {RECEIVER_EMAIL}"
                        nao.speak("Alert sent to caretaker.")
                        horizontal_start = None
                        time.sleep(30)
                        fall_state.status = "monitoring"
            else:
                if horizontal_start:
                    horizontal_start = None
                fall_state.status = "monitoring"
                fall_state.message = f"Monitoring... ({details[:20]})"
            time.sleep(DETECTION_CHECK_INTERVAL)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
    fall_state.status = "idle"
    fall_state.message = "Stopped"

PROMPTS = {
    "GREETING": "Hello! I am ready for our exercise session. I will show you how to do each exercise.",
    "READINESS": "Say yes or start when you are ready to begin.",
    "SQUAT_INTRO": "We will start with squats. Watch me demonstrate, then follow along.",
    "SQUAT_DO": "Now do it with me. Bend your knees slowly, keep your back straight, then stand up.",
    "ARM_INTRO": "Now let's do arm stretches. Watch me first.",
    "ARM_DO": "Raise your arms slowly above your head, then lower them down.",
    "COOLDOWN": "Great job! Let's cool down with some breathing.",
    "BREATHE_IN": "Breathe in slowly through your nose.",
    "BREATHE_OUT": "And breathe out slowly through your mouth.",
    "FEEDBACK": "Excellent work! You completed the exercise session. Well done!",
    "CONTINUE_CHECK": "Would you like to continue to arm stretches? Say yes or no.",
    "PRAISE": ["Very good!", "Excellent!", "Great job!", "Well done!", "Keep it up!"],
    "GOODBYE": "Thank you for exercising with me. Goodbye!"
}

import random

def exercise_fsm_loop():
    global exercise_state
    print("Exercise FSM started with demonstrations")
    exercise_state.current_state = "IDLE"
    
    while not exercise_state.stop_event.is_set():
        state = exercise_state.current_state
        print(f"State: {state}")
        
        if state == "IDLE":
            nao.wake_up()
            nao.set_led(LED_BLUE)
            exercise_state.current_state = "GREETING"
            exercise_state.status = "greeting"
            exercise_state.message = "Starting..."
        
        elif state == "GREETING":
            nao.gesture("wave")
            nao.speak(PROMPTS["GREETING"])
            exercise_state.current_state = "READINESS"
            exercise_state.status = "readiness"
            exercise_state.message = "Waiting for you..."
        
        elif state == "READINESS":
            nao.set_led(LED_YELLOW)
            nao.speak(PROMPTS["READINESS"])
            exercise_state.waiting_for_response = True
            exercise_state.message = "Say 'yes' or 'start' or tap Yes"
            
            response = wait_for_response(30)
            exercise_state.waiting_for_response = False
            
            if response in ["yes", "start", "ready", "go", "okay"]:
                exercise_state.current_state = "SQUAT"
            elif response == "stop":
                exercise_state.current_state = "STOP"
            else:
                exercise_state.context["repeat_count"] += 1
                if exercise_state.context["repeat_count"] > 2:
                    exercise_state.current_state = "END"
        
        elif state == "SQUAT":
            nao.set_led(LED_GREEN)
            exercise_state.status = "squat"
            exercise_state.current_exercise = "Squats"
            
            # Introduction
            nao.speak(PROMPTS["SQUAT_INTRO"])
            time.sleep(1)
            
            for rep in range(1, SQUAT_REPS + 1):
                if exercise_state.stop_event.is_set():
                    break
                
                exercise_state.message = f"Squat {rep}/{SQUAT_REPS} - Watch me!"
                
                # Robot demonstrates
                nao.speak(f"Squat number {rep}. Watch me.")
                nao.demo_squat()
                time.sleep(0.5)
                
                # User does it
                nao.speak(PROMPTS["SQUAT_DO"])
                exercise_state.message = f"Squat {rep}/{SQUAT_REPS} - Your turn!"
                time.sleep(4)  # Wait for user
                
                # Praise
                nao.speak(random.choice(PROMPTS["PRAISE"]))
            
            nao.speak("Squats complete!")
            exercise_state.current_state = "CONTINUE"
        
        elif state == "CONTINUE":
            exercise_state.status = "continue_check"
            exercise_state.message = "Continue to arm stretches?"
            nao.speak(PROMPTS["CONTINUE_CHECK"])
            exercise_state.waiting_for_response = True
            
            response = wait_for_response(20)
            exercise_state.waiting_for_response = False
            
            if response in ["yes", "continue", "go", "okay"]:
                exercise_state.current_state = "ARM"
            elif response in ["stop", "no", "enough", "tired", "done"]:
                exercise_state.current_state = "COOLDOWN"
            else:
                exercise_state.current_state = "COOLDOWN"
        
        elif state == "ARM":
            nao.set_led(LED_GREEN)
            exercise_state.status = "arm_stretch"
            exercise_state.current_exercise = "Arm Stretches"
            
            nao.speak(PROMPTS["ARM_INTRO"])
            time.sleep(1)
            
            for rep in range(1, ARM_STRETCH_REPS + 1):
                if exercise_state.stop_event.is_set():
                    break
                
                exercise_state.message = f"Arm stretch {rep}/{ARM_STRETCH_REPS} - Watch me!"
                
                # Robot demonstrates
                nao.speak(f"Arm stretch number {rep}. Watch me.")
                nao.demo_arms_up()
                time.sleep(0.5)
                
                # User does it
                nao.speak(PROMPTS["ARM_DO"])
                exercise_state.message = f"Arm stretch {rep}/{ARM_STRETCH_REPS} - Your turn!"
                time.sleep(4)
                
                nao.speak(random.choice(PROMPTS["PRAISE"]))
            
            nao.speak("Arm stretches complete!")
            exercise_state.current_state = "COOLDOWN"
        
        elif state == "COOLDOWN":
            nao.set_led(LED_BLUE)
            exercise_state.status = "cooldown"
            exercise_state.current_exercise = "Cooldown"
            exercise_state.message = "Cooling down..."
            
            nao.neutral_posture()
            nao.speak(PROMPTS["COOLDOWN"])
            time.sleep(1)
            
            # Breathing exercise with demonstration
            for i in range(2):
                nao.speak(PROMPTS["BREATHE_IN"])
                nao.demo_breathing()
                time.sleep(3)
                nao.speak(PROMPTS["BREATHE_OUT"])
                time.sleep(3)
            
            exercise_state.current_state = "FEEDBACK"
        
        elif state == "FEEDBACK":
            nao.set_led(LED_GREEN)
            exercise_state.status = "feedback"
            exercise_state.message = "Session complete!"
            nao.speak(PROMPTS["FEEDBACK"])
            nao.gesture("celebrate")
            exercise_state.current_state = "END"
        
        elif state == "STOP":
            nao.set_led(LED_RED)
            exercise_state.status = "error"
            exercise_state.message = "Stopped"
            nao.neutral_posture()
            nao.speak("Okay, stopping the exercise session.")
            exercise_state.current_state = "END"
        
        elif state == "END":
            nao.set_led(LED_WHITE)
            exercise_state.status = "session_end"
            exercise_state.message = "Session ended"
            exercise_state.current_exercise = ""
            nao.speak(PROMPTS["GOODBYE"])
            nao.gesture("bow")
            time.sleep(2)
            nao.rest()
            break
        
        time.sleep(0.5)
    
    exercise_state.is_active = False
    exercise_state.status = "idle"
    exercise_state.message = "Ready"
    print("Exercise ended")

def wait_for_response(timeout=20):
    """Wait for response from app button OR voice recognition"""
    exercise_state.user_response = None
    exercise_state.response_event.clear()
    
    # Start voice listening in background
    voice_result = {"got": False, "text": ""}
    
    def listen_voice():
        got, text = nao.listen_for_response(timeout - 2)
        voice_result["got"] = got
        voice_result["text"] = text
        if got:
            exercise_state.user_response = text
            exercise_state.response_event.set()
    
    voice_thread = threading.Thread(target=listen_voice, daemon=True)
    voice_thread.start()
    
    start = time.time()
    while time.time() - start < timeout:
        # Check app button response
        if exercise_state.response_event.is_set():
            response = exercise_state.user_response or "timeout"
            print(f"Got response: {response}")
            return response
        
        if exercise_state.stop_event.is_set():
            return "stop"
        
        time.sleep(0.3)
    
    # Check voice result
    if voice_result["got"]:
        return voice_result["text"].lower()
    
    return "timeout"

# ==================== API ROUTES ====================
@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({"message": "NAO API v3.1", "features": ["fall_detection", "exercise", "gestures"]})

@app.route('/api/robot/connect', methods=['POST'])
def connect():
    data = request.get_json() or {}
    result = nao.connect(data.get('ip_address', NAO_IP))
    if result.get('success'):
        return jsonify({"success": True, "message": result['message'], "status": nao.get_status()})
    return jsonify(result)

@app.route('/api/robot/disconnect', methods=['POST'])
def disconnect():
    if fall_state.is_active:
        fall_state.stop_event.set()
        fall_state.is_active = False
    if exercise_state.is_active:
        exercise_state.stop_event.set()
        exercise_state.is_active = False
    nao.disconnect()
    return jsonify({"success": True})

@app.route('/api/robot/status', methods=['GET'])
def status():
    return jsonify(nao.get_status())

@app.route('/api/robot/sensors', methods=['GET'])
def sensors():
    return jsonify(nao.get_sensors())

@app.route('/api/robot/move', methods=['POST'])
def move():
    data = request.get_json() or {}
    return jsonify(nao.move(float(data.get('x', 0)), float(data.get('y', 0)), float(data.get('theta', 0))))

@app.route('/api/robot/stop', methods=['POST'])
def stop():
    return jsonify(nao.stop())

@app.route('/api/robot/speak', methods=['POST'])
def speak():
    data = request.get_json() or {}
    return jsonify(nao.speak(data.get('text', '')))

@app.route('/api/robot/gesture', methods=['POST'])
def gesture():
    data = request.get_json() or {}
    return jsonify(nao.gesture(data.get('gesture_name', ''), float(data.get('speed', 1.0))))

@app.route('/api/robot/gestures', methods=['GET'])
def gestures():
    """Return all available gestures"""
    return jsonify({"gestures": [
        {"name": "wave", "description": "Wave hello", "icon": "hand-left"},
        {"name": "bow", "description": "Bow politely", "icon": "body"},
        {"name": "yes", "description": "Nod yes", "icon": "checkmark-circle"},
        {"name": "no", "description": "Shake head no", "icon": "close-circle"},
        {"name": "dance", "description": "Dance moves", "icon": "musical-notes"},
        {"name": "celebrate", "description": "Celebrate", "icon": "happy"},
        {"name": "handshake", "description": "Offer handshake", "icon": "hand-right"},
        {"name": "think", "description": "Thinking pose", "icon": "bulb"},
        {"name": "happy", "description": "Show happiness", "icon": "happy"},
        {"name": "sad", "description": "Show sadness", "icon": "sad"},
        {"name": "angry", "description": "Show anger", "icon": "flame"},
        {"name": "surprised", "description": "Show surprise", "icon": "alert"},
        {"name": "clap", "description": "Clap hands", "icon": "thumbs-up"},
        {"name": "kungfu", "description": "Kung fu move", "icon": "flash"},
        {"name": "stretch", "description": "Stretch arms", "icon": "fitness"},
        {"name": "stand", "description": "Stand up", "icon": "arrow-up"},
        {"name": "sit", "description": "Sit down", "icon": "arrow-down"},
        {"name": "crouch", "description": "Crouch down", "icon": "chevron-down"},
        {"name": "lookleft", "description": "Look left", "icon": "arrow-back"},
        {"name": "lookright", "description": "Look right", "icon": "arrow-forward"},
        {"name": "lookup", "description": "Look up", "icon": "caret-up"},
        {"name": "lookdown", "description": "Look down", "icon": "caret-down"},
    ]})

@app.route('/api/robot/fall_detection/start', methods=['POST'])
def start_fall():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    if fall_state.is_active:
        return jsonify({"success": True, "message": "Running"})
    fall_state.stop_event.clear()
    fall_state.is_active = True
    fall_state.monitoring_thread = threading.Thread(target=fall_detection_loop, daemon=True)
    fall_state.monitoring_thread.start()
    nao.speak("Fall detection on.")
    return jsonify({"success": True})

@app.route('/api/robot/fall_detection/stop', methods=['POST'])
def stop_fall():
    if fall_state.is_active:
        fall_state.stop_event.set()
        fall_state.is_active = False
        nao.speak("Fall detection off.")
    fall_state.status = "idle"
    fall_state.message = "Stopped"
    return jsonify({"success": True})

@app.route('/api/robot/fall_detection/status', methods=['GET'])
def fall_status():
    return jsonify({"active": fall_state.is_active, "status": fall_state.status, "message": fall_state.message, "last_alert": fall_state.last_alert})

@app.route('/api/robot/fall_detection/test', methods=['POST'])
def test_fall():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    results = []
    nao.speak("Testing.")
    img, _ = nao.capture_camera_frame()
    results.append(f"Camera: {'OK' if img else 'FAIL'}")
    nao.speak("Are you okay?")
    results.append("Speech: OK")
    nao.play_alert_sound()
    results.append("Alert: OK")
    if send_alert_email(fall_state.last_frame):
        results.append("Email: Sent")
    else:
        results.append("Email: FAIL")
    nao.speak("Test done.")
    return jsonify({"success": True, "results": results})

@app.route('/api/robot/exercise/start', methods=['POST'])
def start_exercise():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    if exercise_state.is_active:
        return jsonify({"success": True, "message": "Running"})
    if fall_state.is_active:
        fall_state.stop_event.set()
        fall_state.is_active = False
    exercise_state.stop_event.clear()
    exercise_state.is_active = True
    exercise_state.current_state = "IDLE"
    exercise_state.context = {"repeat_count": 0}
    exercise_state.exercise_thread = threading.Thread(target=exercise_fsm_loop, daemon=True)
    exercise_state.exercise_thread.start()
    return jsonify({"success": True})

@app.route('/api/robot/exercise/stop', methods=['POST'])
def stop_exercise():
    if exercise_state.is_active:
        exercise_state.stop_event.set()
        exercise_state.response_event.set()
        exercise_state.is_active = False
        nao.speak("Exercise stopped.")
        nao.rest()
    exercise_state.status = "idle"
    exercise_state.message = "Stopped"
    exercise_state.waiting_for_response = False
    return jsonify({"success": True})

@app.route('/api/robot/exercise/status', methods=['GET'])
def exercise_status():
    return jsonify({
        "active": exercise_state.is_active,
        "status": exercise_state.status,
        "message": exercise_state.message,
        "current_exercise": exercise_state.current_exercise,
        "waiting_for_response": exercise_state.waiting_for_response
    })

@app.route('/api/robot/exercise/respond', methods=['POST'])
def exercise_respond():
    data = request.get_json() or {}
    response = data.get('response', '').lower()
    exercise_state.user_response = response
    exercise_state.response_event.set()
    return jsonify({"success": True, "response": response})

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
    print("="*60)
    print("  NAO Robot API v3.1")
    print("  Features: Fall Detection + Exercise + 22 Gestures")
    print("="*60)
    print(f"  NAO: {NAO_IP}")
    print(f"  Server: http://{local_ip}:{SERVER_PORT}")
    print(f"  OpenCV: {'YES' if OPENCV_AVAILABLE else 'NO'}")
    print("="*60)
    
    result = nao.connect(NAO_IP)
    print(f"NAO: {result['message']}")
    
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)
