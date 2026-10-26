import cv2
import os
import time
import threading
import queue
import pyttsx3
from ultralytics import YOLO
from cameras.models import CameraNode

# --- SMART AUDIO QUEUE SYSTEM (No Overlapping/Lag) ---
audio_queue = queue.Queue()

def audio_worker():
    """Single dedicated background thread to handle all audio safely"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 165)
        while True:
            message = audio_queue.get()
            if message is None: break
            try:
                engine.say(message)
                engine.runAndWait()
            except Exception as e:
                print(f"Speech Error: {e}")
            finally:
                audio_queue.task_done()
    except Exception as e:
        print(f"Audio Engine Error: {e}")

threading.Thread(target=audio_worker, daemon=True).start()

def speak_alert(message):
    audio_queue.put(message)

# -------------------------------------------------------

class VideoCamera:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.frame_count = 0
        self.load_camera_config()
        
        # 1. Load YOLO Model Safely
        self.model = None
        try:
            if os.path.exists('yolov8n.pt'):
                self.model = YOLO('yolov8n.pt')
        except Exception as e:
            print(f"YOLO load error: {e}")
            
        # 2. Load Face Detection Model Safely (Crash-Proof)
        self.face_cascade = None
        try:
            if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
                cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
                if os.path.exists(cascade_path):
                    self.face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            print(f"Face detection load error (Ignored): {e}")  
            
        self.current_occupancy = 0
        self.tracked_objects = {}
        self.last_alert_time = 0
        
        self.frame = None
        self.grabbed = False
        self.running = True
        
        self.thread = threading.Thread(target=self.update, args=(), daemon=True)
        self.thread.start()

    def load_camera_config(self):
        try:
            self.node = CameraNode.objects.get(id=self.camera_id)
            if str(self.node.rtsp_url).isdigit():
                self.url = int(self.node.rtsp_url)
                self.video = cv2.VideoCapture(self.url, cv2.CAP_DSHOW)
            else:
                self.url = self.node.rtsp_url
                self.video = cv2.VideoCapture(self.url)
            
            self.line_pt1 = (getattr(self.node, 'line_x1', 50), getattr(self.node, 'line_y1', 140))
            self.line_pt2 = (getattr(self.node, 'line_x2', 500), getattr(self.node, 'line_y2', 140))
            
            self.ai_mobile = getattr(self.node, 'enable_mobile_detection', True)
            self.ai_threat = getattr(self.node, 'enable_threat_detection', True)
            self.ai_crowd = getattr(self.node, 'enable_crowd_detection', False)
            self.ai_fence = getattr(self.node, 'enable_fence_alert', True)
            self.ai_face = getattr(self.node, 'enable_face_recognition', True)
            
        except CameraNode.DoesNotExist:
            self.url = 0
            self.video = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            self.line_pt1 = (50, 140)
            self.line_pt2 = (500, 140)
            self.ai_mobile, self.ai_threat, self.ai_face, self.ai_fence = True, True, True, True
            self.ai_crowd = False

        self.video.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def update(self):
        while self.running:
            if self.video.isOpened():
                self.grabbed, self.frame = self.video.read()
            else:
                self.grabbed = False

    def __del__(self):
        self.running = False
        if hasattr(self, 'video') and self.video.isOpened():
            self.video.release()

    def trigger_alarm(self, frame, message, cooldown_seconds=6):
        current_time = time.time()
        if current_time - self.last_alert_time > cooldown_seconds:
            self.last_alert_time = current_time
            os.makedirs("media/alerts", exist_ok=True)
            snapshot_path = f"media/alerts/alarm_{self.camera_id}_{int(current_time)}.jpg"
            cv2.imwrite(snapshot_path, frame)
            cam_name = getattr(self.node, 'name', 'Camera')
            speak_alert(f"{message} at {cam_name}")

    def get_frame(self):
        if not self.grabbed or self.frame is None:
            return None

        # --- DYNAMIC AI REFRESH (Check DB settings every 3 seconds) ---
        if not hasattr(self, 'frame_count'): self.frame_count = 0
        self.frame_count += 1
        if self.frame_count % 60 == 0:
            try:
                self.node.refresh_from_db()
                self.ai_mobile = getattr(self.node, 'enable_mobile_detection', True)
                self.ai_threat = getattr(self.node, 'enable_threat_detection', True)
                self.ai_crowd = getattr(self.node, 'enable_crowd_detection', False)
                self.ai_fence = getattr(self.node, 'enable_fence_alert', True)
                self.ai_face = getattr(self.node, 'enable_face_recognition', True)
            except Exception: pass

        frame = self.frame.copy()

        # Draw Tripwire / Fence Line
        if getattr(self, 'ai_fence', True):
            cv2.line(frame, self.line_pt1, self.line_pt2, (255, 255, 0), 2)

        person_count = 0
        threat_classes = ['knife', 'scissors', 'baseball bat', 'fork']

        # --- YOLO AI DETECTION (Instant & Reliable) ---
        if self.model:
            try:
                # Using standard model inference (no strict tracking dependency)
                results = self.model(frame, conf=0.3, verbose=False)
                for r in results:
                    boxes = r.boxes
                    if boxes is not None and len(boxes) > 0:
                        for box in boxes:
                            coords = box.xyxy[0].cpu().tolist()
                            x1, y1, x2, y2 = map(int, coords)
                            cls_id = int(box.cls[0].item())
                            cls_name = self.model.names[cls_id]
                            
                            # 1. Person Detection (Crowd)
                            if cls_name == 'person':
                                person_count += 1
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)

                            # 2. Mobile / Spying Detection
                            if getattr(self, 'ai_mobile', True) and cls_name == 'cell phone':
                                cv2.putText(frame, "MOBILE DETECTED!", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                                self.trigger_alarm(frame, "Security Warning! Mobile phone detected.")

                            # 3. Threat / Weapon Detection (Knife, etc.)
                            if getattr(self, 'ai_threat', True) and cls_name in threat_classes:
                                cv2.putText(frame, f"THREAT: {cls_name.upper()}!", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                                self.trigger_alarm(frame, f"Emergency Alert! {cls_name} detected.")

            except Exception as e:
                print(f"AI Error: {e}")

        # --- OPENCV FACE DETECTION ---
        if getattr(self, 'ai_face', True) and self.face_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                for (fx, fy, fw, fh) in faces:
                    cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (0, 255, 255), 2)
                    cv2.putText(frame, "FACE DETECTED", (fx, fy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            except Exception:
                pass

        # --- CROWD ALERT (>2 for easy testing, you can change back to >5 later) ---
        if getattr(self, 'ai_crowd', False) and person_count > 2:
            cv2.putText(frame, f"WARNING: CROWD ({person_count} PEOPLE)", (30, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            self.trigger_alarm(frame, "Warning! Crowd gathering detected.", cooldown_seconds=10)

        # UI Stats Overlay on Stream
        cv2.putText(frame, f'PEOPLE IN FRAME: {person_count}', (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cam_display_name = getattr(self.node, 'name', 'Webcam')
        cv2.putText(frame, f'CAMERA: {cam_display_name}', (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return jpeg.tobytes()
def trigger_alarm(self, frame, message, cooldown_seconds=6):
        current_time = time.time()
        if current_time - self.last_alert_time > cooldown_seconds:
            self.last_alert_time = current_time
            os.makedirs("media/alerts", exist_ok=True)
            
            relative_path = f"media/alerts/alarm_{self.camera_id}_{int(current_time)}.jpg"
            cv2.imwrite(relative_path, frame)
            
            cam_name = getattr(self.node, 'name', 'Camera')
            full_msg = f"{message} at {cam_name}"
            
            # 🔊 Voice Alert
            speak_alert(full_msg)
            
            # 💾 Save to Database for AI Analysis Page
            try:
                from cameras.models import AlertLog
                AlertLog.objects.create(
                    camera=self.node,
                    message=full_msg,
                    image_path=relative_path
                )
            except Exception as e:
                print(f"Log Save Error: {e}")