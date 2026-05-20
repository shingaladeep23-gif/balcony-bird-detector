import os
import cv2
import time
import json
import logging
import threading
import numpy as np
from datetime import datetime
from ultralytics import YOLO
import notifier
import serial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Detector")

class BirdDetector:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config()

        # State management
        self.running = False
        self.latest_raw_frame = None
        self.latest_annotated_frame = None
        self.frame_lock = threading.Lock()
        
        # Connection status
        self.camera_status = "Disconnected"  # "Connected", "Disconnected", "Error"
        self.model_status = "Loading..."
        
        # Cooldown management
        self.last_alert_time = 0
        
        # Hysteresis counters
        self.consecutive_frames_counter = 0

        # Arduino integration
        self.arduino = None
        self.arduino_status = "Disabled"
        self.last_arduino_port = None
        self.last_arduino_enabled = False

        # Create directories for captures
        os.makedirs("static/captures", exist_ok=True)
        self.logs_path = "static/captures/logs.json"
        if not os.path.exists(self.logs_path):
            with open(self.logs_path, "w") as f:
                json.dump([], f)

        # Threading for capturing
        self.capture_thread = None
        self.model = None

    def load_config(self):
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config.json: {e}")
            return {
                "camera_url": "0",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "confidence_threshold": 0.5,
                "cooldown_minutes": 5,
                "consecutive_frames": 5,
                "detection_zone": [],
                "arduino_port": "",
                "arduino_enabled": False
            }

    def save_config(self, new_config):
        self.config = new_config
        try:
            with open(self.config_path, "w") as f:
                json.dump(new_config, f, indent=2)
            logger.info("Configuration updated successfully.")
        except Exception as e:
            logger.error(f"Failed to write config.json: {e}")

    def load_model(self):
        try:
            self.model_status = "Loading..."
            # Using CPU by default, it will auto-detect GPU if PyTorch is configured with CUDA.
            logger.info("Initializing YOLOv8 model...")
            self.model = YOLO("yolov8n.pt")
            self.model_status = "Active"
            logger.info("YOLOv8 model loaded successfully.")
        except Exception as e:
            self.model_status = f"Error: {str(e)}"
            logger.error(f"Error loading YOLOv8 model: {e}")

    def start(self):
        if self.running:
            return
        self.running = True
        self.load_model()
        self.capture_thread = threading.Thread(target=self._capture_and_detect_loop, daemon=True)
        self.capture_thread.start()
        logger.info("Bird detection background thread started.")

    def stop(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=3)
        self.camera_status = "Disconnected"
        self._close_arduino_serial()
        logger.info("Bird detection thread stopped.")

    def _init_arduino_serial(self, port, enabled):
        self._close_arduino_serial()
        self.last_arduino_port = port
        self.last_arduino_enabled = enabled
        
        if not enabled or not port:
            self.arduino_status = "Disabled"
            return
            
        try:
            logger.info(f"Connecting to Arduino on serial port {port} at 9600 baud...")
            # Set a timeout so opening does not hang indefinitely
            self.arduino = serial.Serial(port, 9600, timeout=1)
            # Give Arduino time to auto-reset
            time.sleep(1.5)
            self.arduino_status = "Connected"
            logger.info("Arduino serial connection established successfully.")
        except Exception as e:
            self.arduino_status = f"Error: {str(e)}"
            self.arduino = None
            logger.error(f"Failed to connect to Arduino on port {port}: {e}")

    def _close_arduino_serial(self):
        if self.arduino:
            try:
                self.arduino.close()
                logger.info("Arduino serial port closed.")
            except Exception as e:
                logger.error(f"Error closing Arduino serial port: {e}")
            self.arduino = None
        self.arduino_status = "Disabled"

    def _trigger_arduino_spray(self, angle=90):
        if self.arduino and self.arduino.is_open:
            try:
                # Clamp angle to safe sweep boundaries [45, 135]
                clamped_angle = max(45, min(135, int(angle)))
                command = f"S{clamped_angle}\n"
                logger.info(f"Sending spray command '{command.strip()}' to Arduino...")
                self.arduino.write(command.encode('ascii'))
                self.arduino.flush()
                return True, f"Spray command '{command.strip()}' sent to Arduino."
            except Exception as e:
                logger.error(f"Failed to write to Arduino serial port: {e}")
                self.arduino_status = f"Error: {str(e)}"
                return False, f"Failed to send command: {e}"
        else:
            logger.warning("Attempted to trigger water spray, but Arduino is not connected or enabled.")
            return False, "Arduino is not connected or enabled."

    def trigger_manual_spray(self):
        logger.info("Manual spray override requested.")
        return self._trigger_arduino_spray(angle=90)

    def _capture_and_detect_loop(self):
        cap = None
        reconnect_delay = 5
        
        while self.running:
            camera_url = self.config.get("camera_url", "0")
            # Parse webcam index
            if camera_url.isdigit():
                camera_url = int(camera_url)

            logger.info(f"Connecting to video stream: {camera_url}...")
            cap = cv2.VideoCapture(camera_url)
            
            if not cap.isOpened():
                self.camera_status = "Error"
                logger.error(f"Failed to open video source: {camera_url}. Retrying in {reconnect_delay}s...")
                time.sleep(reconnect_delay)
                continue

            self.camera_status = "Connected"
            logger.info("Video stream connection established.")

            # Frame timing to control inference rate (approx 10-15 FPS is plenty)
            target_fps = 15
            frame_delay = 1.0 / target_fps

            while self.running:
                start_time = time.time()
                ret, frame = cap.read()
                
                if not ret:
                    self.camera_status = "Error"
                    logger.warning("Failed to grab frame from camera. Reconnecting...")
                    break
                
                # Check for updates in config
                self.config = self.load_config()

                # If Arduino config changed, re-init serial connection
                current_port = self.config.get("arduino_port", "")
                current_enabled = self.config.get("arduino_enabled", False)
                if current_port != self.last_arduino_port or current_enabled != self.last_arduino_enabled:
                    self._init_arduino_serial(current_port, current_enabled)

                # Process the frame
                annotated = frame.copy()
                self._process_frame_ai(frame, annotated)

                # Store frames thread-safely
                with self.frame_lock:
                    self.latest_raw_frame = frame
                    self.latest_annotated_frame = annotated

                # Throttle logic
                elapsed = time.time() - start_time
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            cap.release()
            self.camera_status = "Disconnected"
            time.sleep(1)

    def _process_frame_ai(self, raw_frame, annotated_frame):
        h, w, _ = raw_frame.shape
        detection_zone = self.config.get("detection_zone", [])
        conf_thresh = self.config.get("confidence_threshold", 0.5)
        consecutive_req = self.config.get("consecutive_frames", 5)
        cooldown_min = self.config.get("cooldown_minutes", 5)

        # 1. Parse and Draw Active Detection Zone
        zone_polygon_px = []
        if detection_zone:
            zone_polygon_px = np.array([
                [int(pt["x"] * w), int(pt["y"] * h)] for pt in detection_zone
            ], dtype=np.int32)
            
            # Draw semi-transparent zone overlay
            overlay = annotated_frame.copy()
            cv2.fillPoly(overlay, [zone_polygon_px], (241, 102, 99)) # Sleek Electric Indigo in BGR
            cv2.polylines(annotated_frame, [zone_polygon_px], True, (241, 102, 99), 2)
            cv2.addWeighted(overlay, 0.15, annotated_frame, 0.85, 0, annotated_frame)
        else:
            # Full screen overlay hint (light border)
            cv2.rectangle(annotated_frame, (5, 5), (w-5, h-5), (99, 102, 241), 1)

        # 2. Run YOLOv8 Inference
        bird_detected_this_frame = False
        detected_bird_box = None
        detected_bird_conf = 0.0

        if self.model:
            results = self.model(raw_frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # Class 14 is 'bird' in COCO dataset
                    if class_id == 14 and conf >= conf_thresh:
                        # Extract coordinates (xyxy)
                        xyxy = box.xyxy[0].cpu().numpy()
                        x_min, y_min, x_max, y_max = map(int, xyxy)
                        
                        # Calculate anchor point (bottom center of the bounding box)
                        px = int((x_min + x_max) / 2)
                        py = int(y_max)
                        
                        # Filter by Active Zone
                        in_zone = True
                        if len(zone_polygon_px) > 0:
                            dist = cv2.pointPolygonTest(zone_polygon_px, (px, py), False)
                            in_zone = (dist >= 0)
                        
                        if in_zone:
                            bird_detected_this_frame = True
                            detected_bird_box = (x_min, y_min, x_max, y_max)
                            detected_bird_conf = conf
                            
                            # Draw active target box (Bright Emerald Green in BGR)
                            cv2.rectangle(annotated_frame, (x_min, y_min), (x_max, y_max), (129, 230, 16), 2)
                            cv2.circle(annotated_frame, (px, py), 6, (129, 230, 16), -1)
                            cv2.putText(
                                annotated_frame, 
                                f"Bird: {conf:.2f}", 
                                (x_min, y_min - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.6, 
                                (129, 230, 16), 
                                2
                            )
                        else:
                            # Draw out-of-zone target box (Muted orange/yellow in BGR)
                            cv2.rectangle(annotated_frame, (x_min, y_min), (x_max, y_max), (0, 165, 255), 1)
                            cv2.circle(annotated_frame, (px, py), 4, (0, 165, 255), -1)
                            cv2.putText(
                                annotated_frame, 
                                "Bird (Out of Zone)", 
                                (x_min, y_min - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.5, 
                                (0, 165, 255), 
                                1
                            )

        # 3. Trigger & Hysteresis Engine
        current_time = time.time()
        cooldown_seconds = cooldown_min * 60
        on_cooldown = (current_time - self.last_alert_time) < cooldown_seconds
        
        if bird_detected_this_frame:
            self.consecutive_frames_counter += 1
            logger.debug(f"Bird detected in zone. Counter: {self.consecutive_frames_counter}/{consecutive_req}")
            
            # Fire alert if hysteresis threshold is reached and we are not in cooldown
            if self.consecutive_frames_counter >= consecutive_req:
                # Reset counter to prevent repeated rapid alerts if hysteresis is satisfied
                self.consecutive_frames_counter = 0 
                
                if not on_cooldown:
                    logger.info("Hysteresis passed! Launching bird detection trigger.")
                    self.last_alert_time = current_time
                    
                    # Calculate targeting angle based on bird horizontal center
                    x_min, y_min, x_max, y_max = detected_bird_box
                    x_center = (x_min + x_max) / 2.0
                    x_norm = x_center / w  # Normalized coordinate (0.0 to 1.0)
                    
                    # Map x_norm to angle (60 deg camera FOV centered at 90 deg)
                    target_angle = int(90.0 + (x_norm - 0.5) * 60.0)
                    logger.info(f"Targeting bird: x_norm={x_norm:.3f} -> physical angle={target_angle} deg")
                    
                    # Trigger automated water spray deterrent with targeted angle
                    self._trigger_arduino_spray(angle=target_angle)
                    
                    # Create photo capture (with annotation)
                    # Prepare image bytes for sending via Telegram and saving
                    _, img_encoded = cv2.imencode('.jpg', annotated_frame)
                    img_bytes = img_encoded.tobytes()
                    
                    # Log visit
                    self._log_visit(detected_bird_conf, annotated_frame)
                    
                    # Push mobile notification
                    self._fire_alert_notification(detected_bird_conf, img_bytes)
                else:
                    logger.info("Bird detected, but alert throttled by cooldown timer.")
        else:
            # Cool down counter when no bird is detected
            if self.consecutive_frames_counter > 0:
                self.consecutive_frames_counter -= 1

        # 4. Status Indicator Overlay
        # Draw status card on the top left
        cv2.rectangle(annotated_frame, (10, 10), (220, 75), (25, 18, 11), -1) # Dark card background
        cv2.rectangle(annotated_frame, (10, 10), (220, 75), (63, 59, 56), 1) # Card border
        
        cv2.putText(annotated_frame, "AI DETECTION STATUS", (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        
        status_color = (0, 0, 255) # Disconnected (Red)
        if self.camera_status == "Connected":
            status_color = (129, 230, 16) # Connected (Emerald)
        
        cv2.circle(annotated_frame, (25, 45), 5, status_color, -1)
        cv2.putText(annotated_frame, f"CAM: {self.camera_status}", (38, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        if on_cooldown:
            remaining = int(cooldown_seconds - (current_time - self.last_alert_time))
            cv2.putText(annotated_frame, f"COOLDOWN ({remaining}s)", (20, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
        else:
            cv2.putText(annotated_frame, "MONITORING ACTIVE", (20, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (129, 230, 16), 1)

    def _log_visit(self, confidence, frame):
        """Saves physical capture image and appends a entry in logs.json."""
        timestamp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"capture_{timestamp_id}.jpg"
        filepath = os.path.join("static/captures", filename)
        
        try:
            cv2.imwrite(filepath, frame)
            
            # Read existing logs
            logs = []
            if os.path.exists(self.logs_path):
                with open(self.logs_path, "r") as f:
                    logs = json.load(f)
            
            # Add new log item
            new_log = {
                "id": timestamp_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "confidence": round(confidence, 2),
                "image_path": f"/static/captures/{filename}"
            }
            logs.insert(0, new_log)  # Prepend so newest is first
            
            # Keep log count sane (e.g., last 100 entries)
            logs = logs[:100]
            
            with open(self.logs_path, "w") as f:
                json.dump(logs, f, indent=2)
                
            logger.info(f"Captured visit logged: {filename}")
        except Exception as e:
            logger.error(f"Failed to log bird visit: {e}")

    def _fire_alert_notification(self, confidence, image_bytes):
        """Assembles and triggers the async Telegram notifier."""
        token = self.config.get("telegram_bot_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        
        time_str = datetime.now().strftime("%H:%M:%S")
        message = (
            f"🐦 <b>Bird Detected on Balcony!</b>\n"
            f"🕒 <b>Time:</b> {time_str}\n"
            f"🎯 <b>AI Confidence:</b> {confidence * 100:.1f}%\n"
            f"✨ <i>Visit registered in your local Web Dashboard history log.</i>"
        )
        
        notifier.send_notification(token, chat_id, message, image_bytes)

    def get_latest_frame_bytes(self):
        """Returns the latest annotated frame as JPEG bytes for the live web stream."""
        with self.frame_lock:
            if self.latest_annotated_frame is None:
                # Return a black loading frame if camera is loading
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    black_frame, 
                    "Camera Stream Loading...", 
                    (120, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, 
                    (255, 255, 255), 
                    2
                )
                _, img_encoded = cv2.imencode('.jpg', black_frame)
                return img_encoded.tobytes()
                
            _, img_encoded = cv2.imencode('.jpg', self.latest_annotated_frame)
            return img_encoded.tobytes()

    def send_test_telegram(self):
        """Triggers a test message + dummy camera frame instantly."""
        token = self.config.get("telegram_bot_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        
        if not token or not chat_id:
            return False, "Bot Token or Chat ID not configured."

        time_str = datetime.now().strftime("%H:%M:%S")
        message = (
            f"🔔 <b>Balcony Bird Detector: Test Alert</b>\n"
            f"🕒 <b>Trigger Time:</b> {time_str}\n"
            f"✅ <i>Your connection to the detector bot is working flawlessly!</i>"
        )
        
        # Draw a beautiful mock frame
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Create subtle blue background gradient
        for y in range(480):
            mock_frame[y, :] = (40 + int(y/12), 20 + int(y/24), 10 + int(y/48))
            
        cv2.putText(mock_frame, "TEST NOTIFICATION PROOF", (140, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (99, 102, 241), 2)
        cv2.rectangle(mock_frame, (200, 180), (440, 360), (129, 230, 16), 2)
        cv2.putText(mock_frame, "Mock Bird (99.8%)", (200, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (129, 230, 16), 2)
        # Draw a circular bird representation
        cv2.circle(mock_frame, (320, 270), 50, (129, 230, 16), -1)
        cv2.circle(mock_frame, (355, 230), 20, (129, 230, 16), -1)
        # Orange beak
        cv2.fillPoly(mock_frame, [np.array([[370, 225], [385, 230], [370, 235]])], (0, 165, 255))
        
        _, img_encoded = cv2.imencode('.jpg', mock_frame)
        notifier.send_notification(token, chat_id, message, img_encoded.tobytes())
        return True, "Test alert sent! Check your phone."
