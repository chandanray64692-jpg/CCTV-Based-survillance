# cameras/services/analytics.py
from ultralytics import YOLO
from datetime import datetime

# Gaadiyon wala same YOLO model use karenge memory bachane ke liye
model = YOLO('yolov8n.pt') 

def check_night_intrusion(frame):
    """
    Detects unauthorized human presence during restricted hours (e.g., 10 PM to 6 AM).
    """
    current_hour = datetime.now().hour
    
    # Check if time is between 22:00 (10 PM) and 06:00 (6 AM)
    if current_hour >= 22 or current_hour < 6:
        results = model(frame, classes=[0]) # Class '0' = Human/Person
        
        for result in results:
            if len(result.boxes) > 0:
                # Agar insaan detect hua toh turant True return karein
                return True, "🚨 *INTRUSION ALERT*: Unauthorized person detected in restricted hours!"
                
    return False, "Clear"
# cameras/services/analytics.py (File ke end mein add karein)

def check_crowd_and_loitering(frame, crowd_threshold=4):
    """
    Detects if there are too many people (Crowd) gathered in the camera frame.
    crowd_threshold: Default 4 log ek sath dikhne par alert aayega.
    """
    results = model(frame, classes=[0]) # Class '0' = Human/Person
    
    for result in results:
        person_count = len(result.boxes)
        # Agar frame mein 4 ya usse zyada log hain, toh alert bhejo
        if person_count >= crowd_threshold:
            return True, f"⚠️ *CROWD ALERT*: {person_count} people detected gathering together!"
            
    return False, "Normal Traffic"