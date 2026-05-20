import sys
import numpy as np

print("Checking OpenCV installation...")
try:
    import cv2
    print(f"[OK] OpenCV version: {cv2.__version__}")
except Exception as e:
    print(f"[ERROR] OpenCV import failed: {e}")
    sys.exit(1)

print("Checking PyTorch & Ultralytics installation...")
try:
    from ultralytics import YOLO
    print("[OK] Ultralytics YOLO imported successfully.")
except Exception as e:
    print(f"[ERROR] Ultralytics import failed: {e}")
    sys.exit(1)

def run_test():
    print("Loading yolov8n.pt model...")
    try:
        model = YOLO("yolov8n.pt")
        print("[OK] YOLOv8 Nano model loaded successfully.")
        
        print("Running mock inference on a blank frame...")
        blank_image = np.zeros((480, 640, 3), dtype=np.uint8)
        results = model(blank_image, verbose=False)
        print("[OK] Inference completed successfully.")
        print(f"Number of detections on blank frame: {len(results[0].boxes)}")
        print("\n[OK] Environment and YOLO Model are fully verified and operational!")
    except Exception as e:
        print(f"[ERROR] Inference failed: {e}")

if __name__ == "__main__":
    run_test()

