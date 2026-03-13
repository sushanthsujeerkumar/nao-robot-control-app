#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAO Robot REST API Server
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

# ==================== Flask App ====================
app = Flask(__name__)
CORS(app)

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


# Global controller
nao = NAOController()

# ==================== API Routes ====================

@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({
        "message": "NAO Robot REST API Server",
        "version": "1.0.0",
        "nao_ip": NAO_IP
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
    return jsonify({"error": "Camera not available in this version"}), 501


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
    
    print("=" * 60)
    print("  NAO Robot REST API Server")
    print("=" * 60)
    print(f"\n  NAO Robot IP: {NAO_IP}")
    print(f"  Server running on: http://{local_ip}:{SERVER_PORT}")
    print(f"\n  In the mobile app, enter:")
    print(f"    IP Address: {local_ip}")
    print(f"    Port: {SERVER_PORT}")
    print("\n" + "=" * 60)
    print("  Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")
    
    print("Connecting to NAO automatically...")
    result = nao.connect(NAO_IP)
    if result.get('success'):
        print(f"SUCCESS: {result['message']}")
    else:
        print(f"FAILED: {result['message']}")
        print("\nYou can still start the server - connect via the app later.")
    
    print(f"\nStarting server on http://0.0.0.0:{SERVER_PORT}...")
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)
