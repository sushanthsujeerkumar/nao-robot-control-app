#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAO Robot REST API - Storytelling Module
Arooj_storytelling.py

Features: NAO Connection + General Robot Control + Storytelling

Run this on your laptop connected to the same WiFi as your NAO robot.

Requirements:
    pip install paramiko flask flask-cors

Usage:
    python Arooj_storytelling.py
"""

import json
import time
import sys
import socket
import threading
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
    print("Run: pip install paramiko flask flask-cors")
    sys.exit(1)

# ==================== CONFIG ====================
NAO_IP = "172.18.16.49"
SSH_USERNAME = "nao"
SSH_PASSWORD = "nao"
SERVER_PORT = 5000

app = Flask(__name__)
CORS(app)

# ==================== STATE ====================
class StorytellingState:
    def __init__(self):
        self.is_active = False
        self.status = "idle"
        self.message = "Select a story"
        self.current_story = ""
        self.is_playing = False
        self.stop_event = threading.Event()
        self.story_thread = None

storytelling_state = StorytellingState()

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
memory = ALProxy("ALMemory", robot_ip, port)
temps = []
temp_sensors = [
    "Device/SubDeviceList/HeadPitch/Temperature/Sensor/Value",
    "Device/SubDeviceList/LShoulderPitch/Temperature/Sensor/Value",
    "Device/SubDeviceList/RShoulderPitch/Temperature/Sensor/Value"
]
for sensor in temp_sensors:
    try:
        t = memory.getData(sensor)
        if t and t > 0:
            temps.append(float(t))
    except:
        pass
avg_temp = sum(temps) / len(temps) if temps else 35.0
print(json.dumps({
    "battery_level": battery.getBatteryCharge(),
    "posture": posture.getPostureFamily(),
    "avg_temperature": round(avg_temp, 1)
}))
''')
        try:
            data = json.loads(out) if out else {}
            return {
                "connected": True,
                "ip_address": self.nao_ip,
                "battery_level": data.get("battery_level", 0),
                "temperature": data.get("avg_temperature", 35),
                "robot_name": "NAO V5",
                "posture": data.get("posture", "Unknown"),
                "uptime": int(time.time() - self.start_time) if self.start_time else 0
            }
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

nao = NAOController()

# ==================== STORIES ====================
STORIES = {
    1: {
        "name": "The Bear and the Bee",
        "parts": [
            {"text": "Once upon a time, there was a hungry bear named Bruno.", "gesture": "wave"},
            {"text": "Bruno loved honey more than anything in the world.", "gesture": "happy"},
            {"text": "One day, he found a beehive in a tall tree.", "gesture": "lookup"},
            {"text": "He tried to reach the honey, but the bees said, Buzz off!", "gesture": "angry"},
            {"text": "Bruno was sad, but then he had an idea.", "gesture": "think"},
            {"text": "He brought flowers to the bees as a gift.", "gesture": "bow"},
            {"text": "The bees were so happy, they shared their honey with Bruno.", "gesture": "celebrate"},
            {"text": "And they all became the best of friends. The end!", "gesture": "clap"}
        ]
    },
    2: {
        "name": "The Lion and the Mouse",
        "parts": [
            {"text": "A mighty lion was sleeping in the jungle.", "gesture": "sad"},
            {"text": "A tiny mouse accidentally ran over his paw.", "gesture": "surprised"},
            {"text": "The lion caught the mouse and roared, How dare you!", "gesture": "angry"},
            {"text": "Please let me go, said the mouse. I might help you someday.", "gesture": "bow"},
            {"text": "The lion laughed but let the mouse go.", "gesture": "happy"},
            {"text": "Later, the lion got caught in a hunter's net.", "gesture": "sad"},
            {"text": "The little mouse came and chewed through the ropes.", "gesture": "clap"},
            {"text": "Even the smallest friend can be the greatest help. The end!", "gesture": "celebrate"}
        ]
    },
    3: {
        "name": "The Tortoise and the Hare",
        "parts": [
            {"text": "A hare was always bragging about how fast he was.", "gesture": "happy"},
            {"text": "One day, a tortoise challenged him to a race.", "gesture": "wave"},
            {"text": "The hare laughed. You, race me? Okay!", "gesture": "surprised"},
            {"text": "The race began, and the hare zoomed ahead.", "gesture": "dance"},
            {"text": "The hare was so confident, he took a nap.", "gesture": "sad"},
            {"text": "Meanwhile, the tortoise kept going slowly but surely.", "gesture": "stand"},
            {"text": "The tortoise crossed the finish line while the hare slept.", "gesture": "celebrate"},
            {"text": "Slow and steady wins the race. The end!", "gesture": "clap"}
        ]
    },
    4: {
        "name": "The Fox and the Grapes",
        "parts": [
            {"text": "A hungry fox was walking through a vineyard.", "gesture": "stand"},
            {"text": "He saw beautiful, juicy grapes hanging high above.", "gesture": "lookup"},
            {"text": "He jumped as high as he could, but could not reach them.", "gesture": "stretch"},
            {"text": "He tried again and again, but still could not get them.", "gesture": "angry"},
            {"text": "Finally, he gave up and walked away.", "gesture": "sad"},
            {"text": "Those grapes are probably sour anyway, he said.", "gesture": "no"},
            {"text": "Sometimes we pretend we do not want what we cannot have. The end!", "gesture": "think"}
        ]
    },
    5: {
        "name": "The Ant and the Grasshopper",
        "parts": [
            {"text": "In summer, an ant worked hard carrying food.", "gesture": "stand"},
            {"text": "A grasshopper played music and danced all day.", "gesture": "dance"},
            {"text": "Why work so hard? Come play! said the grasshopper.", "gesture": "happy"},
            {"text": "The ant said, I am saving food for winter.", "gesture": "think"},
            {"text": "Winter came, and snow covered everything.", "gesture": "sad"},
            {"text": "The grasshopper had no food and was very hungry.", "gesture": "sad"},
            {"text": "The kind ant shared his food with the grasshopper.", "gesture": "handshake"},
            {"text": "It is best to prepare for the future. The end!", "gesture": "celebrate"}
        ]
    }
}

# ==================== STORYTELLING LOOP ====================
def storytelling_loop(story_id):
    global storytelling_state

    story = STORIES.get(story_id)
    if not story:
        storytelling_state.status = "error"
        storytelling_state.message = "Story not found"
        return

    print(f"Starting story: {story['name']}")
    storytelling_state.status = "playing"
    storytelling_state.message = f"Playing: {story['name']}"
    storytelling_state.current_story = story['name']
    storytelling_state.is_playing = True

    nao.wake_up()
    nao.speak(f"Let me tell you the story of {story['name']}")
    time.sleep(1)

    for part in story['parts']:
        if storytelling_state.stop_event.is_set():
            break
        nao.speak(part['text'])
        nao.gesture(part.get("gesture", "stand"))
        time.sleep(1)

    if not storytelling_state.stop_event.is_set():
        nao.speak("I hope you enjoyed the story!")
        nao.gesture("bow")

    storytelling_state.is_playing = False
    storytelling_state.is_active = False
    storytelling_state.status = "idle"
    storytelling_state.message = "Select a story"
    storytelling_state.current_story = ""
    print("Story ended")

# ==================== API ROUTES ====================
@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({"message": "NAO Storytelling API", "module": "Arooj_storytelling"})

# --- General Robot Routes ---
@app.route('/api/robot/connect', methods=['POST'])
def connect():
    data = request.get_json() or {}
    result = nao.connect(data.get('ip_address', NAO_IP))
    if result.get('success'):
        return jsonify({"success": True, "message": result['message'], "status": nao.get_status()})
    return jsonify(result)

@app.route('/api/robot/disconnect', methods=['POST'])
def disconnect():
    if storytelling_state.is_active:
        storytelling_state.stop_event.set()
        storytelling_state.is_active = False
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
        {"name": "stretch", "description": "Stretch arms", "icon": "fitness"},
        {"name": "stand", "description": "Stand up", "icon": "arrow-up"},
        {"name": "sit", "description": "Sit down", "icon": "arrow-down"},
        {"name": "crouch", "description": "Crouch down", "icon": "chevron-down"},
        {"name": "lookleft", "description": "Look left", "icon": "arrow-back"},
        {"name": "lookright", "description": "Look right", "icon": "arrow-forward"},
        {"name": "lookup", "description": "Look up", "icon": "caret-up"},
        {"name": "lookdown", "description": "Look down", "icon": "caret-down"},
    ]})

# --- Storytelling Routes ---
@app.route('/api/storytelling/play', methods=['POST'])
def play_story():
    data = request.get_json() or {}
    story_id = data.get('story_id', 1)

    if not nao.connected:
        return jsonify({"success": False, "message": "Robot not connected"})
    if storytelling_state.is_playing:
        return jsonify({"success": False, "message": "A story is already playing"})
    if story_id not in STORIES:
        return jsonify({"success": False, "message": "Invalid story ID"})

    storytelling_state.stop_event.clear()
    storytelling_state.is_active = True
    storytelling_state.story_thread = threading.Thread(target=storytelling_loop, args=(story_id,), daemon=True)
    storytelling_state.story_thread.start()

    return jsonify({
        "success": True,
        "message": f"Playing story: {STORIES[story_id]['name']}",
        "story_name": STORIES[story_id]['name']
    })

@app.route('/api/storytelling/stop', methods=['POST'])
def stop_story():
    if storytelling_state.is_playing:
        storytelling_state.stop_event.set()
        nao.speak("Stopping the story.")

    storytelling_state.is_playing = False
    storytelling_state.is_active = False
    storytelling_state.status = "idle"
    storytelling_state.message = "Story stopped"

    return jsonify({"success": True, "message": "Story stopped"})

@app.route('/api/storytelling/status', methods=['GET'])
def story_status():
    return jsonify({
        "is_playing": storytelling_state.is_playing,
        "status": storytelling_state.status,
        "message": storytelling_state.message,
        "current_story": storytelling_state.current_story
    })

@app.route('/api/storytelling/list', methods=['GET'])
def list_stories():
    stories = []
    for sid, story in STORIES.items():
        stories.append({
            "id": sid,
            "name": story['name'],
            "parts_count": len(story['parts'])
        })
    return jsonify({"stories": stories})

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
    print("=" * 60)
    print("  NAO Robot API - Storytelling Module (Arooj)")
    print("=" * 60)
    print(f"  NAO Robot IP : {NAO_IP}")
    print(f"  Server       : http://{local_ip}:{SERVER_PORT}")
    print("=" * 60)
    print(f"\n  In the app, enter your laptop IP: {local_ip}")
    print("=" * 60)

    result = nao.connect(NAO_IP)
    print(f"NAO: {result['message']}")

    print(f"\nStarting server on http://0.0.0.0:{SERVER_PORT}...")
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)
