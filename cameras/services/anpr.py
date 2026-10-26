# cameras/services/anpr.py
import cv2
import easyocr
import numpy as np
from ultralytics import YOLO
from django.core.files.base import ContentFile
from logs.models import VehicleLog
from cameras.models import CameraNode

# Load models (YOLOv8 nano model will auto-download on first run)
vehicle_model = YOLO('yolov8n.pt') 
reader = easyocr.Reader(['en'], gpu=False) # Set gpu=True if you have an NVIDIA GPU

def process_vehicle_frame(frame, camera_id):
    """
    Core AI Pipeline: Detect Vehicle -> Crop Plate -> OCR Text -> Log Entry
    """
    try:
        camera = CameraNode.objects.get(id=camera_id)
    except CameraNode.DoesNotExist:
        return {"status": "error", "message": "Camera not found"}

    # 1. Detect objects in the frame using YOLOv8
    results = vehicle_model(frame, classes=[2, 3, 5, 7]) # Class IDs for car, motorcycle, bus, truck

    for result in results:
        boxes = result.boxes
        for box in boxes:
            # Get bounding box coordinates for the vehicle
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            vehicle_crop = frame[y1:y2, x1:x2]

            if vehicle_crop.size == 0:
                continue

            # 2. Use EasyOCR to read text (License Plate) from the vehicle crop
            # In a production environment, you would use a specialized plate detector before OCR
            ocr_results = reader.readtext(vehicle_crop)
            
            for (bbox, text, prob) in ocr_results:
                # Filter out garbage text based on probability and length
                text = text.replace(" ", "").upper()
                if prob > 0.5 and 4 <= len(text) <= 10: 
                    
                    # 3. Save Snapshot
                    _, buffer = cv2.imencode('.jpg', vehicle_crop)
                    snapshot_file = ContentFile(buffer.tobytes(), name=f"vehicle_{text}.jpg")

                    # 4. Determine Entry/Exit Status
                    latest_log = VehicleLog.objects.filter(license_plate=text).order_by('-timestamp').first()
                    status = 'Exit' if (latest_log and latest_log.status == 'Entry') else 'Entry'

                    # 5. Save to Database
                    log = VehicleLog.objects.create(
                        license_plate=text,
                        camera=camera,
                        status=status,
                        snapshot=snapshot_file
                    )

                    return {
                        "status": "success",
                        "license_plate": text,
                        "gate_status": status,
                        "timestamp": str(log.timestamp.strftime('%Y-%m-%d %H:%M:%S'))
                    }

    return {"status": "failed", "message": "No valid license plate detected"}