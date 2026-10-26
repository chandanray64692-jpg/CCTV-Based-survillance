# visitors/services/detector.py
import cv2
from django.core.files.base import ContentFile
from visitors.models import Visitor
from logs.models import GateLog
from cameras.models import CameraNode
from deepface import DeepFace
from .liveness import check_liveness
from .tracker import update_visitor_footprint

def process_frame_and_log(frame, camera_id):
    """
    Core AI Pipeline: Frame Capture -> Liveness Check -> DeepFace Matching -> Footprint Tracking -> Log Entry
    """
    try:
        camera = CameraNode.objects.get(id=camera_id)
    except CameraNode.DoesNotExist:
        return {"status": "error", "message": "CameraNode not found"}

    # ==========================================
    # STEP 1: LIVENESS & ANTI-SPOOFING CHECK
    # ==========================================
    is_live, liveness_msg = check_liveness(frame)
    if not is_live:
        # Save snapshot of spoof attempt
        _, buffer = cv2.imencode('.jpg', frame)
        snapshot_file = ContentFile(buffer.tobytes(), name=f"spoof_alert_{camera.id}.jpg")
        
        # Log unknown/spoof attempt
        GateLog.objects.create(
            visitor=None,
            camera=camera,
            status='Unknown',
            snapshot=snapshot_file
        )
        return {
            "status": "spoof_detected",
            "visitor": "SPOOF / FAKE ATTEMPT",
            "gate_status": "BLOCKED",
            "timestamp": "NOW"
        }

    # ==========================================
    # STEP 2: DEEPFACE AI RECOGNITION PIPELINE
    # ==========================================
    visitors = Visitor.objects.all()
    matched_visitor = None

    for visitor in visitors:
        if visitor.photo:
            try:
                result = DeepFace.verify(
                    img1_path=frame, 
                    img2_path=visitor.photo.path, 
                    model_name="VGG-Face", 
                    enforce_detection=False
                )
                if result.get("verified"):
                    matched_visitor = visitor
                    break
            except Exception as e:
                print(f"AI Processing Error for {visitor.name}: {e}")
                continue

    # ==========================================
    # STEP 3: SNAPSHOT & STATUS LOGGING
    # ==========================================
    _, buffer = cv2.imencode('.jpg', frame)
    snapshot_file = ContentFile(buffer.tobytes(), name=f"log_cam_{camera.id}.jpg")

    status = "Unknown"
    if matched_visitor:
        latest_log = GateLog.objects.filter(visitor=matched_visitor).order_by('-timestamp').first()
        if latest_log and latest_log.status == 'Entry':
            status = 'Exit'
        else:
            status = 'Entry'

    log = GateLog.objects.create(
        visitor=matched_visitor,
        camera=camera,
        status=status,
        snapshot=snapshot_file
    )

    # ==========================================
    # STEP 4: GEO-FOOTPRINT TRACKING (RE-ID)
    # ==========================================
    path_trail = "Single Point"
    if matched_visitor:
        path_trail = update_visitor_footprint(matched_visitor, camera, snapshot_file)

    return {
        "status": "success",
        "visitor": matched_visitor.name if matched_visitor else "Unknown",
        "gate_status": status,
        "timestamp": str(log.timestamp.strftime('%Y-%m-%d %H:%M:%S')),
        "footprint": path_trail  # Multi-camera tracking trail
    }