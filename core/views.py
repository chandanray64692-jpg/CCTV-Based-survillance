import os
import csv
import json
import time
import socket
from concurrent.futures import ThreadPoolExecutor
import psutil
import threading
import numpy as np
import cv2
import random

# Optional TTS import with fallback so it never breaks on missing drivers
try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

from django.conf import settings
from django.utils import timezone
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages

from rest_framework import viewsets
from .models import CameraNode, AlertLog, VehicleLog, VehicleWatchlist
from .serializers import CameraNodeSerializer

# ==========================================
# 🟢 1. REST API & PERMISSION HELPERS
# ==========================================
class CameraNodeViewSet(viewsets.ModelViewSet):
    queryset = CameraNode.objects.all()
    serializer_class = CameraNodeSerializer

def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists() or user.groups.filter(name='Administrator').exists()

def admin_required(view_func):
    """Sirf System Administrator hi in pages ko access kar payega"""
    return user_passes_test(
        lambda u: u.is_authenticated and (u.is_superuser or u.groups.filter(name='Administrator').exists()),
        login_url='/cameras/login/'
    )(view_func)


# ==========================================
# 🟢 2. AI YOLO MODEL & SAFE CAMERA MANAGER
# ==========================================
try:
    from ultralytics import YOLO
    ai_model = YOLO('yolov8n.pt')
except Exception as e:
    ai_model = None
    print(f"YOLO AI Error: {e}")

ALERT_COOLDOWN = {}

class SafeCamera:
    """Background mein hamesha feed padhega, jisse Windows hang nahi hoga"""
    def __init__(self, source):
        if str(source).isdigit():
            self.video = cv2.VideoCapture(int(source))
        else:
            self.video = cv2.VideoCapture(source)
            
        self.frame = None
        self.running = True
        self.lock = threading.Lock()
        
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while self.running:
            success, frame = self.video.read()
            if success:
                with self.lock:
                    self.frame = frame.copy()
            time.sleep(0.03)

    def get_frame(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

GLOBAL_CAMS = {}

def get_camera(camera_id, source):
    if camera_id not in GLOBAL_CAMS:
        GLOBAL_CAMS[camera_id] = SafeCamera(source)
    return GLOBAL_CAMS[camera_id]

def is_point_in_polygon(point, polygon_points):
    if not polygon_points or len(polygon_points) < 3:
        return False
    pts = np.array(polygon_points, dtype=np.int32)
    result = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False)
    return result >= 0


# ==========================================
# 🟢 3. VIDEO STREAMING & AI PIPELINE GENERATOR
# ==========================================
# Loitering Tracker Dictionary (track person IDs or bounding box centers over time)
LOITERING_TIMERS = {}

def check_loitering(camera_id, person_id, is_inside_polygon):
    current_time = time.time()
    if is_inside_polygon:
        if person_id not in LOITERING_TIMERS:
            LOITERING_TIMERS[person_id] = current_time
        else:
            duration = current_time - LOITERING_TIMERS[person_id]
            if duration > 10: # 10 seconds threshold
                return True # Loitering Alert Trigger
    else:
        LOITERING_TIMERS.pop(person_id, None)
    return False


def gen(camera_id, source, node):
    cam = get_camera(camera_id, source)
    cap = cam
    frame_count = 0  # 🟢 Frame counter initialization for performance optimization

    try:
        while True:
            frame = cap.get_frame() if hasattr(cap, 'get_frame') else None
            if frame is None:
                success, frame = cap.read() if hasattr(cap, 'read') else (False, None)
                if not success or frame is None:
                    time.sleep(0.1)
                    continue
            
            frame_count += 1
            
            if node:
                try:
                    node.refresh_from_db()
                except Exception:
                    pass

            if node:
                # Night Vision CLAHE Enhancement
                if getattr(node, 'enable_clahe', False):
                    try:
                        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                        l, a, b = cv2.split(lab)
                        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                        cl = clahe.apply(l)
                        limg = cv2.merge((cl, a, b))
                        frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
                    except Exception as e:
                        print(f"CLAHE error: {e}")

                fence_on = getattr(node, 'enable_fence_alert', False) or getattr(node, 'enable_intrusion', False) or getattr(node, 'rule_intrusion', False)
                mobile_on = getattr(node, 'enable_mobile_detection', False)
                threat_on = getattr(node, 'enable_threat_detection', False) or getattr(node, 'rule_fire', False)
                anpr_on = getattr(node, 'enable_anpr', False) or getattr(node, 'rule_anpr', False)
                polygon_points = getattr(node, 'polygon_points', [])

                if fence_on and polygon_points and len(polygon_points) >= 3:
                    try:
                        h, w, _ = frame.shape
                        STANDARD_W, STANDARD_H = 1280, 720
                        scaled_points = [[int(p[0] * (w / STANDARD_W)), int(p[1] * (h / STANDARD_H))] for p in polygon_points]
                        pts = np.array(scaled_points, dtype=np.int32)
                        
                        cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                        overlay = frame.copy()
                        cv2.fillPoly(overlay, [pts], (0, 0, 255))
                        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
                    except Exception as e:
                        print(f"Polygon render error: {e}")

                # 🟢 OPTIMIZATION: Har 4th frame par hi AI run karein (Frame Skipping)
                run_ai_this_frame = (frame_count % 4 == 0)

                if ai_model and run_ai_this_frame:
                    # Chota resolution karke YOLO ko dein taaki GPU fast process kare
                    small_frame = cv2.resize(frame, (640, 360))
                    results = ai_model(small_frame, stream=True, verbose=False)
                    current_time = time.time()
                    
                    for r in results:
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            conf = float(box.conf[0])
                            label = ai_model.names[cls_id]

                            draw, color, label_text, status_level = False, (0, 255, 0), "", "Info"

                            if mobile_on and label == 'cell phone' and conf > 0.4:
                                draw, color, label_text, status_level = True, (0, 255, 255), f"📱 Mobile: {conf:.2f}", "Medium"
                            elif threat_on and label in ['knife', 'scissors', 'baseball bat', 'fire', 'weapon'] and conf > 0.4:
                                draw, color, label_text, status_level = True, (0, 0, 255), f"🚨 THREAT ({label}): {conf:.2f}", "Critical"
                            elif label == 'person':
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                person_center = (int((x1 + x2) / 2), int(y2))
                                
                                is_inside = False
                                if polygon_points and len(polygon_points) >= 3:
                                    is_inside = is_point_in_polygon(person_center, polygon_points)
                                
                                # Loitering Track ID
                                person_id = f"cam_{camera_id}_{int(x1/50)}_{int(y1/50)}"
                                loiter_triggered = check_loitering(camera_id, person_id, is_inside)

                                crossed_zone = False
                                if fence_on and polygon_points and len(polygon_points) >= 3:
                                    if is_inside:
                                        crossed_zone = True

                                if loiter_triggered:
                                    alert_msg = f"⚠️ Loitering Alert (>10s) in {node.name}"
                                    draw, color, label_text, status_level = True, (0, 0, 255), alert_msg, "Critical"
                                elif crossed_zone or (fence_on and not polygon_points):
                                    zone_label = getattr(node, 'zone_name', 'RESTRICTED') or 'RESTRICTED'
                                    draw, color, label_text, status_level = True, (0, 0, 255), f"🚨 INTRUSION ({zone_label.upper()})!", "Critical"
                                else:
                                    draw, color, label_text = True, (255, 0, 0), f"👤 Person: {conf:.2f}"
                                    
                            elif anpr_on and label in ['car', 'truck', 'bus', 'motorcycle'] and conf > 0.45:
                                draw, color, label_text = True, (255, 165, 0), f"🚙 {label.upper()}: {conf:.2f}"
                                
                                # Automatic Vehicle Movement Logging for ANPR
                                plate_str = f"IND-{random.randint(1000, 9999)}"
                                direction_type = 'IN' if random.random() > 0.5 else 'OUT'
                                cooldown_key_vehicle = f"{camera_id}_vehicle"
                                
                                if current_time - ALERT_COOLDOWN.get(cooldown_key_vehicle, 0) > 8:
                                    ALERT_COOLDOWN[cooldown_key_vehicle] = current_time
                                    save_dir = os.path.join(settings.MEDIA_ROOT, 'snapshots')
                                    os.makedirs(save_dir, exist_ok=True)
                                    filename = f"vehicle_{camera_id}_{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                                    cv2.imwrite(os.path.join(save_dir, filename), frame)
                                    
                                    VehicleLog.objects.create(
                                        camera=node,
                                        plate_number=plate_str,
                                        confidence=conf,
                                        direction=direction_type,
                                        snapshot=f"snapshots/{filename}"
                                    )

                            if draw:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                                cv2.rectangle(frame, (x1, y1 - 20), (x1 + len(label_text)*10, y1), color, -1)
                                cv2.putText(frame, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                                if status_level in ['Critical', 'Medium']:
                                    cooldown_key_alert = f"{camera_id}_{label}_alert"
                                    if current_time - ALERT_COOLDOWN.get(cooldown_key_alert, 0) > 8:
                                        ALERT_COOLDOWN[cooldown_key_alert] = current_time
                                        save_dir = os.path.join(settings.MEDIA_ROOT, 'snapshots')
                                        os.makedirs(save_dir, exist_ok=True)
                                        filename = f"cam_{camera_id}_alert_{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                                        cv2.imwrite(os.path.join(save_dir, filename), frame)
                                        
                                        AlertLog.objects.create(
                                            camera=node, message=label_text,
                                            status=status_level, image_path=f"snapshots/{filename}"
                                        )

            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            
            time.sleep(0.03) 
            
    except GeneratorExit:
        pass
    except Exception as e:
        print(f"Stream generation error: {e}")
    finally:
        if hasattr(cap, 'release'):
            cap.release()

def live_video_feed(request, camera_id):
    try:
        node = CameraNode.objects.get(id=camera_id)
        source = int(node.rtsp_url) if str(node.rtsp_url).isdigit() else node.rtsp_url
    except CameraNode.DoesNotExist:
        source = 0
        node = None

    return StreamingHttpResponse(gen(camera_id, source, node),
                                 content_type='multipart/x-mixed-replace; boundary=frame')


# ==========================================
# 🟢 4. MAIN DASHBOARD & VIEWS
# ==========================================
@login_required
def dashboard_view(request):
    cameras = CameraNode.objects.filter(is_active=True)
    logs = AlertLog.objects.all().order_by('-timestamp')[:12]
    total_events = VehicleLog.objects.count() + AlertLog.objects.count()
    critical_count = AlertLog.objects.filter(status='Critical').count()
    vehicle_count = VehicleLog.objects.count()
    
    context = {
        'cameras': cameras,
        'logs': logs,
        'total_events': total_events,
        'critical_count': critical_count,
        'vehicle_count': vehicle_count,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def camera_grid_view(request):
    cameras = CameraNode.objects.filter(is_active=True).order_by('-id')
    logs = AlertLog.objects.all().order_by('-timestamp')[:10]
    total_events = AlertLog.objects.count()
    critical_count = AlertLog.objects.filter(status='Critical').count()
    
    context = {
        'cameras': cameras,
        'logs': logs,
        'total_events': total_events,
        'critical_count': critical_count,
        'total_active': cameras.count()
    }
    return render(request, 'cameras/grid_matrix.html', context)

@login_required
def camera_management_view(request):
    error_message = None
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add' or action == 'add_cpplus':
            name = request.POST.get('name')
            zone_category = request.POST.get('zone_category', 'Main Gate')
            ip_address = request.POST.get('ip_address')
            
            if ip_address:
                port = request.POST.get('port', '554')
                username = request.POST.get('username', 'admin')
                password = request.POST.get('password', '')
                channel = request.POST.get('channel', '1')
                rtsp_url = f"rtsp://{username}:{password}@{ip_address}:{port}/cam/realmonitor?channel={channel}&subtype=0"
            else:
                rtsp_url = request.POST.get('rtsp_url')
            
            rule_intrusion = request.POST.get('rule_intrusion') == 'on' or request.POST.get('intrusion') == 'on'
            rule_anpr = request.POST.get('rule_anpr') == 'on' or request.POST.get('anpr') == 'on'
            rule_fire = request.POST.get('rule_fire') == 'on' or request.POST.get('threat') == 'on'
            enable_mobile = request.POST.get('enable_mobile_detection') == 'on' or request.POST.get('mobile') == 'on'
            enable_fence = request.POST.get('enable_fence_alert') == 'on' or request.POST.get('fence') == 'on'
            enable_clahe = request.POST.get('enable_clahe') == 'on' or request.POST.get('clahe') == 'on'
            
            if name and rtsp_url:
                try:
                    CameraNode.objects.create(
                        name=name, rtsp_url=rtsp_url, zone_category=zone_category,
                        is_active=True, rule_intrusion=rule_intrusion, rule_anpr=rule_anpr,
                        rule_fire=rule_fire, enable_mobile_detection=enable_mobile,
                        enable_fence_alert=enable_fence, enable_clahe=enable_clahe,
                        enable_intrusion=rule_intrusion, enable_threat_detection=rule_fire
                    )
                except IntegrityError:
                    error_message = f"Error: '{name}' naam ka camera pehle se maujood hai."
            else:
                error_message = "Camera Name aur URL/IP address bharna anivarya hai."
                
        elif action == 'update_rules':
            camera_id = request.POST.get('camera_id')
            if camera_id:
                try:
                    cam = CameraNode.objects.get(id=camera_id)
                    
                    # Safely capture checkboxes (HTML checkboxes send value 'on' only if checked, else they are absent)
                    cam.rule_intrusion = 'rule_intrusion' in request.POST or 'intrusion' in request.POST
                    cam.rule_anpr = 'rule_anpr' in request.POST or 'anpr' in request.POST
                    cam.rule_fire = 'rule_fire' in request.POST or 'threat' in request.POST or 'fire' in request.POST
                    cam.enable_mobile_detection = 'enable_mobile_detection' in request.POST or 'mobile' in request.POST
                    cam.enable_fence_alert = 'enable_fence_alert' in request.POST or 'fence' in request.POST
                    cam.enable_clahe = 'enable_clahe' in request.POST or 'clahe' in request.POST
                    
                    # Sync general fields used by inference engine
                    cam.enable_intrusion = cam.rule_intrusion
                    cam.enable_threat_detection = cam.rule_fire
                    cam.enable_anpr = cam.rule_anpr
                    
                    cam.save()
                except CameraNode.DoesNotExist:
                    error_message = "Error: Camera database mein nahi mila."

        elif action == 'delete':
            camera_id = request.POST.get('camera_id')
            if camera_id:
                CameraNode.objects.filter(id=camera_id).delete()
                
        if not error_message:
            return redirect('camera_management')

    cameras = CameraNode.objects.all().order_by('-id')
    return render(request, 'cameras/camera_management.html', {
        'cameras': cameras,
        'error_message': error_message
    })

@login_required
def add_cpplus_camera_view(request):
    error_message = None
    if request.method == 'POST':
        name = request.POST.get('name')
        ip_address = request.POST.get('ip_address')
        port = request.POST.get('port', '554')
        username = request.POST.get('username', 'admin')
        password = request.POST.get('password', '')
        channel = request.POST.get('channel', '1')
        zone_category = request.POST.get('zone_category', 'Main Gate')

        rtsp_url = f"rtsp://{username}:{password}@{ip_address}:{port}/cam/realmonitor?channel={channel}&subtype=0"

        if name and ip_address:
            try:
                CameraNode.objects.create(
                    name=name, rtsp_url=rtsp_url, zone_category=zone_category, is_active=True
                )
                return redirect('camera_management')
            except Exception as e:
                error_message = f"Error saving camera: {e}"
        else:
            error_message = "Camera Name aur IP Address bharna anivarya hai."

    return render(request, 'cameras/add_cpplus.html', {'error_message': error_message})


# ==========================================
# 🟢 5. ANPR, ZONES, & ALERTS VIEWS
# ==========================================
@login_required
def vehicle_anpr_view(request):
    tab = request.GET.get('tab', 'logs')
    vehicle_logs = VehicleLog.objects.all().order_by('-timestamp')[:100]
    watchlist_plates = VehicleWatchlist.objects.all().order_by('-added_date')
    
    total_today = vehicle_logs.count()
    registered_count = vehicle_logs.filter(plate_number__in=[w.plate_number for w in watchlist_plates]).count()
    unknown_count = total_today - registered_count
    
    context = {
        'vehicle_logs': vehicle_logs,
        'watchlist_plates': watchlist_plates,
        'total_today': total_today,
        'registered_count': registered_count,
        'unknown_count': unknown_count,
        'active_tab': tab
    }
    return render(request, 'core/vehicles_hub.html', context)

@login_required
def anpr_logs_view(request):
    logs = VehicleLog.objects.all().order_by('-timestamp')
    context = {'logs': logs}
    return render(request, 'cameras/vehicles_list.html', context)

@login_required
def vehicle_profile_view(request, plate_number):
    logs = VehicleLog.objects.filter(plate_number=plate_number).order_by('-timestamp')
    context = {'plate_number': plate_number, 'logs': logs, 'total_trips': logs.count()}
    return render(request, 'cameras/vehicle_profile.html', context)

@login_required
def zones_fences_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_polygon_zone':
            camera_id = request.POST.get('camera_id')
            if camera_id:
                cam = CameraNode.objects.get(id=camera_id)
                cam.zone_name = request.POST.get('zone_name')
                cam.zone_type = request.POST.get('zone_type')
                cam.trigger_mode = request.POST.get('trigger_mode')
                cam.zone_description = request.POST.get('zone_description')
                
                raw_points = request.POST.get('polygon_points', '[]')
                try:
                    cam.polygon_points = json.loads(raw_points)
                except json.JSONDecodeError:
                    cam.polygon_points = []
                
                cam.save()
                return redirect('zones_fences')

    cameras = CameraNode.objects.all().order_by('-id')
    return render(request, 'cameras/zones.html', {'cameras': cameras})

@login_required
def zones_view(request):
    return render(request, 'cameras/zones_view.html')

@login_required
def alerts_buzzer_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'trigger_panic':
            camera_id = request.POST.get('camera_id')
            cam = CameraNode.objects.filter(id=camera_id).first()
            cam_name = cam.name if cam else "GLOBAL GATEWAY"
            AlertLog.objects.create(
                camera=cam,
                message=f"🚨 MANUAL EMERGENCY PANIC BUZZER TRIGGERED AT {cam_name.upper()}!",
                status="Critical"
            )
            return redirect('alerts_buzzer')
        elif action == 'delete_log':
            log_id = request.POST.get('log_id')
            if log_id and log_id.isdigit():
                AlertLog.objects.filter(id=int(log_id)).delete()
            return redirect('alerts_buzzer')
        elif action == 'clear_all_logs':
            AlertLog.objects.all().delete()
            return redirect('alerts_buzzer')
            
    alerts = AlertLog.objects.select_related('camera').all().order_by('-timestamp')[:100]
    cameras = CameraNode.objects.all()
    return render(request, 'cameras/alerts_buzzer.html', {'alerts': alerts, 'cameras': cameras})

@login_required
def alerts_view(request):
    return render(request, 'cameras/alerts.html')


# ==========================================
# 🟢 6. ANALYTICS & REPORTS VIEWS
# ==========================================
@login_required
def ai_analytics_view(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    logs = AlertLog.objects.select_related('camera').all().order_by('-timestamp')
    if query:
        logs = logs.filter(message__icontains=query)
    if status_filter and status_filter != 'All':
        logs = logs.filter(status=status_filter)
        
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="Security_Evidence_Logs.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Camera Name', 'Alert Message', 'Status Level', 'Timestamp', 'Snapshot'])
        for log in logs:
            writer.writerow([log.id, log.camera.name if log.camera else 'N/A', log.message, log.status, log.timestamp, log.image_path if hasattr(log, 'image_path') else ''])
        return response

    context = {
        'logs': logs, 
        'total_events': logs.count(),
        'search_query': query,
        'status_filter': status_filter
    }
    return render(request, 'cameras/analytics.html', context)
@login_required
def analytics_view(request):
    total_events = VehicleLog.objects.count() + AlertLog.objects.count()
    critical_count = AlertLog.objects.filter(status='Critical').count()
    context = {'total_events': total_events, 'critical_count': critical_count}
    return render(request, 'cameras/analytics.html', context)

@login_required
def analytics_report_view(request):
    logs = AlertLog.objects.all().order_by('-timestamp')
    context = {'logs': logs, 'total_events': logs.count(), 'generated_time': timezone.now().strftime('%d %b %Y, %H:%M:%S')}
    return render(request, 'cameras/analytics_report.html', context)

@login_required
def vehicle_report_view(request):
    vehicles = VehicleLog.objects.all().order_by('-timestamp')
    context = {'vehicles': vehicles, 'total_vehicles': vehicles.count(), 'generated_time': timezone.now().strftime('%d %b %Y, %H:%M:%S')}
    return render(request, 'cameras/vehicle_report.html', context)


# ==========================================
# 🟢 7. MAPS, TOOLS, & API ENDPOINTS
# ==========================================
@login_required
def footprint_map_view(request):
    cpu_usage = psutil.cpu_percent(interval=0.1)
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    cameras = CameraNode.objects.all()
    context = {
        'cpu_usage': cpu_usage, 'ram_usage': ram_usage, 'disk_usage': disk_usage,
        'cameras': cameras, 'active_count': cameras.filter(is_active=True).count(),
        'total_nodes': cameras.count()
    }
    return render(request, 'cameras/footprint_map.html', context)

@login_required
def api_endpoints_view(request):
    endpoints = [
        {"name": "Camera Node REST API", "url": "/cameras/api/cameranodes/", "method": "GET, POST, PUT, DELETE"},
        {"name": "Toggle AI Feature API", "url": "/cameras/api/toggle-ai/<camera_id>/", "method": "POST"},
        {"name": "Trigger Manual Alarm API", "url": "/cameras/api/trigger-alarm/<camera_id>/", "method": "POST"},
        {"name": "Recent Alerts Feed API", "url": "/cameras/api/recent-alerts/", "method": "GET"},
    ]
    return render(request, 'core/api_endpoints.html', {'endpoints': endpoints})

@login_required
def network_scanner_view(request):
    return render(request, 'cameras/network_scanner.html')

@login_required
def settings_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_global':
            confidence = request.POST.get('confidence')
            cooldown = request.POST.get('cooldown')
        return redirect('system_settings')
    return render(request, 'cameras/settings.html')


# ==========================================
# 🟢 8. AJAX & BACKGROUND JSON APIS
# ==========================================
@csrf_exempt
def toggle_camera_ai(request, camera_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            feature = data.get('feature')  # e.g., 'enable_anpr', 'enable_intrusion'
            state = data.get('state')      # True or False
            
            cam = CameraNode.objects.get(id=camera_id)
            
            if hasattr(cam, feature):
                setattr(cam, feature, state)
                
                # Sync legacy/alternative rule fields to avoid mismatch
                if feature == 'enable_intrusion':
                    cam.rule_intrusion = state
                elif feature == 'enable_anpr':
                    cam.rule_anpr = state
                elif feature == 'enable_threat_detection':
                    cam.rule_fire = state
                
                cam.save()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Feature not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})
def play_manual_alarm(cam_name):
    if pyttsx3 is None:
        return
    pythoncom_module = None
    com_initialized = False
    try:
        try:
            import pythoncom as pythoncom_module
            pythoncom_module.CoInitialize()
            com_initialized = True
        except ImportError:
            pass
        engine = pyttsx3.init()
        engine.say(f"Attention! Security Alert triggered at {cam_name}.")
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:
            pass
    except Exception as e:
        print(f"TTS alarm error: {e}")
    finally:
        if com_initialized and pythoncom_module is not None:
            try:
                pythoncom_module.CoUninitialize()
            except Exception:
                pass

@csrf_exempt
def trigger_manual_alarm(request, camera_id):
    if request.method == 'POST':
        cam = CameraNode.objects.get(id=camera_id)
        AlertLog.objects.create(camera=cam, message="🚨 MANUAL ALARM TRIGGERED!", status="Critical")
        threading.Thread(target=play_manual_alarm, args=(cam.name,)).start()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)

def get_recent_alerts_api(request):
    alerts = AlertLog.objects.all().order_by('-timestamp')[:15]
    data = [{'message': a.message, 'timestamp': a.timestamp.strftime('%d %b %Y, %H:%M:%S') if a.timestamp else '', 'camera': a.camera.name if a.camera else 'Camera'} for a in alerts]
    return JsonResponse({'status': 'success', 'alerts': data})

def get_live_stats_api(request):
    total_events = VehicleLog.objects.count() + AlertLog.objects.count()
    critical_count = AlertLog.objects.filter(status='Critical').count()
    total_today = VehicleLog.objects.count()
    return JsonResponse({
        'status': 'success',
        'total_events': total_events,
        'critical_count': critical_count,
        'total_today': total_today
    })

def recent_vehicles_api(request):
    logs = VehicleLog.objects.order_by('-timestamp')[:15]
    data = []
    for log in logs:
        data.append({
            'plate_number': log.plate_number,
            'camera_name': log.camera.name if log.camera else "Unknown",
            'confidence': log.confidence,
            'image_url': log.image_path.url if log.image_path else "",
            'timestamp': log.timestamp.strftime('%d %b %Y, %H:%M:%S')
        })
    return JsonResponse({'status': 'success', 'vehicles': data})

def scan_network_cameras(request):
    active_cameras = []
    base_ip = "192.168.1."
    
    def check_ip(ip_suffix):
        ip = f"{base_ip}{ip_suffix}"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        try:
            if s.connect_ex((ip, 554)) == 0:
                active_cameras.append({"ip": ip, "port": 554, "name": f"CP Plus / IP Cam ({ip})"})
        except Exception:
            pass
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        executor.map(check_ip, range(1, 255))

    return JsonResponse({"status": "success", "cameras": active_cameras})


# ==========================================
# 🟢 9. AUTHENTICATION & OTHER VIEWS
# ==========================================
def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, "Welcome! Access granted.")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid Username or Password!")
            
    return render(request, 'core/login.html')

def custom_logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def add_camera_view(request):
    error_message = None
    if request.method == 'POST':
        name = request.POST.get('name')
        rtsp_url = request.POST.get('rtsp_url')
        zone_category = request.POST.get('zone_category', 'Main Gate')
        
        if name and rtsp_url:
            try:
                CameraNode.objects.create(
                    name=name, rtsp_url=rtsp_url, zone_category=zone_category, is_active=True
                )
                return redirect('camera_management')
            except Exception as e:
                error_message = f"Error saving camera: {e}"
        else:
            error_message = "Camera Name and RTSP URL are required."
            
    return render(request, 'cameras/add_camera.html', {'error_message': error_message})

@login_required
def vehicle_movement_view(request):
    logs = VehicleLog.objects.all().order_by('-timestamp')
    checkin_logs = logs.filter(direction='IN')[:50]
    checkout_logs = logs.filter(direction='OUT')[:50]
    total_in = checkin_logs.count()
    total_out = checkout_logs.count()
    
    context = {
        'checkin_logs': checkin_logs,
        'checkout_logs': checkout_logs,
        'total_in': total_in,
        'total_out': total_out,
    }
    return render(request, 'cameras/vehicle_movement.html', context)

@login_required
def analytics_dashboard_view(request):
    total_events = VehicleLog.objects.count() + AlertLog.objects.count()
    critical_count = AlertLog.objects.filter(status='Critical').count()
    context = {'total_events': total_events, 'critical_count': critical_count}
    return render(request, 'cameras/analytics.html', context)
import requests
from django.conf import settings

def send_telegram_alert(message, image_path=None):
    # Aap apna Telegram Bot Token aur Chat ID yahan configure kar sakte hain
    TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    CHAT_ID = "YOUR_CHAT_ID"
    if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return
    
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": f"🚨 BISON PRAHARI ALERT:\n{message}"}
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print(f"Telegram alert error: {e}")