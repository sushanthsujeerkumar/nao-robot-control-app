#!/usr/bin/env python3
"""
NAO Robot REST API Server - Fall Detection + Exercise v3.0
Includes: Fall Detection (camera-based) and Exercise Session (FSM-based)
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
    print("OpenCV not found - Fall detection limited")

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

# Fall Detection Settings
HORIZONTAL_DETECTION_SECONDS = 12
VERBAL_RESPONSE_WAIT_SECONDS = 10
FINAL_ALERT_WAIT_SECONDS = 10
DETECTION_CHECK_INTERVAL = 3

# Exercise Settings
SQUAT_REPS = 3
ARM_STRETCH_REPS = 3
SPEECH_SPEED = 90

# LED Colors (RGB)
LED_BLUE = 0x0000FF
LED_GREEN = 0x00FF00
LED_YELLOW = 0xFFFF00
LED_RED = 0xFF0000
LED_WHITE = 0xFFFFFF

app = Flask(__name__)
CORS(app)

# ==================== FALL DETECTION STATE ====================
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

# ==================== EXERCISE STATE ====================
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
        self.context = {"repeat_count": 0, "continue_choice": "yes"}

exercise_state = ExerciseState()

# ==================== LAPTOP DETECTOR ====================
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
            return False, 0.0, "OpenCV not available"
        try:
            img = self.ppm_to_cv2(image_base64)
            if img is None:
                return False, 0.0, "Failed to decode"
            fall_state.last_frame = img
            small = cv2.resize(img, None, fx=0.5, fy=0.5)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            is_horizontal = False
            confidence = 0.0
            details = []
            persons, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(4, 4), scale=1.05)
            for i, (x, y, w, h) in enumerate(persons):
                aspect = w / h if h > 0 else 0
                if aspect > 1.2:
                    is_horizontal = True
                    confidence = max(confidence, min(0.9, aspect / 2))
                if (y + h/2) / small.shape[0] > 0.6:
                    confidence = max(confidence, 0.7)
                details.append(f"Person:{aspect:.2f}")
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(20, 20))
            for (x, y, w, h) in faces:
                face_y = (y + h/2) / small.shape[0]
                if face_y > 0.65:
                    confidence = max(confidence, 0.6)
                details.append(f"Face:{face_y:.2f}")
            if confidence > 0.5:
                is_horizontal = True
            return is_horizontal, confidence, " ".join(details) if details else "None"
        except Exception as e:
            return False, 0.0, str(e)

laptop_detector = LaptopDetector()

# ==================== NAO CONTROLLER ====================
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
            out, err = self._execute_naoqi('ALProxy("ALTextToSpeech", robot_ip, port).say("Connected")')
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
        return {"success": True, "message": "Moving"}
    
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
            "standinit": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("StandInit", {speed})',
            "wave": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], [1.0, -0.2, 1.2, 0.5], 0.15)
time.sleep(1.0)
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], [1.3, -0.1, 1.0, 0.3], 0.15)
time.sleep(1.0)
''',
        }
        code = gestures.get(name.lower())
        if code:
            self._execute_naoqi(code, timeout=30)
        return {"success": True}
    
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
posture.goToPosture("StandInit", 0.5)
motion.rest()
''')
    
    def arms_forward(self):
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.8, 0.8], 0.1)
time.sleep(1.0)
''')
    
    def arms_up(self):
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.4, 0.4], 0.1)
time.sleep(1.0)
''')
    
    def arms_down(self):
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.1)
time.sleep(1.0)
''')
    
    def small_encouragement(self):
        if not self.connected:
            return
        self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.0, 1.0], 0.15)
time.sleep(0.7)
motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.3, 1.3], 0.15)
time.sleep(0.7)
''')
    
    def neutral_posture(self):
        if not self.connected:
            return
        self._execute_naoqi('ALProxy("ALRobotPosture", robot_ip, port).goToPosture("StandInit", 0.5)')
    
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
        if not self.connected:
            return False, ""
        out, _ = self._execute_naoqi(f'''
import time
asr = ALProxy("ALSpeechRecognition", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)
vocabulary = ["yes", "no", "help", "okay", "fine", "good", "start", "ready", "stop", "continue", "go"]
asr.setVocabulary(vocabulary, False)
asr.subscribe("Listener")
start = time.time()
got = False
text = ""
while time.time() - start < {duration}:
    data = memory.getData("WordRecognized")
    if data and len(data) > 1 and data[1] > 0.3:
        got = True
        text = data[0]
        break
    time.sleep(0.5)
asr.unsubscribe("Listener")
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

# ==================== EMAIL ====================
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

# ==================== FALL DETECTION LOOP ====================
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
                fall_state.message = f"Monitoring... ({details[:30]})"
            time.sleep(DETECTION_CHECK_INTERVAL)
        except Exception as e:
            print(f"Fall error: {e}")
            time.sleep(5)
    fall_state.status = "idle"
    fall_state.message = "Stopped"

# ==================== EXERCISE FSM ====================
EXERCISE_PROMPTS = {
    "GREETING": "Hello. I am ready for our gentle exercise session.",
    "READINESS": "Touch my hand, or say start, when you are ready.",
    "READINESS_REPEAT": "Please let me know when you are ready.",
    "SQUAT_INTRO": "We will begin with a gentle supported squat movement.",
    "SQUAT_COUNT": "Bend gently, and rise slowly.",
    "SQUAT_PRAISE": "Very good. Keep going.",
    "CONTINUE_CHECK": "Would you like to continue to the arm stretch?",
    "ARM_STRETCH_INTRO": "Now we will do a simple arm stretch together.",
    "ARM_STRETCH_COUNT": "Raise your arms slowly with me.",
    "COOLDOWN": "Let us slow down and breathe calmly.",
    "FEEDBACK": "Well done. Thank you for exercising with me today.",
    "STOP": "I will stop the session now for safety.",
    "ERROR": "I am having trouble continuing the session.",
    "GOODBYE": "Session complete. Goodbye."
}

def exercise_fsm_loop():
    global exercise_state
    print("Exercise FSM started")
    exercise_state.current_state = "IDLE"
    
    while not exercise_state.stop_event.is_set():
        state = exercise_state.current_state
        print(f"Exercise state: {state}")
        
        if state == "IDLE":
            nao.wake_up()
            nao.set_led(LED_BLUE)
            exercise_state.current_state = "GREETING"
            exercise_state.status = "greeting"
            exercise_state.message = "Starting session..."
        
        elif state == "GREETING":
            nao.gesture("wave")
            nao.speak(EXERCISE_PROMPTS["GREETING"])
            exercise_state.current_state = "READINESS"
            exercise_state.status = "readiness"
            exercise_state.message = "Waiting for you to be ready..."
        
        elif state == "READINESS":
            nao.set_led(LED_YELLOW)
            nao.speak(EXERCISE_PROMPTS["READINESS"])
            exercise_state.waiting_for_response = True
            exercise_state.message = "Say 'yes' or 'start' when ready"
            
            # Wait for response (from app button or speech)
            response = wait_for_exercise_response(timeout=30)
            exercise_state.waiting_for_response = False
            
            if response in ["yes", "start", "ready", "go"]:
                exercise_state.context["repeat_count"] = 0
                exercise_state.current_state = "SQUAT"
            elif response == "stop":
                exercise_state.current_state = "SAFETY_STOP"
            else:
                exercise_state.context["repeat_count"] += 1
                if exercise_state.context["repeat_count"] <= 2:
                    nao.speak(EXERCISE_PROMPTS["READINESS_REPEAT"])
                else:
                    exercise_state.current_state = "SESSION_END"
        
        elif state == "SQUAT":
            nao.set_led(LED_GREEN)
            exercise_state.status = "squat"
            exercise_state.current_exercise = "Squats"
            exercise_state.message = "Performing squats..."
            nao.speak(EXERCISE_PROMPTS["SQUAT_INTRO"])
            
            for rep in range(1, SQUAT_REPS + 1):
                if exercise_state.stop_event.is_set():
                    break
                exercise_state.message = f"Squat {rep}/{SQUAT_REPS}"
                nao.speak(f"Squat repetition {rep}.")
                nao.speak(EXERCISE_PROMPTS["SQUAT_COUNT"])
                nao.arms_forward()
                nao.speak(EXERCISE_PROMPTS["SQUAT_PRAISE"])
                nao.small_encouragement()
            
            exercise_state.current_state = "CONTINUE_CHECK"
        
        elif state == "CONTINUE_CHECK":
            exercise_state.status = "continue_check"
            exercise_state.message = "Continue to arm stretches?"
            nao.speak(EXERCISE_PROMPTS["CONTINUE_CHECK"])
            exercise_state.waiting_for_response = True
            
            response = wait_for_exercise_response(timeout=20)
            exercise_state.waiting_for_response = False
            
            if response in ["yes", "continue", "go"]:
                exercise_state.current_state = "ARM_STRETCH"
            elif response == "stop":
                exercise_state.current_state = "SAFETY_STOP"
            else:
                exercise_state.current_state = "COOLDOWN"
        
        elif state == "ARM_STRETCH":
            nao.set_led(LED_GREEN)
            exercise_state.status = "arm_stretch"
            exercise_state.current_exercise = "Arm Stretches"
            exercise_state.message = "Performing arm stretches..."
            nao.speak(EXERCISE_PROMPTS["ARM_STRETCH_INTRO"])
            
            for rep in range(1, ARM_STRETCH_REPS + 1):
                if exercise_state.stop_event.is_set():
                    break
                exercise_state.message = f"Arm stretch {rep}/{ARM_STRETCH_REPS}"
                nao.speak(f"Arm stretch repetition {rep}.")
                nao.speak(EXERCISE_PROMPTS["ARM_STRETCH_COUNT"])
                nao.arms_up()
                nao.arms_down()
            
            exercise_state.current_state = "COOLDOWN"
        
        elif state == "COOLDOWN":
            nao.set_led(LED_BLUE)
            exercise_state.status = "cooldown"
            exercise_state.current_exercise = "Cooldown"
            exercise_state.message = "Cooling down..."
            nao.neutral_posture()
            nao.speak(EXERCISE_PROMPTS["COOLDOWN"])
            nao.speak("Breathe in slowly.")
            time.sleep(2)
            nao.speak("And breathe out slowly.")
            time.sleep(2)
            exercise_state.current_state = "FEEDBACK"
        
        elif state == "FEEDBACK":
            nao.set_led(LED_GREEN)
            exercise_state.status = "feedback"
            exercise_state.message = "Session complete!"
            nao.speak(EXERCISE_PROMPTS["FEEDBACK"])
            exercise_state.current_state = "SESSION_END"
        
        elif state == "SAFETY_STOP":
            nao.set_led(LED_RED)
            exercise_state.status = "error"
            exercise_state.message = "Session stopped for safety"
            nao.neutral_posture()
            nao.speak(EXERCISE_PROMPTS["STOP"])
            exercise_state.current_state = "SESSION_END"
        
        elif state == "ERROR":
            nao.set_led(LED_RED)
            exercise_state.status = "error"
            exercise_state.message = "An error occurred"
            nao.neutral_posture()
            nao.speak(EXERCISE_PROMPTS["ERROR"])
            exercise_state.current_state = "SESSION_END"
        
        elif state == "SESSION_END":
            nao.set_led(LED_WHITE)
            exercise_state.status = "session_end"
            exercise_state.message = "Session ended"
            exercise_state.current_exercise = ""
            nao.speak(EXERCISE_PROMPTS["GOODBYE"])
            nao.rest()
            break
        
        time.sleep(0.5)
    
    exercise_state.is_active = False
    exercise_state.status = "idle"
    exercise_state.message = "Exercise session ended"
    print("Exercise FSM ended")

def wait_for_exercise_response(timeout=20):
    """Wait for response from app button or NAO speech recognition"""
    exercise_state.user_response = None
    exercise_state.response_event.clear()
    
    # Try to get speech response while waiting
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check if app sent a response
        if exercise_state.response_event.is_set():
            return exercise_state.user_response or "timeout"
        
        # Check if stopped
        if exercise_state.stop_event.is_set():
            return "stop"
        
        time.sleep(0.5)
    
    # Try speech recognition as fallback
    got, text = nao.listen_for_response(5)
    if got:
        return text.lower()
    
    return "timeout"

# ==================== API ROUTES ====================
@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({"message": "NAO Robot API v3.0", "features": ["fall_detection", "exercise"], "opencv": OPENCV_AVAILABLE})

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
    return jsonify(nao.gesture(data.get('gesture_name', '')))

@app.route('/api/robot/gestures', methods=['GET'])
def gestures():
    return jsonify({"gestures": [{"name": "wave"}, {"name": "sit"}, {"name": "stand"}, {"name": "standinit"}]})

# ==================== FALL DETECTION ROUTES ====================
@app.route('/api/robot/fall_detection/start', methods=['POST'])
def start_fall_detection():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    if fall_state.is_active:
        return jsonify({"success": True, "message": "Already running"})
    fall_state.stop_event.clear()
    fall_state.is_active = True
    fall_state.monitoring_thread = threading.Thread(target=fall_detection_loop, daemon=True)
    fall_state.monitoring_thread.start()
    nao.speak("Fall detection activated.")
    return jsonify({"success": True, "message": "Started"})

@app.route('/api/robot/fall_detection/stop', methods=['POST'])
def stop_fall_detection():
    if fall_state.is_active:
        fall_state.stop_event.set()
        fall_state.is_active = False
        nao.speak("Fall detection stopped.")
    fall_state.status = "idle"
    fall_state.message = "Stopped"
    return jsonify({"success": True})

@app.route('/api/robot/fall_detection/status', methods=['GET'])
def fall_detection_status():
    return jsonify({"active": fall_state.is_active, "status": fall_state.status, "message": fall_state.message, "last_alert": fall_state.last_alert})

@app.route('/api/robot/fall_detection/test', methods=['POST'])
def test_fall_detection():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    results = []
    nao.speak("Testing.")
    img, err = nao.capture_camera_frame()
    results.append(f"Camera: {'OK' if img else 'FAILED'}")
    if OPENCV_AVAILABLE and img:
        h, c, d = laptop_detector.detect_horizontal_person(img)
        results.append(f"OpenCV: OK ({c:.2f})")
    nao.speak("Are you okay?")
    results.append("Speech: OK")
    nao.play_alert_sound()
    results.append("Alert: OK")
    if send_alert_email(fall_state.last_frame):
        results.append(f"Email: Sent")
    else:
        results.append("Email: FAILED")
    nao.speak("Test complete.")
    return jsonify({"success": True, "results": results})

# ==================== EXERCISE ROUTES ====================
@app.route('/api/robot/exercise/start', methods=['POST'])
def start_exercise():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    if exercise_state.is_active:
        return jsonify({"success": True, "message": "Already running"})
    
    # Stop fall detection if running
    if fall_state.is_active:
        fall_state.stop_event.set()
        fall_state.is_active = False
    
    exercise_state.stop_event.clear()
    exercise_state.is_active = True
    exercise_state.current_state = "IDLE"
    exercise_state.context = {"repeat_count": 0, "continue_choice": "yes"}
    exercise_state.exercise_thread = threading.Thread(target=exercise_fsm_loop, daemon=True)
    exercise_state.exercise_thread.start()
    return jsonify({"success": True, "message": "Exercise started"})

@app.route('/api/robot/exercise/stop', methods=['POST'])
def stop_exercise():
    if exercise_state.is_active:
        exercise_state.stop_event.set()
        exercise_state.response_event.set()  # Unblock any waiting
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
        "waiting_for_response": exercise_state.waiting_for_response,
        "current_state": exercise_state.current_state
    })

@app.route('/api/robot/exercise/respond', methods=['POST'])
def exercise_respond():
    data = request.get_json() or {}
    response = data.get('response', '').lower()
    exercise_state.user_response = response
    exercise_state.response_event.set()
    return jsonify({"success": True, "response": response})

# ==================== MAIN ====================
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
    print("  NAO Robot API v3.0 - Fall Detection + Exercise")
    print("="*60)
    print(f"  NAO: {NAO_IP}")
    print(f"  Server: http://{local_ip}:{SERVER_PORT}")
    print(f"  Features: Fall Detection, Exercise Session")
    print(f"  OpenCV: {'YES' if OPENCV_AVAILABLE else 'NO'}")
    print("="*60)
    
    result = nao.connect(NAO_IP)
    print(f"NAO: {result['message']}")
    
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)
