#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAO Robot REST API - Exercise Module
Natasha_exercise.py

Features: NAO Connection + General Robot Control + Exercise FSM + Voice Commands

Run this on your laptop connected to the same WiFi as your NAO robot.

Requirements:
    pip install paramiko flask flask-cors

Usage:
    python Natasha_exercise.py
"""

import json
import time
import sys
import socket
import threading
import random

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

SQUAT_REPS = 3
ARM_STRETCH_REPS = 3

LED_BLUE   = 0x0000FF
LED_GREEN  = 0x00FF00
LED_YELLOW = 0xFFFF00
LED_RED    = 0xFF0000
LED_WHITE  = 0xFFFFFF

app = Flask(__name__)
CORS(app)

# ==================== STATE ====================
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
            "lookleft": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadYaw", 0.8, 0.15)
time.sleep(1)
motion.setAngles("HeadYaw", 0.0, 0.15)
''',
            "lookright": '''
import time
motion = ALProxy("ALMotion", robot_ip, port)
motion.wakeUp()
motion.setAngles("HeadYaw", -0.8, 0.15)
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
        """Robot demonstrates squat movement - crouching motion"""
        if not self.connected:
            return False
        print(">>> Executing demo_squat (crouch motion)...")
        out, err = self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)

motion.wakeUp()
posture.goToPosture("StandInit", 0.5)
time.sleep(0.5)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.3, 0.3], 0.2)
motion.setAngles(["LElbowRoll", "RElbowRoll"], [-0.5, 0.5], 0.2)
time.sleep(1)

motion.setAngles(["LHipYawPitch"], [-0.2], 0.1)
motion.setAngles(["LHipPitch", "RHipPitch"], [-0.5, -0.5], 0.1)
motion.setAngles(["LKneePitch", "RKneePitch"], [0.8, 0.8], 0.1)
motion.setAngles(["LAnklePitch", "RAnklePitch"], [-0.35, -0.35], 0.1)
time.sleep(2)

posture.goToPosture("StandInit", 0.3)
time.sleep(1)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.2)
print("squat_demo_done")
''', timeout=30)
        print(f"demo_squat result: {out}, err: {err}")
        return True

    def demo_arms_up(self):
        """Robot demonstrates ARM STRETCH - arms up high"""
        if not self.connected:
            return False
        print(">>> Executing demo_arms_up (arm stretch)...")
        out, err = self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)

motion.wakeUp()
posture.goToPosture("StandInit", 0.5)
time.sleep(0.5)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.15)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.8, -0.8], 0.15)
motion.setAngles(["LElbowYaw", "RElbowYaw"], [-1.5, 1.5], 0.15)
motion.setAngles(["LElbowRoll", "RElbowRoll"], [0.0, 0.0], 0.15)
time.sleep(1)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.2, -1.2], 0.12)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.2, -0.2], 0.12)
time.sleep(1.5)

time.sleep(1.5)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.12)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.5, -0.5], 0.12)
time.sleep(1)

posture.goToPosture("StandInit", 0.3)
print("arms_up_demo_done")
''', timeout=35)
        print(f"demo_arms_up result: {out}, err: {err}")
        return True

    def demo_breathing(self):
        """Robot demonstrates breathing exercise"""
        if not self.connected:
            return False
        print(">>> Executing demo_breathing...")
        out, err = self._execute_naoqi('''
import time
motion = ALProxy("ALMotion", robot_ip, port)
posture = ALProxy("ALRobotPosture", robot_ip, port)

motion.wakeUp()
posture.goToPosture("StandInit", 0.5)
time.sleep(0.5)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.2, 1.2], 0.08)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.4, -0.4], 0.08)
motion.setAngles("HeadPitch", -0.1, 0.08)
time.sleep(3)

motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.08)
motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.15, -0.15], 0.08)
motion.setAngles("HeadPitch", 0.1, 0.08)
time.sleep(3)

posture.goToPosture("StandInit", 0.3)
print("breathing_demo_done")
''', timeout=30)
        print(f"demo_breathing result: {out}, err: {err}")
        return True

    def listen_for_response(self, duration=10):
        """Listen for voice response"""
        if not self.connected:
            return False, ""
        out, _ = self._execute_naoqi(f'''
import time
asr = ALProxy("ALSpeechRecognition", robot_ip, port)
memory = ALProxy("ALMemory", robot_ip, port)

vocabulary = ["yes", "no", "help", "okay", "fine", "good", "start", "ready", "stop", "continue", "go", "please", "thank you", "more", "enough", "tired", "done", "next"]
asr.setVocabulary(vocabulary, False)
asr.subscribe("Listener")

start = time.time()
got = False
text = ""

while time.time() - start < {duration}:
    data = memory.getData("WordRecognized")
    if data and len(data) > 1 and data[1] > 0.25:
        word = data[0]
        if word in vocabulary:
            got = True
            text = word
            break
    time.sleep(0.3)

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

nao = NAOController()

# ==================== EXERCISE FSM ====================
PROMPTS = {
    "GREETING": "Hello! I am ready for our exercise session. I will show you how to do each exercise first, then you follow along.",
    "READINESS": "Say yes or start when you are ready to begin.",
    "SQUAT_INTRO": "We will start with squats. Watch me demonstrate first.",
    "SQUAT_DO": "Now your turn! Bend your knees slowly, keep your back straight, then stand up.",
    "ARM_INTRO": "Now let us do arm stretches. Watch me raise my arms high.",
    "ARM_DO": "Your turn! Raise your arms slowly above your head and stretch, then lower them down.",
    "COOLDOWN": "Great job! Let us cool down with some breathing exercises.",
    "BREATHE_IN": "Breathe in slowly through your nose.",
    "BREATHE_OUT": "And breathe out slowly through your mouth.",
    "FEEDBACK": "Excellent work! You completed the exercise session. Well done!",
    "CONTINUE_CHECK": "Would you like to continue to arm stretches? Say yes or no.",
    "PRAISE": ["Very good!", "Excellent!", "Great job!", "Well done!", "Keep it up!", "Perfect!"],
    "GOODBYE": "Thank you for exercising with me. Goodbye!"
}

def wait_for_response(timeout=20):
    """Wait for response from app button OR voice recognition"""
    exercise_state.user_response = None
    exercise_state.response_event.clear()

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
        if exercise_state.response_event.is_set():
            response = exercise_state.user_response or "timeout"
            print(f"Got response: {response}")
            return response
        if exercise_state.stop_event.is_set():
            return "stop"
        time.sleep(0.3)

    if voice_result["got"]:
        return voice_result["text"].lower()

    return "timeout"

def exercise_fsm_loop():
    global exercise_state
    print("Exercise FSM started")
    exercise_state.current_state = "IDLE"

    while not exercise_state.stop_event.is_set():
        state = exercise_state.current_state
        print(f"Exercise State: {state}")

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

            nao.speak(PROMPTS["SQUAT_INTRO"])
            time.sleep(1)

            for rep in range(1, SQUAT_REPS + 1):
                if exercise_state.stop_event.is_set():
                    break

                exercise_state.message = f"Squat {rep}/{SQUAT_REPS} - Watch me!"
                nao.speak(f"Squat number {rep}. Watch me crouch down.")
                nao.demo_squat()
                time.sleep(0.5)

                nao.speak(PROMPTS["SQUAT_DO"])
                exercise_state.message = f"Squat {rep}/{SQUAT_REPS} - Your turn!"
                time.sleep(4)

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
                nao.speak(f"Arm stretch number {rep}. Watch me raise my arms.")
                nao.demo_arms_up()
                time.sleep(0.5)

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

# ==================== API ROUTES ====================
@app.route('/api/', methods=['GET'])
@app.route('/api', methods=['GET'])
def api_root():
    return jsonify({"message": "NAO Exercise API", "module": "Natasha_exercise"})

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
    if exercise_state.is_active:
        exercise_state.stop_event.set()
        exercise_state.response_event.set()
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
    return jsonify({"gestures": [
        {"name": "wave", "description": "Wave hello", "icon": "hand-left"},
        {"name": "bow", "description": "Bow politely", "icon": "body"},
        {"name": "yes", "description": "Nod yes", "icon": "checkmark-circle"},
        {"name": "no", "description": "Shake head no", "icon": "close-circle"},
        {"name": "dance", "description": "Dance moves", "icon": "musical-notes"},
        {"name": "celebrate", "description": "Celebrate", "icon": "happy"},
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

# --- Exercise Routes ---
@app.route('/api/robot/exercise/start', methods=['POST'])
def start_exercise():
    if not nao.connected:
        return jsonify({"success": False, "message": "Not connected"})
    if exercise_state.is_active:
        return jsonify({"success": True, "message": "Running"})

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
    print("  NAO Robot API - Exercise Module (Natasha)")
    print("  Phases: Squats → Arm Stretches → Cooldown")
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
