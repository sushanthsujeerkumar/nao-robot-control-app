#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAO Robot REST API Server with Fall Detection
Run this on your laptop that's connected to the same WiFi as your NAO robot.

Requirements:
    pip install paramiko flask flask-cors

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
    print("  pip install paramiko flask flask-cors")
    sys.exit(1)

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

fall_state = FallDetectionState()

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
    
    def capture_photo(self):
        """Capture a photo from NAO's camera and return base64 encoded image"""
        if not self.connected:
            return None, "Not connected"
        
        output, error = self._execute_naoqi('''
import vision_definitions
import base64

video = ALProxy("ALVideoDevice", robot_ip, port)

# Subscribe to camera
resolution = vision_definitions.kVGA  # 640x480
colorSpace = vision_definitions.kRGBColorSpace
fps = 5

camProxy = video.subscribeCamera("fall_detector", 0, resolution, colorSpace, fps)
import time
time.sleep(0.5)

# Get image
image = video.getImageRemote(camProxy)

if image:
    # Get image data
    width = image[0]
    height = image[1]
    array = image[6]
    
    # Convert to base64 (simple RGB to PNG conversion)
    import struct
    
    # Create a simple PPM image
    header = "P6\\n{}\\n{}\\n255\\n".format(width, height)
    img_data = header.encode() + array
    
    encoded = base64.b64encode(img_data).decode('utf-8')
    print(json.dumps({"success": True, "image": encoded, "width": width, "height": height}))
else:
    print(json.dumps({"success": False, "error": "Failed to capture image"}))

video.unsubscribe(camProxy)
''', timeout=30)
        
        try:
            if output:
                data = json.loads(output)
                if data.get("success"):
                    return data.get("image"), None
                return None, data.get("error", "Failed to capture")
        except:
            pass
        return None, error or "Failed to capture photo"
    
    def detect_person_horizontal(self):
        """
        Check if a person is lying horizontal using NAO's sensors.
        Uses face detection position to estimate if person is horizontal.
        Returns: (is_horizontal, confidence)
        """
        if not self.connected:
            return False, 0
        
        output, error = self._execute_naoqi('''
import time

face_detection = ALProxy("ALFaceDetection", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)

# Enable face detection if not already
face_detection.subscribe("FallDetector", 500, 0.0)
time.sleep(1)

# Check for face data
face_data = memory.getData("FaceDetected")

is_horizontal = False
confidence = 0.0

if face_data and len(face_data) > 0 and face_data[0]:
    # Face detected - check position
    # face_data[1] contains face info array
    # If face is detected but at unusual vertical position, person might be horizontal
    
    # Get sonar readings to check if something is on the ground
    sonar_left = memory.getData("Device/SubDeviceList/US/Left/Sensor/Value") or 999
    sonar_right = memory.getData("Device/SubDeviceList/US/Right/Sensor/Value") or 999
    
    # If sonar detects something close (< 0.5m) and face is detected at low position
    # This is a simplified heuristic
    if sonar_left < 0.5 or sonar_right < 0.5:
        # Something is close - could be fallen person
        # Look down to check
        motion = ALProxy("ALMotion", robot_ip, port)
        current_pitch = motion.getAngles("HeadPitch", True)[0]
        
        # If we need to look down significantly to see the face
        # the person might be on the ground
        if current_pitch > 0.3:  # Looking down
            is_horizontal = True
            confidence = 0.7
    
    if not is_horizontal:
        confidence = 0.3  # Face detected but seems normal

face_detection.unsubscribe("FallDetector")
print(json.dumps({"is_horizontal": is_horizontal, "confidence": confidence}))
''', timeout=15)
        
        try:
            if output:
                data = json.loads(output)
                return data.get("is_horizontal", False), data.get("confidence", 0)
        except:
            pass
        return False, 0
    
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
def send_alert_email(image_base64=None):
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
- Action Taken: NAO asked "Are you okay?" - No verbal response received
- Alert Sound: Played

IMMEDIATE ACTION REQUIRED

Please check on the person immediately or contact emergency services if needed.

---
This is an automated alert from NAO Fall Detection System.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach photo if available
        if image_base64:
            try:
                image_data = base64.b64decode(image_base64)
                image = MIMEImage(image_data, name='fall_detection.ppm')
                image.add_header('Content-Disposition', 'attachment', filename='fall_detection_photo.ppm')
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
    """Background thread for continuous fall detection monitoring"""
    global fall_state, nao
    
    print("Fall detection monitoring started")
    fall_state.status = "monitoring"
    fall_state.message = "Monitoring for fallen persons..."
    
    horizontal_start_time = None
    
    while not fall_state.stop_event.is_set():
        try:
            if not nao.connected:
                fall_state.status = "error"
                fall_state.message = "Robot disconnected"
                time.sleep(2)
                continue
            
            # Check if person is horizontal
            is_horizontal, confidence = nao.detect_person_horizontal()
            
            if is_horizontal and confidence > 0.5:
                if horizontal_start_time is None:
                    horizontal_start_time = time.time()
                    fall_state.status = "person_detected"
                    fall_state.message = "Person detected in horizontal position..."
                    fall_state.person_horizontal_since = horizontal_start_time
                    print("Person detected horizontal - starting timer")
                
                # Check if horizontal for too long
                elapsed = time.time() - horizontal_start_time
                
                if elapsed >= HORIZONTAL_DETECTION_SECONDS:
                    print(f"Person horizontal for {elapsed:.1f} seconds - initiating alert sequence")
                    fall_state.status = "checking"
                    fall_state.message = "Person horizontal too long - checking on them..."
                    
                    # Step 1: Move closer
                    nao.move_closer()
                    time.sleep(1)
                    
                    # Step 2: Ask "Are you okay?"
                    nao.ask_are_you_okay()
                    fall_state.message = "Asked 'Are you okay?' - waiting for response..."
                    
                    # Step 3: Listen for verbal response
                    got_response, response_text = nao.listen_for_response(VERBAL_RESPONSE_WAIT_SECONDS)
                    
                    if got_response:
                        print(f"Got response: {response_text}")
                        fall_state.status = "monitoring"
                        fall_state.message = f"Person responded: '{response_text}' - resuming monitoring"
                        nao.speak("Okay, I'm glad you're alright. Let me know if you need help.")
                        horizontal_start_time = None
                    else:
                        print("No verbal response - playing alert sound")
                        fall_state.message = "No response - playing alert sound..."
                        
                        # Step 4: Play loud alert sound
                        nao.play_alert_sound()
                        
                        # Wait a bit more
                        time.sleep(FINAL_ALERT_WAIT_SECONDS)
                        
                        # Step 5: Send email with photo
                        print("Sending alert email...")
                        fall_state.message = "Sending alert email to caretaker..."
                        
                        # Capture photo
                        photo, _ = nao.capture_photo()
                        
                        # Send email
                        if send_alert_email(photo):
                            fall_state.status = "alert_sent"
                            fall_state.message = f"Alert email sent to {RECEIVER_EMAIL}"
                            nao.speak("I have sent an alert email to your caretaker.")
                        else:
                            fall_state.message = "Failed to send email, but alert was raised"
                        
                        # Reset after alert
                        horizontal_start_time = None
                        time.sleep(30)  # Wait before next detection cycle
                        fall_state.status = "monitoring"
                        fall_state.message = "Resuming monitoring..."
            else:
                # Person not horizontal - reset timer
                if horizontal_start_time is not None:
                    print("Person no longer horizontal - resetting timer")
                    horizontal_start_time = None
                    fall_state.person_horizontal_since = None
                    fall_state.status = "monitoring"
                    fall_state.message = "Monitoring for fallen persons..."
            
            # Check every 2 seconds
            time.sleep(2)
            
        except Exception as e:
            print(f"Fall detection error: {e}")
            fall_state.status = "error"
            fall_state.message = f"Error: {str(e)}"
            time.sleep(5)
    
    print("Fall detection monitoring stopped")
    fall_state.status = "idle"
    fall_state.message = "Fall detection stopped"


# ==================== API Routes ====================

@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({
        "message": "NAO Robot REST API Server",
        "version": "2.0.0",
        "nao_ip": NAO_IP,
        "features": ["movement", "speech", "gestures", "sensors", "fall_detection"]
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
    photo, error = nao.capture_photo()
    if photo:
        return jsonify({"success": True, "frame": photo})
    return jsonify({"success": False, "error": error or "Camera not available"}), 501


# ==================== Fall Detection API Routes ====================

@app.route('/api/robot/fall_detection/start', methods=['POST'])
def start_fall_detection():
    global fall_state
    
    if not nao.connected:
        return jsonify({"success": False, "message": "Robot not connected"})
    
    if fall_state.is_active:
        return jsonify({"success": True, "message": "Fall detection already active"})
    
    # Start monitoring thread
    fall_state.stop_event.clear()
    fall_state.is_active = True
    fall_state.monitoring_thread = threading.Thread(target=fall_detection_loop, daemon=True)
    fall_state.monitoring_thread.start()
    
    # Announce activation
    nao.speak("Fall detection activated. I will monitor for anyone who may have fallen.")
    
    return jsonify({
        "success": True,
        "message": "Fall detection started",
        "status": fall_state.status
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
        "person_horizontal_since": fall_state.person_horizontal_since
    })

@app.route('/api/robot/fall_detection/test', methods=['POST'])
def test_fall_detection():
    """Test the fall detection alert system without actual detection"""
    if not nao.connected:
        return jsonify({"success": False, "message": "Robot not connected"})
    
    # Test speech
    nao.speak("Testing fall detection system.")
    time.sleep(1)
    
    # Test asking
    nao.ask_are_you_okay()
    time.sleep(2)
    
    # Test alert sound
    nao.play_alert_sound()
    time.sleep(1)
    
    # Test email
    nao.speak("Testing email alert.")
    email_sent = send_alert_email()
    
    if email_sent:
        nao.speak("Test complete. Email alert sent successfully.")
        return jsonify({
            "success": True,
            "message": f"Test complete! Alert email sent to {RECEIVER_EMAIL}"
        })
    else:
        nao.speak("Test complete but email failed to send. Please check email settings.")
        return jsonify({
            "success": False,
            "message": "Test complete but email failed. Check SMTP settings."
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
    print("=" * 70)
    print(f"\n  NAO Robot IP: {NAO_IP}")
    print(f"  Server running on: http://{local_ip}:{SERVER_PORT}")
    print(f"\n  In the mobile app, enter:")
    print(f"    IP Address: {local_ip}")
    print(f"    Port: {SERVER_PORT}")
    print(f"\n  Fall Detection Email Alerts:")
    print(f"    Sender: {SENDER_EMAIL}")
    print(f"    Receiver: {RECEIVER_EMAIL}")
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
