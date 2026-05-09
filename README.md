# 🤖 NAO Robot Companion System

A comprehensive multi-functional application and server system that transforms the NAO V5 humanoid robot into a versatile companion for elderly care, rehabilitation, smart home automation, and interactive entertainment.

[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-24.8%25-blue?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React Native](https://img.shields.io/badge/React%20Native-Expo-black?logo=react&logoColor=61dafb)](https://expo.dev/)
[![Flask](https://img.shields.io/badge/Flask-Backend-blue?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Team Contributions](#team-contributions)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Hardware Requirements](#hardware-requirements)
- [Installation & Setup](#installation--setup)
- [API Documentation](#api-documentation)
- [Mobile App Tabs](#mobile-app-tabs)
- [Demo Scenarios](#demo-scenarios)
- [Project Statistics](#project-statistics)
- [Future Enhancements](#future-enhancements)

---

## 🎯 Project Overview

**NAO Robot Companion System** is an intelligent robotic application designed to:

- 👴 **Monitor elderly individuals** for falls with automated emergency response
- 💪 **Guide physical exercise** sessions with real-time robot demonstrations
- 🏠 **Control smart home devices** via voice commands and mobile interface
- 📖 **Entertain users** with interactive storytelling featuring gestures and dialogue

### Target Use Cases
- Elderly care and monitoring
- Physical rehabilitation centers
- Smart home automation
- Educational entertainment

---

## 🎯 Features

### 1. 🚨 Fall Detection System
**Developed by: Sushanth**

Intelligent camera-based fall detection with automated emergency response.

**How It Works:**
- Continuous video monitoring using NAO's camera
- OpenCV HOG (Histogram of Oriented Gradients) for person detection
- Body orientation analysis to detect horizontal (fallen) position
- Automated response protocol:
  1. Robot moves closer and asks "Are you okay?"
  2. Listens for verbal response (10 seconds)
  3. Plays alert sound if no response
  4. Sends emergency email with photo to caregiver

**Configurable Parameters:**
```python
HORIZONTAL_DETECTION_SECONDS = 12
VERBAL_RESPONSE_WAIT_SECONDS = 10
FINAL_ALERT_WAIT_SECONDS = 10
DETECTION_CHECK_INTERVAL = 3
```

**Technical Stack:**
- OpenCV HOG Descriptor & Haar Cascade
- Gmail SMTP for alerts
- NAO ALSpeechRecognition
- Multi-threaded monitoring

---

### 2. 💡 ESP32 Smart Home Automation
**Developed by: Deshwin**

Voice-controlled smart home light system integration with the NAO robot.

**Features:**
- WiFi-enabled ESP32 microcontroller
- LED control via GPIO 4
- Three control methods:
  - **App buttons** - Direct Turn ON/OFF
  - **Robot voice** - "I am turning on the light"
  - **Voice commands** - "Turn on the light" recognized by NAO

**Hardware Setup:**
```
Device           IP Address    Port    Purpose
─────────────────────────────────────────────────
ESP32            172.18.16.43  80      Light control
LED              GPIO 4        -       Output device
Network          ll_cst_labs   -       WiFi connection
```

**API Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Web interface |
| `/on` | GET | Turn light ON |
| `/off` | GET | Turn light OFF |
| `/status` | GET | JSON status |
| `/toggle` | GET | Toggle state |

**Voice Commands:**
- "turn on the light" / "turn off the light"
- "turn on" / "turn off"
- "light on" / "light off"
- "on" / "off"

---

### 3. 🏋️ Exercise Session Guide
**Developed by: Natasha**

Guided physical exercise routines with robot demonstrations for rehabilitation.

**Exercise Program:**
1. **Squat Exercise** (3 repetitions)
   - Robot demonstrates proper form
   - User follows along
   - Robot provides encouragement

2. **Arm Stretch** (3 repetitions)
   - Robot raises arms high
   - User follows along

3. **Cooldown** 
   - Guided breathing exercises
   - "Breathe in... Breathe out..."

**State Machine:**
```
IDLE → GREETING → READINESS → SQUAT → CONTINUE → ARM → COOLDOWN → FEEDBACK → END
```

**Robot Demonstrations:**
- `demo_squat()` - Bending, arm balance, crouching
- `demo_arms_up()` - Raising arms high above head
- `demo_breathing()` - Expanding/contracting arms

**LED Color Indicators:**
| Color | State |
|-------|-------|
| 🔵 Blue | Greeting/Cooldown |
| 🟡 Yellow | Waiting for response |
| 🟢 Green | Exercise in progress |
| 🔴 Red | Stopped/Error |
| ⚪ White | Session ended |

---

### 4. 📚 Interactive Storytelling
**Developed by: Arooj**

Engaging stories with robot narration and expressive gestures.

**Available Stories:**

| Story | Parts | Theme |
|-------|-------|-------|
| 🐻 The Bear and the Bee | 8 | Kindness and sharing |
| 🦁 The Lion and the Mouse | 8 | Small friends can help greatly |
| 🐢 The Tortoise and the Hare | 8 | Slow and steady wins the race |
| 🦊 The Fox and the Grapes | 7 | Sour grapes mentality |
| 🐜 The Ant and the Grasshopper | 8 | Prepare for the future |

**Story Presentation:**
1. Robot announces story title
2. For each story part:
   - Robot narrates the text
   - Performs corresponding gesture
3. Robot ends with "I hope you enjoyed the story!" and bows

**Gestures Used:**
`wave` `happy` `sad` `angry` `surprised` `think` `bow` `celebrate` `clap` `lookup` `stand` `stretch` `dance` `handshake`

---

## 👥 Team Contributions

| Team Member | Feature | Role |
|-------------|---------|------|
| **Sushanth** | 🚨 Fall Detection | Computer vision & emergency response |
| **Deshwin** | 💡 ESP32 Automation | IoT & smart home integration |
| **Natasha** | 🏋️ Exercise Session | Rehabilitation & exercise guidance |
| **Arooj** | 📚 Storytelling | Interactive narrative & entertainment |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    📱 MOBILE APP (React Native + Expo)          │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐ │
│  │ Connect │ Control │ Actions │ Speech  │ Sensors │Functions│ │
│  └────┬────┴────┬────┴────┬────┴────┬────┴────┬────┴────┬────┘ │
└───────┼─────────┼─────────┼─────────┼─────────┼─────────┼───────┘
        │ HTTP API (Axios)  │
        ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│           💻 LAPTOP BRIDGE SERVER (Python Flask)                │
│                      REST API (Port 5000)                       │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │   OpenCV     │   Exercise   │  Automation  │ Storytelling │ │
│  │   Thread     │     FSM      │   Control    │    Thread    │ │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘ │
│         │              │              │              │          │
│         │   ┌──────────┘              │              │          │
└─────────┼───┼──────────────────────┬──┼──────────────┼──────────┘
          │   │                      │  │              │
          ▼   ▼                      │  ▼              ▼
    ┌──────────────┐                 │  ┌────────────────────┐
    │  🤖 NAO V5   │                 │  │    🔌 ESP32        │
    │  Robot       │                 │  │   Microcontroller  │
    │ 172.18.16.38 │                 │  │   172.18.16.43     │
    │              │                 │  │                    │
    │ • SSH (22)   │                 │  │ • LED Control      │
    │ • NAOqi (9559)                 │  │ • GPIO 4 Output    │
    │ • Camera     │                 │  │ • Web Server (80)  │
    │ • Speech     │                 │  │                    │
    │ • Motion     │                 │  │                    │
    └──────┬───────┘                 │  └────────┬───────────┘
           │                         │           │
           │ SMTP                    │           │
           └─────────────────────┬───┴───────────┘
                                 ▼
                        ┌─────────────────┐
                        │   📧 Gmail SMTP │
                        │   (Email Alerts)│
                        └─────────────────┘
```

---

## 💻 Technology Stack

### Frontend (Mobile App)
- **Framework:** React Native with Expo
- **Routing:** Expo Router (file-based)
- **State Management:** Zustand
- **HTTP Client:** Axios
- **UI Components:** Ionicons + Custom components
- **Platform:** iOS & Android

### Backend (Laptop Server)
- **Language:** Python 3.x
- **Web Framework:** Flask + Flask-CORS
- **SSH Library:** Paramiko
- **Computer Vision:** OpenCV
- **Email Service:** smtplib (Gmail)
- **Threading:** Python threading module

### Hardware
- **Robot:** NAO V5 Humanoid Robot
- **Microcontroller:** ESP32 Development Board
- **LED:** Standard LED (GPIO 4)
- **Network:** WiFi (ll_cst_labs)

### NAO Robot APIs
- `ALMotion` - Movement control
- `ALRobotPosture` - Posture management
- `ALTextToSpeech` - Speech synthesis
- `ALSpeechRecognition` - Voice recognition
- `ALVideoDevice` - Camera access
- `ALLeds` - LED control
- `ALBattery` - Battery monitoring
- `ALMemory` - Sensor data access

---

## 🔧 Hardware Requirements

### Network Configuration
```
Device          IP Address      Port          Purpose
─────────────────────────────────────────────────────────
NAO Robot       172.18.16.38    22, 9559      Main robot
Laptop Server   172.18.16.41    5000          Bridge server
ESP32           172.18.16.43    80            Light control
Mobile Device   (varies)        (client)      App interface
```

### ESP32 Wiring Diagram
```
┌─────────────┐
│    ESP32    │
│             │
│  GPIO 4 ────┬─────[220Ω Resistor]──┐
│             │                       │
│  GND ───────┴───────────────────┬───┴─── (to LED cathode)
│             │                   │
│             │                 ┌─┴─┐
│             │                 │LED│ (anode to GPIO 4)
│             │                 └───┘
└─────────────┘
```

---

## 📦 Software Requirements

### Python Dependencies (Laptop)
```bash
flask>=2.0.0
flask-cors>=3.0.10
paramiko>=2.9.0
opencv-python>=4.5.0
numpy>=1.19.0
Pillow>=8.0.0
```

### React Native/Expo Dependencies (App)
```json
{
  "expo": "^48.0.0",
  "expo-router": "^2.0.0",
  "react-native": "0.71.0",
  "axios": "^1.3.0",
  "zustand": "^4.3.0",
  "@expo/vector-icons": "^13.0.0",
  "react-native-safe-area-context": "^4.5.0"
}
```

### Arduino Libraries (ESP32)
```cpp
#include <WiFi.h>
#include <WebServer.h>
```

---

## 🚀 Installation & Setup

### Step 1: NAO Robot Configuration

```bash
# Power on NAO robot
# Connect to WiFi network: ll_cst_labs
# SSH into robot
ssh nao@172.18.16.38
# Password: nao

# Test NAOqi connection
telnet 172.18.16.38 9559
```

### Step 2: ESP32 Setup

1. **Install Arduino IDE or PlatformIO**
2. **Upload the sketch:**
   ```cpp
   // Configure WiFi credentials
   const char* ssid = "ll_cst_labs";
   const char* password = "your_password";
   const int LED_PIN = 4;
   
   // Upload to ESP32
   ```
3. **Connect LED to GPIO 4**
4. **Power on ESP32**
5. **Verify IP address:** `172.18.16.43`

### Step 3: Laptop Server Setup

```bash
# Clone the repository
git clone https://github.com/sushanthsujeerkumar/nao-robot-control-app.git
cd nao-robot-control-app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials (create .env file)
cat > .env << EOF
NAO_IP=172.18.16.38
NAO_PORT=9559
LAPTOP_IP=172.18.16.41
LAPTOP_PORT=5000
ESP32_IP=172.18.16.43
GMAIL_USER=your_email@gmail.com
GMAIL_PASSWORD=your_app_password
EOF

# Run the server
python nao_final.py
# Server running on http://172.18.16.41:5000
```

### Step 4: Mobile App Setup

```bash
# Navigate to app directory
cd mobile-app

# Install dependencies
npm install
# or
yarn install

# Start Expo development server
npx expo start

# Connect from mobile device:
# 1. Install Expo Go app
# 2. Scan QR code
# 3. Enter server IP: 172.18.16.41:5000
```

---

## 📱 Mobile App Tabs

### **Tab 1: Connect** 📡
- Enter laptop IP address and port
- Connect/Disconnect buttons
- Connection status indicator
- Robot information:
  - Battery level
  - Temperature
  - Posture status

### **Tab 2: Control** 🎮
- **Directional joystick:**
  - Forward, Backward
  - Left, Right rotation
  - Speed adjustment (0-100%)
- Emergency stop button

### **Tab 3: Actions** 🎭
22 gesture buttons with icons:
- **Emotions:** happy, sad, angry, surprised
- **Social:** wave, handshake, bow, clap
- **Actions:** think, dance, celebrate, stretch
- **Positions:** stand, sit, crouch, lookup, lookdown
- **Special:** yes, no, kungfu, lookleft, lookright

### **Tab 4: Speech** 🗣️
- Text input for robot to speak
- Adjustable speech speed (0-100%)
- Adjustable volume (0-100%)
- Language selection

### **Tab 5: Sensors** 📊
Real-time monitoring:
- Battery percentage & voltage
- Temperature readings
- Sonar distance sensors
- Joint positions
- Pressure sensors

### **Tab 6: Functions** ⚙️
Advanced features with sub-tabs:

#### **Fall Detection Sub-tab:**
- Start/Stop monitoring
- Test system components
- Status display
- Alert history

#### **Exercise Sub-tab:**
- Start/Stop session
- Yes/No response buttons
- Progress display
- Session statistics

#### **Automation Sub-tab:**
- Light ON/OFF buttons
- Voice command listener
- "NAO Speaks Then Controls" mode
- ESP32 status

#### **Storytelling Sub-tab:**
- Story selection cards
- Play/Stop buttons
- Current story status
- Story progress indicator

---

## 🔌 API Documentation

### **Connection Endpoints**

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| POST | `/api/robot/connect` | Connect to NAO | `{ip, port}` |
| POST | `/api/robot/disconnect` | Disconnect from robot | - |
| GET | `/api/robot/status` | Get robot status | - |

### **Movement & Actions**

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| POST | `/api/robot/move` | Move robot | `{x, y, theta, speed}` |
| POST | `/api/robot/stop` | Stop movement | - |
| POST | `/api/robot/speak` | Text-to-speech | `{text, speed, volume}` |
| POST | `/api/robot/gesture` | Execute gesture | `{gesture_name}` |
| GET | `/api/robot/gestures` | List all gestures | - |
| GET | `/api/robot/sensors` | Get sensor data | - |

### **Fall Detection**

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| POST | `/api/robot/fall_detection/start` | Start monitoring | `{email}` |
| POST | `/api/robot/fall_detection/stop` | Stop monitoring | - |
| GET | `/api/robot/fall_detection/status` | Get detection status | - |
| POST | `/api/robot/fall_detection/test` | Test all components | - |

### **Exercise**

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| POST | `/api/robot/exercise/start` | Start session | - |
| POST | `/api/robot/exercise/stop` | Stop session | - |
| GET | `/api/robot/exercise/status` | Get session status | - |
| POST | `/api/robot/exercise/respond` | Send response | `{response: "yes"/"no"}` |

### **Smart Home Automation**

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| POST | `/api/automation/light` | Control light | `{action: "on"/"off"}` |
| POST | `/api/automation/voice_light` | NAO speaks then controls | `{action: "on"/"off"}` |
| POST | `/api/automation/listen_command` | Listen for voice | - |
| POST | `/api/automation/set_ip` | Set ESP32 IP | `{ip_address}` |
| GET | `/api/automation/status` | Get ESP32 status | - |

### **Storytelling**

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| POST | `/api/storytelling/play` | Play story | `{story_id: 1-5}` |
| POST | `/api/storytelling/stop` | Stop story | - |
| GET | `/api/storytelling/status` | Get playback status | - |
| GET | `/api/storytelling/list` | List all stories | - |

### **Example API Calls**

```bash
# Connect to robot
curl -X POST http://172.18.16.41:5000/api/robot/connect \
  -H "Content-Type: application/json" \
  -d '{"ip": "172.18.16.38", "port": 9559}'

# Make robot speak
curl -X POST http://172.18.16.41:5000/api/robot/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello everyone!", "speed": 100, "volume": 100}'

# Turn on light
curl -X POST http://172.18.16.41:5000/api/automation/light \
  -H "Content-Type: application/json" \
  -d '{"action": "on"}'

# Start exercise
curl -X POST http://172.18.16.41:5000/api/robot/exercise/start
```

---

## 🎬 Demo Scenarios

### **Scenario 1: Fall Detection Demo** 🚨
```
1. Open app → Functions → Fall Detection
2. Click "Start Monitoring"
3. Person lies down on floor
4. After 12 seconds: Robot says "Are you okay?"
5. No response given
6. Alert email sent with photo
7. Caregiver receives emergency notification
```

### **Scenario 2: Exercise Session Demo** 💪
```
1. Open app → Functions → Exercise
2. Click "Start Session"
3. Robot: "Let's exercise together! Are you ready?"
4. Click "Yes" button
5. Robot demonstrates squat (3 times)
6. Robot: "Your turn! Do a squat."
7. User performs squat
8. Repeat for arm stretches
9. Cooldown with breathing
10. Robot: "Great job! Well done!"
```

### **Scenario 3: Smart Home Automation Demo** 💡
```
1. Open app → Functions → Automation
2. Click "Turn ON" button
3. ESP32 LED turns on immediately
4. Click "Voice Listen"
5. Say "turn off the light"
6. NAO says "I heard 'turn off', turning off the light"
7. ESP32 LED turns off
```

### **Scenario 4: Storytelling Demo** 📚
```
1. Open app → Functions → Storytelling
2. Select story: "The Tortoise and the Hare"
3. Click "Play"
4. NAO narrates: "Once upon a time..."
5. NAO performs gestures throughout story
6. NAO bows and says "I hope you enjoyed!"
```

---

## 📊 Project Statistics

| Metric | Value |
|--------|-------|
| **Python Code** | ~1,750 lines |
| **React Native Code** | ~2,500 lines |
| **API Endpoints** | 24 |
| **Gesture Actions** | 22 |
| **Stories** | 5 |
| **Exercise Types** | 3 |
| **Team Members** | 4 |
| **Development Period** | 6 months |

### Language Composition
```
Python:      73.1%  ███████████████████████████████░
TypeScript:  24.8%  ███████████░
C++:          1.1%  ░
JavaScript:   1.0%  ░
```

---

## 🔮 Future Enhancements

### Fall Detection
- [ ] Night vision camera support
- [ ] Multi-person fall detection
- [ ] Depth camera integration
- [ ] Machine learning model optimization

### Exercise Module
- [ ] Additional exercise types (lunges, neck rolls, balance exercises)
- [ ] Pose estimation for form correction
- [ ] Personalized workout plans
- [ ] Calorie tracking

### Smart Home Automation
- [ ] Support for multiple smart devices
- [ ] Voice command expansion
- [ ] Smart scheduling & automation
- [ ] Integration with Alexa/Google Home

### Storytelling
- [ ] Custom story uploads
- [ ] Story editing interface
- [ ] Multiple language support
- [ ] User rating & feedback system

### General Improvements
- [ ] User authentication & profiles
- [ ] Cloud data synchronization
- [ ] Advanced analytics dashboard
- [ ] Real-time performance monitoring
- [ ] Offline mode support

---

## 📝 Documentation

### Important Files
```
nao-robot-control-app/
├── backend/
│   ├── nao_final.py              # Main Flask server
│   ├── fall_detection.py         # OpenCV fall detection
│   ├── exercise_module.py        # Exercise FSM
│   ├── automation_control.py     # ESP32 integration
│   └── storytelling_engine.py    # Story engine
├── mobile-app/
│   ├── app/
│   │   ├── (connect)/index.tsx   # Connection tab
│   │   ├── (control)/index.tsx   # Control tab
│   │   ├── (actions)/index.tsx   # Actions tab
│   │   ├── (speech)/index.tsx    # Speech tab
│   │   ├── (sensors)/index.tsx   # Sensors tab
│   │   └── (functions)/          # Advanced features
│   └── store/                    # Zustand state
├── esp32/
│   └── light_control.ino         # ESP32 firmware
└── README.md                     # This file
```

---

## 🤝 Contributing

We welcome contributions! Please feel free to:
1. Fork the repository
2. Create a feature branch
3. Submit pull requests
4. Report issues and suggest improvements

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📧 Contact & Support

**Project Team:**
- **Sushanth** - Fall Detection System
- **Deshwin** - Smart Home Automation
- **Natasha** - Exercise Module
- **Arooj** - Storytelling System

**For questions or support:**
- Open an issue on GitHub
- Contact the development team

---

## 🙏 Acknowledgments

- NAO Robot Community
- Softbank Robotics
- Expo & React Native Community
- OpenCV Contributors
- Flask Framework Team

---

**Last Updated:** May 2026  
**Project Status:** ✅ Complete & Functional  
**Repository:** [nao-robot-control-app](https://github.com/sushanthsujeerkumar/nao-robot-control-app)

---

<div align="center">

**Made with ❤️ by the NAO Companion Team**

⭐ If you find this project helpful, please star the repository!

</div>
