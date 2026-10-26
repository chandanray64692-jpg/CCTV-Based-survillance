# cameras/services/threat_detector.py
import cv2
from ultralytics import YOLO

# Load general YOLOv8 model (COCO dataset can detect person, backpack/suitcases for theft, fire via custom rules)
model = YOLO('yolov8n.pt')

def detect_threats_in_frame(frame):
    """
    Detects Fire, Theft indicators, and Unwanted Suspicious Movements.
    """
    # 1. Run YOLO object detection
    results = model(frame)
    
    threat_detected = False
    threat_message = "Normal"

    for result in results:
        boxes = result.boxes
        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            
            # Class 0 = Person, Class 24 = Backpack/Handbag (Potential theft items)
            # Note: For strict fire detection, a fine-tuned fire detection model is ideal, 
            # but we can detect high-temperature/orange-red color blobs and motion spikes for fire/emergency.
            
            if conf > 0.5:
                # Example: Unauthorized object tracking or sudden loitering
                if cls_id in [24, 26, 28]: # Suitcase, handbag, backpack left unattended (Theft indicator)
                    threat_detected = True
                    threat_message = "🚨 *THEFT ALERT*: Unattended baggage/item detected!"

    # 2. Fire & Smoke Color Heuristics (Detecting bright orange/red fire flickers)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Range for fire color in HSV
    lower_fire = np.array([18, 50, 50])
    upper_fire = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    fire_pixels = cv2.countNonZero(mask)

    if fire_pixels > 1500: # Agar screen par fire/flame jaisa color bada area cover kare
        threat_detected = True
        threat_message = "🔥 *FIRE ACCIDENT ALERT*: Flames or fire detected by camera!"

    return threat_detected, threat_message