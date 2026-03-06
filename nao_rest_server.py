#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
NAO Robot REST API Server
Deploy this to your NAO robot and run it.
The mobile app will connect directly to this server.

Usage:
1. Copy this file to NAO: scp nao_rest_server.py nao@172.18.16.35:~/
2. SSH to NAO: ssh nao@172.18.16.35
3. Run: python nao_rest_server.py

The server will run on port 5000.
"""

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from naoqi import ALProxy
import json
import time
import base64
import threading

# Configuration
NAO_IP = "127.0.0.1"  # localhost since running on NAO
NAO_PORT = 9559
SERVER_PORT = 5000

# Initialize proxies
motion = None
tts = None
posture = None
battery = None
memory = None
behavior = None
video = None
audio = None

def init_proxies():
    global motion, tts, posture, battery, memory, behavior, video, audio
    try:
        motion = ALProxy("ALMotion", NAO_IP, NAO_PORT)
        tts = ALProxy("ALTextToSpeech", NAO_IP, NAO_PORT)
        posture = ALProxy("ALRobotPosture", NAO_IP, NAO_PORT)
        battery = ALProxy("ALBattery", NAO_IP, NAO_PORT)
        memory = ALProxy("ALMemory", NAO_IP, NAO_PORT)
        behavior = ALProxy("ALBehaviorManager", NAO_IP, NAO_PORT)
        audio = ALProxy("ALAudioDevice", NAO_IP, NAO_PORT)
        print("All proxies initialized successfully")
        return True
    except Exception as e:
        print("Error initializing proxies: {}".format(e))
        return False

def init_video():
    global video
    try:
        video = ALProxy("ALVideoDevice", NAO_IP, NAO_PORT)
        return True
    except Exception as e:
        print("Video proxy error: {}".format(e))
        return False

class NAORequestHandler(BaseHTTPRequestHandler):
    
    def _send_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data))
    
    def _read_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            return json.loads(body)
        return {}
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        if path == '/api/' or path == '/api':
            self._send_response({
                "message": "NAO Robot Direct API",
                "version": "1.0.0",
                "robot": "NAO V5"
            })
        
        elif path == '/api/robot/status':
            try:
                batt = battery.getBatteryCharge() if battery else 0
                post = posture.getPostureFamily() if posture else "Unknown"
                temp = 40.0
                try:
                    temp = memory.getData("Device/SubDeviceList/Head/Temperature/Sensor/Value")
                except:
                    pass
                self._send_response({
                    "connected": True,
                    "ip_address": NAO_IP,
                    "battery_level": batt,
                    "temperature": temp,
                    "robot_name": "NAO V5",
                    "posture": post,
                    "connection_mode": "direct"
                })
            except Exception as e:
                self._send_response({"error": str(e)}, 500)
        
        elif path == '/api/robot/sensors':
            try:
                data = {
                    "head_touch_front": bool(memory.getData("Device/SubDeviceList/Head/Touch/Front/Sensor/Value")),
                    "head_touch_middle": bool(memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")),
                    "head_touch_rear": bool(memory.getData("Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")),
                    "left_hand_touch": bool(memory.getData("Device/SubDeviceList/LHand/Touch/Back/Sensor/Value")),
                    "right_hand_touch": bool(memory.getData("Device/SubDeviceList/RHand/Touch/Back/Sensor/Value")),
                    "sonar_left": float(memory.getData("Device/SubDeviceList/US/Left/Sensor/Value") or 0),
                    "sonar_right": float(memory.getData("Device/SubDeviceList/US/Right/Sensor/Value") or 0),
                    "battery_level": int(battery.getBatteryCharge()),
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
                self._send_response(data)
            except Exception as e:
                self._send_response({"error": str(e)}, 500)
        
        elif path == '/api/robot/gestures':
            self._send_response({
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
        
        elif path == '/api/robot/camera/frame':
            try:
                if not video:
                    init_video()
                if video:
                    subscriber_id = video.subscribeCamera("mobile_app", 0, 1, 11, 10)
                    try:
                        nao_image = video.getImageRemote(subscriber_id)
                        if nao_image:
                            width = nao_image[0]
                            height = nao_image[1]
                            array = nao_image[6]
                            # Create PPM and convert to base64
                            header = "P6\n{} {}\n255\n".format(width, height)
                            ppm_data = header + str(bytearray(array))
                            b64 = base64.b64encode(ppm_data)
                            self._send_response({
                                "frame": "data:image/x-portable-pixmap;base64," + b64,
                                "width": width,
                                "height": height
                            })
                        else:
                            self._send_response({"error": "No image"}, 500)
                    finally:
                        video.unsubscribe(subscriber_id)
                else:
                    self._send_response({"error": "Video not available"}, 500)
            except Exception as e:
                self._send_response({"error": str(e)}, 500)
        
        else:
            self._send_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        path = self.path.split('?')[0]
        body = self._read_body()
        
        if path == '/api/robot/connect':
            # Already connected since running on NAO
            try:
                tts.say("Connected")
                self._send_response({
                    "success": True,
                    "message": "Connected to NAO",
                    "status": {
                        "connected": True,
                        "battery_level": battery.getBatteryCharge(),
                        "posture": posture.getPostureFamily(),
                        "robot_name": "NAO V5",
                        "connection_mode": "direct"
                    }
                })
            except Exception as e:
                self._send_response({"success": False, "message": str(e)})
        
        elif path == '/api/robot/disconnect':
            tts.say("Goodbye")
            self._send_response({"success": True, "message": "Disconnected"})
        
        elif path == '/api/robot/move':
            try:
                x = float(body.get('x', 0))
                y = float(body.get('y', 0))
                theta = float(body.get('theta', 0))
                motion.wakeUp()
                motion.moveToward(x, y, theta)
                direction = "stopped"
                if abs(x) > 0.1:
                    direction = "forward" if x > 0 else "backward"
                elif abs(theta) > 0.1:
                    direction = "turning left" if theta > 0 else "turning right"
                self._send_response({"success": True, "message": "Robot " + direction, "direction": direction})
            except Exception as e:
                self._send_response({"success": False, "message": str(e)})
        
        elif path == '/api/robot/stop':
            try:
                motion.stopMove()
                self._send_response({"success": True, "message": "Robot stopped"})
            except Exception as e:
                self._send_response({"success": False, "message": str(e)})
        
        elif path == '/api/robot/speak':
            try:
                text = body.get('text', '')
                volume = float(body.get('volume', 1.0))
                audio.setOutputVolume(int(volume * 100))
                tts.say(str(text))
                self._send_response({"success": True, "message": "Speaking: " + text})
            except Exception as e:
                self._send_response({"success": False, "message": str(e)})
        
        elif path == '/api/robot/gesture':
            try:
                gesture = body.get('gesture_name', '').lower()
                speed = float(body.get('speed', 1.0))
                
                if gesture == 'sit':
                    posture.goToPosture("Sit", speed)
                elif gesture == 'stand':
                    posture.goToPosture("Stand", speed)
                elif gesture == 'wave':
                    motion.wakeUp()
                    # Wave animation
                    names = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"]
                    angles = [-0.5, -0.3, 1.0, 0.5]
                    motion.setAngles(names, angles, 0.2)
                    time.sleep(0.5)
                    for i in range(3):
                        motion.setAngles("RWristYaw", 1.0, 0.3)
                        time.sleep(0.3)
                        motion.setAngles("RWristYaw", -1.0, 0.3)
                        time.sleep(0.3)
                    motion.setAngles(names + ["RWristYaw"], [1.5, 0.1, 1.2, 0.5, 0.0], 0.2)
                elif gesture == 'bow':
                    motion.wakeUp()
                    motion.setAngles("HeadPitch", 0.5, 0.2)
                    time.sleep(1)
                    motion.setAngles("HeadPitch", 0.0, 0.2)
                elif gesture == 'yes':
                    motion.wakeUp()
                    for i in range(3):
                        motion.setAngles("HeadPitch", 0.3, 0.3)
                        time.sleep(0.3)
                        motion.setAngles("HeadPitch", -0.1, 0.3)
                        time.sleep(0.3)
                    motion.setAngles("HeadPitch", 0.0, 0.2)
                elif gesture == 'no':
                    motion.wakeUp()
                    for i in range(3):
                        motion.setAngles("HeadYaw", 0.5, 0.3)
                        time.sleep(0.3)
                        motion.setAngles("HeadYaw", -0.5, 0.3)
                        time.sleep(0.3)
                    motion.setAngles("HeadYaw", 0.0, 0.2)
                elif gesture == 'dance':
                    tts.say("Dancing!")
                    motion.wakeUp()
                    for i in range(4):
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.3)
                        time.sleep(0.4)
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.3)
                        time.sleep(0.4)
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.5, 1.5], 0.2)
                elif gesture == 'celebrate':
                    motion.wakeUp()
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.0, -1.0], 0.3)
                    time.sleep(0.5)
                    for i in range(3):
                        motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.5, -0.5], 0.3)
                        time.sleep(0.3)
                        motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [-0.5, 0.5], 0.3)
                        time.sleep(0.3)
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch", "LShoulderRoll", "RShoulderRoll"], 
                                     [1.5, 1.5, 0.1, -0.1], 0.2)
                elif gesture == 'handshake':
                    motion.wakeUp()
                    motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"], 
                                     [0.3, -0.3, 0.5, 0.2, 0.0], 0.2)
                    motion.openHand("RHand")
                elif gesture == 'think':
                    motion.wakeUp()
                    motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll"], 
                                     [0.5, -0.2, 0.0, 1.5], 0.2)
                    motion.setAngles("HeadPitch", 0.2, 0.2)
                    time.sleep(2)
                    motion.setAngles(["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "HeadPitch"], 
                                     [1.5, 0.1, 1.2, 0.5, 0.0], 0.2)
                else:
                    self._send_response({"success": False, "message": "Unknown gesture"})
                    return
                
                self._send_response({"success": True, "message": "Executing " + gesture, "gesture": gesture})
            except Exception as e:
                self._send_response({"success": False, "message": str(e)})
        
        else:
            self._send_response({"error": "Not found"}, 404)
    
    def log_message(self, format, *args):
        print("[{}] {}".format(time.strftime("%H:%M:%S"), format % args))


def main():
    print("=" * 50)
    print("NAO Robot REST API Server")
    print("=" * 50)
    
    if not init_proxies():
        print("Failed to initialize. Is NAOqi running?")
        return
    
    # Announce startup
    tts.say("REST API server starting")
    
    server = HTTPServer(('0.0.0.0', SERVER_PORT), NAORequestHandler)
    print("Server running on port {}".format(SERVER_PORT))
    print("Connect your mobile app to: http://<NAO_IP>:{}".format(SERVER_PORT))
    print("Press Ctrl+C to stop")
    
    tts.say("Server ready")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        tts.say("Server stopping")
        server.shutdown()


if __name__ == '__main__':
    main()
