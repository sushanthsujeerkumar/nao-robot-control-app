#!/usr/bin/env python3
"""
NAO Robot REST API Server with Fall Detection - CAMERA FIXED
Uses NAO's camera for fall detection with laptop-based analysis.
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
    print("OpenCV not found - install with: pip install opencv-python numpy")

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

app = Flask(__name__)
CORS(app)

class FallDetectionState:
    def __init__(self):
        self.is_active = False
        self.status = "idle"
        self.message = "Fall detection not active"
        self.last_alert = None
        self.person_horizontal_since = None
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        self.last_frame = None

fall_state = FallDetectionState()

class LaptopDetector:
    def __init__(self):
        if OPENCV_AVAILABLE:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    def ppm_to_cv2(self, ppm_base64):
        try:
            raw = base64.b64decode(ppm_base64)
            # Parse PPM: P6\nWIDTH HEIGHT\n255\nDATA
            parts = raw.split(b'\n', 3)
            if len(parts) >= 4:
                dims = parts[1].decode().split()
                width, height = int(dims[0]), int(dims[1])
                pixel_data = parts[3]
                if len(pixel_data) >= width * height * 3:
                    img = np.frombuffer(pixel_data[:width*height*3], dtype=np.uint8)
                    img = img.reshape((height, width, 3))
                    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"PPM parse error: {e}")
        return None
    
    def detect_horizontal_person(self, image_base64):
        if not OPENCV_AVAILABLE:
            return False, 0.0, "OpenCV not available"
        try:
            img = self.ppm_to_cv2(image_base64)
            if img is None:
                return False, 0.0, "Failed to decode image"
            
            fall_state.last_frame = img
            small = cv2.resize(img, None, fx=0.5, fy=0.5)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            
            is_horizontal = False
            confidence = 0.0
            details = []
            
            # Person detection
            persons, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(4, 4), scale=1.05)
            for i, (x, y, w, h) in enumerate(persons):
                aspect = w / h if h > 0 else 0
                details.append(f"Person: aspect={aspect:.2f}")
                if aspect > 1.2:
                    is_horizontal = True
                    confidence = max(confidence, min(0.9, aspect / 2))
                if (y + h/2) / small.shape[0] > 0.6:
                    confidence = max(confidence, 0.7)
            
            # Face detection
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(20, 20))
            for (x, y, w, h) in faces:
                face_y = (y + h/2) / small.shape[0]
                details.append(f"Face at y={face_y:.2f}")
                if face_y > 0.65:
                    confidence = max(confidence, 0.6)
            
            if confidence > 0.5:
                is_horizontal = True
            
            return is_horizontal, confidence, " | ".join(details) if details else "No detection"
        except Exception as e:
            return False, 0.0, f"Error: {e}"

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
            out, err = self._execute_naoqi('''
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.say("Connected")
print(json.dumps({"success": True}))
''')
            if out and "success" in out:
                self.connected = True
                self.start_time = time.time()
                print(f"Connected to NAO at {ip}")
                return {"success": True, "message": f"Connected to NAO at {ip}"}
            self.ssh.close()
            self.ssh = None
            return {"success": False, "message": f"NAOqi failed: {err or out}"}
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
            return {"success": False, "message": "Not connected"}
        self._execute_naoqi(f'''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.moveToward({x}, {y}, {theta})
''')
        return {"success": True, "message": "Moving"}
    
    def stop(self):
        if not self.connected:
            return {"success": False}
        self._execute_naoqi('ALProxy("ALMotion", robot_ip, port).stopMove()')
        return {"success": True, "message": "Stopped"}
    
    def speak(self, text):
        if not self.connected:
            return {"success": False, "message": "Not connected"}
        text = text.replace('"', '\\"').replace("'", "\\'")
        self._execute_naoqi(f'ALProxy("ALTextToSpeech", robot_ip, port).say("{text}")', timeout=60)
        return {"success": True, "message": f"Speaking: {text}"}
    
    def gesture(self, name, speed=1.0):
        if not self.connected:
            return {"success": False}
        gestures = {
            "stand": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("Stand", {speed})',
            "sit": f'ALProxy("ALRobotPosture", robot_ip, port).goToPosture("Sit", {speed})',
            "wave": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles(["RShoulderPitch", "RShoulderRoll"], [-0.5, -0.3], 0.2)
time.sleep(0.5)
for i in range(3):
    motion.setAngles("RWristYaw", 1.0, 0.3)
    time.sleep(0.3)
    motion.setAngles("RWristYaw", -1.0, 0.3)
    time.sleep(0.3)
motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RWristYaw"], [1.5, 0.1, 0.0], 0.2)
'''
        }
        code = gestures.get(name.lower())
        if code:
            self._execute_naoqi(code, timeout=30)
        return {"success": True, "message": f"Gesture: {name}"}
    
    def capture_camera_frame(self):
        """Capture image from NAO camera - FIXED VERSION"""
        if not self.connected:
            return None, "Not connected"
        
        out, err = self._execute_naoqi('''
import base64
import time

video = ALProxy("ALVideoDevice", robot_ip, port)

# Resolution: 0=QQVGA(160x120), 1=QVGA(320x240), 2=VGA(640x480)
# ColorSpace: 11=RGB
# Camera: 0=Top, 1=Bottom
resolution = 1
colorSpace = 11
fps = 10
cameraId = 0

subscriberName = "nao_cam_" + str(int(time.time() * 1000) % 100000)

try:
    clientId = video.subscribeCamera(subscriberName, cameraId, resolution, colorSpace, fps)
    time.sleep(0.3)
    naoImage = video.getImageRemote(clientId)
    video.unsubscribe(clientId)
    
    if naoImage is not None:
        imageWidth = naoImage[0]
        imageHeight = naoImage[1]
        imageData = naoImage[6]
        
        ppmHeader = "P6\\n" + str(imageWidth) + " " + str(imageHeight) + "\\n255\\n"
        ppmImage = ppmHeader + imageData
        encoded = base64.b64encode(ppmImage).decode('utf-8')
        
        print(json.dumps({"success": True, "image": encoded, "width": imageWidth, "height": imageHeight}))
    else:
        print(json.dumps({"success": False, "error": "No image from camera"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
''', timeout=20)
        
        try:
            if out:
                for line in out.split('\n'):
                    line = line.strip()
                    if line.startswith('{'):
                        data = json.loads(line)
                        if data.get("success"):
                            print(f"Camera: captured {data.get('width')}x{data.get('height')}")
                            return data.get("image"), None
                        return None, data.get("error", "Camera failed")
        except Exception as e:
            print(f"Parse error: {e}")
        
        return None, err or "Camera capture failed"
    
    def ask_are_you_okay(self):
        return self.speak("Are you okay? Please respond if you can hear me.")
    
    def listen_for_response(self, duration=10):
        if not self.connected:
            return False, ""
        out, _ = self._execute_naoqi(f'''
import time
asr = ALProxy("ALSpeechRecognition", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)
vocabulary = ["yes", "no", "help", "okay", "fine", "good", "here", "hello"]
asr.setVocabulary(vocabulary, False)
asr.subscribe("FallListener")
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
asr.unsubscribe("FallListener")
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
            return {"success": False}
        self._execute_naoqi('''
import time
tts = ALProxy("ALTextToSpeech", robot_ip, port)
tts.setVolume(1.0)
tts.say("Alert! Emergency! Someone may have fallen!")
for i in range(3):
    tts.say("Beep")
    time.sleep(0.3)
''', timeout=30)
        return {"success": True}
    
    def move_closer(self):
        if not self.connected:
            return {"success": False}
        self._execute_naoqi('''
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.moveTo(0.3, 0, 0)
motion.setAngles("HeadPitch", 0.4, 0.2)
''', timeout=20)
        return {"success": True}

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
    print("="*50)
    print("Fall detection started - Camera + OpenCV")
    print("="*50)
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
            
            print("Capturing camera frame...")
            image, error = nao.capture_camera_frame()
            
            if not image:
                print(f"Camera error: {error}")
                fall_state.message = f"Camera: {error}"
                time.sleep(DETECTION_CHECK_INTERVAL)
                continue
            
            print("Analyzing on laptop...")
            is_horiz, conf, details = laptop_detector.detect_horizontal_person(image)
            print(f"Result: horizontal={is_horiz}, conf={conf:.2f}, {details}")
            
            if is_horiz and conf > 0.5:
                if horizontal_start is None:
                    horizontal_start = time.time()
                    fall_state.status = "person_detected"
                    fall_state.message = f"Person horizontal detected! ({conf:.0%})"
                    print(">>> HORIZONTAL DETECTED - timer started")
                
                elapsed = time.time() - horizontal_start
                fall_state.message = f"Horizontal for {elapsed:.0f}s (threshold: {HORIZONTAL_DETECTION_SECONDS}s)"
                
                if elapsed >= HORIZONTAL_DETECTION_SECONDS:
                    print(">>> ALERT SEQUENCE")
                    fall_state.status = "checking"
                    
                    nao.move_closer()
                    time.sleep(1)
                    nao.ask_are_you_okay()
                    fall_state.message = "Asked 'Are you okay?' - listening..."
                    
                    got_resp, resp_text = nao.listen_for_response(VERBAL_RESPONSE_WAIT_SECONDS)
                    
                    if got_resp:
                        print(f">>> Response: {resp_text}")
                        fall_state.status = "monitoring"
                        fall_state.message = f"Person responded: {resp_text}"
                        nao.speak("Good, you're alright.")
                        horizontal_start = None
                    else:
                        print(">>> NO RESPONSE - ALERTING!")
                        nao.play_alert_sound()
                        time.sleep(FINAL_ALERT_WAIT_SECONDS)
                        
                        if send_alert_email(fall_state.last_frame):
                            fall_state.status = "alert_sent"
                            fall_state.message = f"Alert sent to {RECEIVER_EMAIL}"
                            nao.speak("Alert email sent.")
                        
                        horizontal_start = None
                        time.sleep(30)
                        fall_state.status = "monitoring"
            else:
                if horizontal_start:
                    print(">>> Person OK - reset")
                    horizontal_start = None
                fall_state.status = "monitoring"
                fall_state.message = f"Monitoring... ({details[:40]})"
            
            time.sleep(DETECTION_CHECK_INTERVAL)
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)
    
    fall_state.status = "idle"
    fall_state.message = "Stopped"

# ==================== API ROUTES ====================
@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({"message": "NAO Robot API v2.3", "opencv": OPENCV_AVAILABLE})

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
    return jsonify({"gestures": [{"name": "wave"}, {"name": "sit"}, {"name": "stand"}]})

@app.route('/api/robot/fall_detection/start', methods=['POST'])
def start_fall_detection():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    if not OPENCV_AVAILABLE:
        return jsonify({"success": False, "message": "OpenCV not installed"})
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
    
    # Test camera
    nao.speak("Testing camera.")
    img, err = nao.capture_camera_frame()
    results.append(f"Camera: {'OK' if img else 'FAILED - ' + str(err)}")
    
    # Test OpenCV
    if OPENCV_AVAILABLE and img:
        h, c, d = laptop_detector.detect_horizontal_person(img)
        results.append(f"OpenCV: OK (h={h}, c={c:.2f})")
    
    # Test speech
    nao.speak("Are you okay?")
    results.append("Speech: OK")
    
    # Test alert
    nao.play_alert_sound()
    results.append("Alert: OK")
    
    # Test email
    if send_alert_email(fall_state.last_frame):
        results.append(f"Email: Sent to {RECEIVER_EMAIL}")
    else:
        results.append("Email: FAILED")
    
    nao.speak("Test complete.")
    return jsonify({"success": True, "results": results})

@app.route('/api/robot/camera/frame', methods=['GET'])
def camera_frame():
    img, err = nao.capture_camera_frame()
    if img:
        return jsonify({"success": True, "frame": img})
    return jsonify({"success": False, "error": err})

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
    print("  NAO Robot API - Camera Fall Detection v2.3")
    print("="*60)
    print(f"  NAO: {NAO_IP}")
    print(f"  Server: http://{local_ip}:{SERVER_PORT}")
    print(f"  OpenCV: {'YES' if OPENCV_AVAILABLE else 'NO'}")
    print(f"  Email: {RECEIVER_EMAIL}")
    print("="*60)
    
    result = nao.connect(NAO_IP)
    print(f"NAO: {result['message']}")
    
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)
