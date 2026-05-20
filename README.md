# 🐦 balcony-bird-detector: AI-Powered Balcony Bird Detector

balcony-bird-detector is an active, premium, and intelligent pest deterrent system designed to protect balcony railings and ledges from landing birds. Using real-time computer vision (Ultralytics YOLOv8), an interactive glassmorphic web dashboard, and instant mobile alerts, it maps physical targets in 2D space to dynamically pan and spray a water deterrent *exactly* where a bird lands.

---

## 🚀 Key Features

*   **Real-Time AI Vision (YOLOv8):** Scans CCTV RTSP streams, local webcams, or test videos to detect birds (COCO Class 14) with high-speed accuracy.
*   **Interactive Target Tracking:** Triangulates the exact horizontal center of the detected bird, maps it to a physical panning angle ($45^\circ \rightarrow 135^\circ$), and transmits targeted serial packets (`S[angle]\n`) to a micro-controller.
*   **Premium Glassmorphic Dashboard:** Built with vanilla HTML/CSS/JS and a high-performance FastAPI backend. Features live video streaming, configuration sliders, and a capture registry timeline.
*   **Draw-Your-Own Landing Zones:** Click-to-draw custom normalized polygon zones directly on top of the live stream feed, restricting triggers to specific ledges or railings.
*   **Active Servo-Aimed Deterrent:** Drives a 180° RC Servo motor and a 5V relay to sweep the water nozzle directly toward the target, wait $400\text{ms}$ for physical alignment, and fire a precise $1.5\text{s}$ spray burst.
*   **Fail-Safe Lockouts & Isolation:**
    *   *Hardware Level:* The microcontroller firmware enforces a strict **10-second lockout cooldown** to prevent balcony flooding.
    *   *Software Level:* Dashboard-configurable alert throttle timers (e.g. 5-minute alerts).
    *   *Connection Level:* Full USB port isolation — the system remains operational if the Arduino is unplugged or COM ports are swapped.
*   **Mobile Notification Proofs:** Sends real-time HTML-formatted Telegram messages accompanied by the annotated snapshot proof showing the exact bird bounding box.

---

## 📐 The Target Tracking Mathematics

balcony-bird-detector translates 2D pixel coordinates from your camera feed into a 1D physical sweep angle ($\theta$) for your servo motor:

$$\theta = 90^\circ + (x_{\text{norm}} - 0.5) \times \text{FOV}$$

Where:
*   $x_{\text{norm}}$ is the horizontal center of the bird's bounding box normalized from `0.0` (far left) to `1.0` (far right).
*   $\text{FOV}$ is the horizontal Field of View of your camera (defaulted to standard $60^\circ$).
*   $90^\circ$ is the straight-ahead calibration center.

---

## 🔌 Hardware Schematics (Servo Mode)

To set up the automated deterrent, connect your Arduino Uno using the following schematic:

```
                  +--------------------+
                  |    Arduino Uno     |
                  |                    |
                  |  Pin 9 (PWM) ------+--------> Servo Signal (Orange/Yellow)
                  |  Pin 4 ------------+--------> 5V Relay Signal (IN)
                  |  GND --------------+---+----> External VCC GND
                  +--------------------+   |
                                           |
  +------------------+                     |
  |  External VCC    | [GND] --------------+----> Servo GND (Brown/Black)
  |  Power (5V-6V)   | [5V-6V] -----------------> Servo VCC (Red)
  +------------------+
```

*Note: Always power high-torque servos (like the MG996R) using an external 5V-6V power source capable of delivering at least 2A. Never power the servo directly from the Arduino's 5V pin, or the controller will brown out.*

---

## 🛠️ Software Setup & Installation

### Prerequisites
*   Python 3.10+
*   Arduino IDE (for uploading firmware)
*   USB-A to USB-B cable

### 1. Backend Installation
Clone this repository and set up a Python virtual environment inside the folder:
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Microcontroller Upload
1.  Open the Arduino IDE.
2.  Open the C++ sketch located at `balcony_sprayer.ino`.
3.  Connect your Arduino Uno via USB.
4.  Select your Board (**Arduino Uno**) and your Port under Tools.
5.  Click **Upload** (Ctrl + U). The Tx/Rx LEDs will flash, and the onboard LED will double-blink to confirm calibration complete.

---

## 🖥️ Running the Application

Activate your virtual environment and boot up the FastAPI local server:
```powershell
.venv\Scripts\activate
python -m uvicorn app:app --reload
```

Open your web browser and navigate to: **`http://127.0.0.1:8000`**

### Inside the Dashboard:
1.  **Configure COM Port:** Enter your active Arduino port (e.g. `COM3` on Windows or `/dev/ttyACM0` on Linux) in the deterrent panel and toggle automated triggers **On**.
2.  **Test Spraying:** Click the blue **Manual Spray Override** button to fire a diagnostic test.
3.  **Active Landing Zone:** Click **Draw Detection Zone** and drop visual boundary points on your railing. Click **Save Zone**.
4.  **Telegram Notifications:** Enter your Bot Token and Chat ID under Settings to receive instant phone notifications.

---

## 📁 Repository Structure

```
d:\Bird Detection\
├── app.py                # FastAPI Web Server & MJPEG Router
├── detector.py           # OpenCV Frame Consumer, YOLOv8 Inference, & Serial Writer
├── notifier.py           # Async Telegram API Integration
├── balcony_sprayer.ino   # Arduino C++ Targeting Firmware
├── config.json           # Local system configuration settings
├── requirements.txt      # Python package dependencies
├── verify_model.py       # YOLOv8 nano validation script
├── test_serial_dryrun.py # PySerial isolation and robustness checks
└── static/
    ├── index.html        # Premium dashboard structural skeleton
    ├── styles.css        # Slate-dark Glassmorphic layout stylesheets
    ├── dashboard.js      # Zone drawing, AJAX polling, and settings sync logic
    └── captures/         # Local database folder for visit snapshot logs
```
