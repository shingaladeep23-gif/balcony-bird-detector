import os
import cv2
import numpy as np
from ultralytics import YOLO

def test_bird_detection(image_path, output_path):
    print(f"Loading test image: {image_path}")
    if not os.path.exists(image_path):
        print(f"[ERROR] Test image not found at: {image_path}")
        return

    # Load YOLOv8 Model
    print("Loading YOLOv8 Nano model...")
    try:
        model = YOLO("yolov8n.pt")
        print("[OK] Model loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return

    # Read image
    img = cv2.imread(image_path)
    if img is None:
        print("[ERROR] OpenCV failed to read the image file.")
        return
        
    h, w, _ = img.shape
    print(f"Image Resolution: {w}x{h}")

    # Run inference
    print("Running bird detection inference...")
    results = model(img, verbose=False)
    
    bird_detected = False
    
    for result in results:
        boxes = result.boxes
        print(f"Total objects detected in frame: {len(boxes)}")
        
        for index, box in enumerate(boxes):
            class_id = int(box.cls[0])
            conf = float(box.conf[0])
            class_name = model.names[class_id]
            
            # Extract coordinates (xyxy)
            xyxy = box.xyxy[0].cpu().numpy()
            x_min, y_min, x_max, y_max = map(int, xyxy)
            
            print(f" -> Detection #{index+1}: Label='{class_name}' (ID: {class_id}), Conf={conf*100:.1f}%, Box=[{x_min}, {y_min}, {x_max}, {y_max}]")
            
            # Check if it is a bird (Class 14)
            if class_id == 14:
                bird_detected = True
                # Draw Box on image (Bright Emerald Green in BGR)
                cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (129, 230, 16), 4)
                # Bounding box label
                cv2.putText(
                    img, 
                    f"BIRD: {conf*100:.1f}%", 
                    (x_min, y_min - 15), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, 
                    (129, 230, 16), 
                    2
                )
                
    if bird_detected:
        print(f"\n[OK] SUCCESS! A bird was successfully identified in the test frame.")
        # Save output image
        cv2.imwrite(output_path, img)
        print(f"[OK] Annotated output saved at: {output_path}")
    else:
        print("\n[WARNING] No bird detected in this test frame. Detections were made on other classes or confidence was below standard thresholds.")

if __name__ == "__main__":
    # Test on the generated sparrow image
    test_img = r"C:\Users\shingala\.gemini\antigravity\brain\1de78909-fcf0-4742-88e0-c354552aa782\sparrow_balcony_1779268721175.png"
    out_img = r"d:\Bird Detection\sparrow_detected.png"
    test_bird_detection(test_img, out_img)
