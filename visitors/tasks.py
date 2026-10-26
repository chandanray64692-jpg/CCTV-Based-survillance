from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import cv2

# Import all detection services
from .services.detector import process_frame_and_log
from cameras.services.anpr import process_vehicle_frame
from cameras.services.analytics import check_night_intrusion, check_crowd_and_loitering
from cameras.services.threat_detector import detect_threats_in_frame
from core.telegram import send_telegram_alert

@shared_task(bind=True)
def run_ai_surveillance_task(self, camera_id, rtsp_url):
    cap = cv2.VideoCapture(rtsp_url)
    success, frame = cap.read()
    cap.release()

    if not success or frame is None:
        return {"status": "failed", "message": "Could not read frame from camera"}

    channel_layer = get_channel_layer()

    # ==========================================
    # 1. INTRUSION DETECTION (NIGHT SECURITY)
    # ==========================================
    try:
        is_intrusion, intrusion_msg = check_night_intrusion(frame)
        if is_intrusion:
            async_to_sync(channel_layer.group_send)(
                "secure_vision_dashboard",
                {
                    "type": "send_alert",
                    "message": {
                        "visitor": "🚨 INTRUDER DETECTED",
                        "gate_status": "RESTRICTED HOURS",
                        "timestamp": "NOW",
                        "type": "Human"
                    }
                }
            )
            send_telegram_alert(f"{intrusion_msg}\nCamera ID: {camera_id}")
    except Exception as e:
        print(f"Intrusion check error: {e}")

    # ==========================================
    # 2. CROWD & LOITERING DETECTION
    # ==========================================
    try:
        is_crowd, crowd_msg = check_crowd_and_loitering(frame, crowd_threshold=4)
        if is_crowd:
            async_to_sync(channel_layer.group_send)(
                "secure_vision_dashboard",
                {
                    "type": "send_alert",
                    "message": {
                        "visitor": "⚠️ HIGH CROWD DETECTED",
                        "gate_status": "SECURITY ALERT",
                        "timestamp": "NOW",
                        "type": "Human"
                    }
                }
            )
            send_telegram_alert(f"{crowd_msg}\nCamera ID: {camera_id}")
    except Exception as e:
        print(f"Crowd check error: {e}")

    # ==========================================
    # 3. HUMAN FACE RECOGNITION & SPOOF DETECTION
    # ==========================================
    try:
        face_result = process_frame_and_log(frame, camera_id)
        if face_result:
            if face_result.get("status") == "spoof_detected":
                async_to_sync(channel_layer.group_send)(
                    "secure_vision_dashboard",
                    {
                        "type": "send_alert",
                        "message": {
                            "visitor": "🚨 FAKE PHOTO/SCREEN BLOCKED",
                            "gate_status": "SPOOF ATTACK",
                            "timestamp": face_result.get("timestamp", "NOW"),
                            "type": "Human"
                        }
                    }
                )
                send_telegram_alert(f"🚨 *SECURITY WARNING*: Spoof attempt detected at Camera ID: {camera_id}!")

            elif face_result.get("status") == "success":
                async_to_sync(channel_layer.group_send)(
                    "secure_vision_dashboard",
                    {
                        "type": "send_alert",
                        "message": {
                            "visitor": face_result.get("visitor"),
                            "gate_status": face_result.get("gate_status"),
                            "timestamp": face_result.get("timestamp"),
                            "type": "Human"
                        }
                    }
                )
                if face_result.get("visitor") == "Unknown":
                    send_telegram_alert(f"👤 *Unknown Person at Gate*\nAction: {face_result.get('gate_status')}\nCamera ID: {camera_id}")
    except Exception as e:
        print(f"Face recognition error: {e}")

    # ==========================================
    # 4. VEHICLE NUMBER PLATE (ANPR)
    # ==========================================
    try:
        vehicle_result = process_vehicle_frame(frame, camera_id)
        if vehicle_result and vehicle_result.get("status") == "success":
            async_to_sync(channel_layer.group_send)(
                "secure_vision_dashboard",
                {
                    "type": "send_alert",
                    "message": {
                        "visitor": f"Vehicle: {vehicle_result.get('license_plate')}",
                        "gate_status": vehicle_result.get("gate_status"),
                        "timestamp": vehicle_result.get("timestamp"),
                        "type": "Vehicle"
                    }
                }
            )
            send_telegram_alert(f"🚗 *Vehicle Detected*\nPlate: {vehicle_result.get('license_plate')}\nStatus: {vehicle_result.get('gate_status')}")
    except Exception as e:
        print(f"ANPR error: {e}")

    # ==========================================
    # 5. EMERGENCY & THREAT DETECTION
    # ==========================================
    try:
        is_threat, threat_msg = detect_threats_in_frame(frame)
        if is_threat:
            async_to_sync(channel_layer.group_send)(
                "secure_vision_dashboard",
                {
                    "type": "send_alert",
                    "message": {
                        "visitor": "⚠️ EMERGENCY THREAT",
                        "gate_status": threat_msg,
                        "timestamp": "NOW",
                        "type": "Human"
                    }
                }
            )
            send_telegram_alert(f"🚨 *CRITICAL EMERGENCY*\n{threat_msg}\nCamera ID: {camera_id}")
    except Exception as e:
        print(f"Threat detector error: {e}")

    return {"status": "processed globally"}