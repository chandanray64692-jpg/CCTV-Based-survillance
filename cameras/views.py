import os
import csv
import json
import time
import socket
import psutil
import threading
import numpy as np
import cv2

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
from .anpr_engine import process_anpr_frame

class CameraNodeViewSet(viewsets.ModelViewSet):
    queryset = CameraNode.objects.all()
    serializer_class = CameraNodeSerializer

def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists() or user.groups.filter(name='Administrator').exists()

def admin_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and (u.is_superuser or u.groups.filter(name='Administrator').exists()),
        login_url='/cameras/login/'
    )(view_func)

try:
    from ultralytics import YOLO
    ai_model = YOLO('yolov8n.pt')
except Exception as e:
    ai_model = None
    print(f'YOLO AI Error: {e}')

ALERT_COOLDOWN = {}

class SafeCamera:
    def __init__(self, source):
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
        if str(source).isdigit():
            self.video = cv2.VideoCapture(int(source))
        else:
            self.video = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
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
    return cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False) >= 0

def gen(camera_id, source, node):
    cam = get_camera(camera_id, source)
    cap = cam
    frame_count = 0
    fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)

    try:
        while True:
            frame = cap.get_frame() if hasattr(cap, 'get_frame') else None
            if frame is None:
                success, frame = cap.read() if hasattr(cap, 'read') else (False, None)
                if not success or frame is None:
                    time.sleep(0.1)
                    continue
            
            if node:
                try:
                    node.refresh_from_db()
                except Exception:
                    pass

            frame_count += 1
            has_motion = False
            
            # 1. Light-weight Motion Check
            if frame_count % 5 == 0:
                small_gray = cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY)
                fgmask = fgbg.apply(small_gray)
                if cv2.countNonZero(fgmask) > 150:
                    has_motion = True

            # 2. Polygon Zone Rendering on frame
            polygon_points = getattr(node, 'polygon_points', []) if node else []
            if node and getattr(node, 'enable_fence_alert', False) and polygon_points and len(polygon_points) >= 3:
                try:
                    h, w, _ = frame.shape
                    scaled_points = [[int(p[0] * (w / 1280)), int(p[1] * (h / 720))] for p in polygon_points]
                    pts = np.array(scaled_points, dtype=np.int32)
                    cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                except Exception:
                    pass

            # 3. YOLO AI Execution on Motion Trigger
            if ai_model and node and has_motion and (frame_count % 15 == 0):
                fence_on = getattr(node, 'enable_fence_alert', False)
                mobile_on = getattr(node, 'enable_mobile_detection', False)
                threat_on = getattr(node, 'enable_threat_detection', False)
                anpr_on = getattr(node, 'enable_anpr', False)

                results = ai_model(frame, stream=True, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = ai_model.names[cls_id]
                        draw, color, label_text, status_level = False, (0, 255, 0), '', 'Info'

                        if mobile_on and label == 'cell phone' and conf > 0.4:
                            draw, color, label_text, status_level = True, (0, 255, 255), f'📱 Mobile: {conf:.2f}', 'Medium'
                        elif threat_on and label in ['knife', 'scissors', 'baseball bat'] and conf > 0.4:
                            draw, color, label_text, status_level = True, (0, 0, 255), f'🚨 THREAT ({label}): {conf:.2f}', 'Critical'
                        elif label == 'person':
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            crossed = False
                            if fence_on and polygon_points and len(polygon_points) >= 3:
                                if is_point_in_polygon((int((x1 + x2) / 2), int(y2)), polygon_points):
                                    crossed = True
                            if crossed:
                                draw, color, label_text, status_level = True, (0, 0, 255), '🚨 INTRUSION!', 'Critical'
                            else:
                                draw, color, label_text = True, (255, 0, 0), f'👤 Person: {conf:.2f}'

                        if draw:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(frame, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

                            if status_level != 'Info':
                                now = time.time()
                                key = f'{camera_id}_{label}_alert'
                                if now - ALERT_COOLDOWN.get(key, 0) > 10:
                                    ALERT_COOLDOWN[key] = now
                                    save_dir = os.path.join(settings.MEDIA_ROOT, 'snapshots')
                                    os.makedirs(save_dir, exist_ok=True)
                                    fname = f'cam_{camera_id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg'
                                    cv2.imwrite(os.path.join(save_dir, fname), frame)
                                    AlertLog.objects.create(camera=node, message=label_text, status=status_level, image_path=f'snapshots/{fname}')

            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            time.sleep(0.04)
    except GeneratorExit:
        pass
    except Exception as e:
        print(f'Stream error: {e}')
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
    return StreamingHttpResponse(gen(camera_id, source, node), content_type='multipart/x-mixed-replace; boundary=frame')

@login_required
def dashboard_view(request):
    return render(request, 'core/dashboard.html', {'cameras': CameraNode.objects.filter(is_active=True), 'logs': AlertLog.objects.all().order_by('-timestamp')[:12]})

@login_required
def camera_grid_view(request):
    return render(request, 'cameras/grid_matrix.html', {'cameras': CameraNode.objects.filter(is_active=True)})

@login_required
def camera_management_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add' or action == 'add_cpplus':
            name = request.POST.get('name')
            ip = request.POST.get('ip_address')
            rtsp = request.POST.get('rtsp_url') or f'rtsp://admin:{request.POST.get('password', '')}@{ip}:554/cam/realmonitor?channel=1&subtype=0'
            if name and (ip or rtsp):
                CameraNode.objects.create(name=name, rtsp_url=rtsp, is_active=True)
        elif action == 'delete':
            CameraNode.objects.filter(id=request.POST.get('camera_id')).delete()
        return redirect('camera_management')
    return render(request, 'cameras/camera_management.html', {'cameras': CameraNode.objects.all()})

@login_required
def add_cpplus_camera_view(request):
    return render(request, 'cameras/add_cpplus.html')

@login_required
def vehicle_anpr_view(request):
    return render(request, 'cameras/vehicle_anpr.html', {'vehicles': VehicleLog.objects.all()[:100], 'watchlist': VehicleWatchlist.objects.all()})

@login_required
def anpr_logs_view(request):
    return render(request, 'cameras/vehicles_list.html', {'logs': VehicleLog.objects.all()})

@login_required
def vehicle_profile_view(request, plate_number):
    return render(request, 'cameras/vehicle_profile.html', {'plate_number': plate_number, 'logs': VehicleLog.objects.filter(plate_number=plate_number)})

@login_required
def zones_fences_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'update_polygon_zone':
        cam = CameraNode.objects.get(id=request.POST.get('camera_id'))
        cam.zone_name = request.POST.get('zone_name')
        try:
            cam.polygon_points = json.loads(request.POST.get('polygon_points', '[]'))
        except:
            cam.polygon_points = []
        cam.save()
        return redirect('zones_fences')
    return render(request, 'cameras/zones.html', {'cameras': CameraNode.objects.all()})

@login_required
def zones_view(request):
    return render(request, 'cameras/zones_view.html')

@login_required
def alerts_buzzer_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'trigger_panic':
            AlertLog.objects.create(message='🚨 MANUAL EMERGENCY PANIC TRIGGERED!', status='Critical')
        elif action == 'clear_all_logs':
            AlertLog.objects.all().delete()
        return redirect('alerts_buzzer')
    return render(request, 'cameras/alerts_buzzer.html', {'alerts': AlertLog.objects.all()[:100], 'cameras': CameraNode.objects.all()})

@login_required
def alerts_view(request):
    return render(request, 'cameras/alerts.html')

@login_required
def ai_analytics_view(request):
    logs = AlertLog.objects.all().order_by('-timestamp')
    return render(request, 'cameras/analytics.html', {'logs': logs})

@login_required
def analytics_view(request):
    return render(request, 'cameras/analytics.html')

@login_required
def analytics_report_view(request):
    return render(request, 'cameras/analytics_report.html', {'logs': AlertLog.objects.all()})

@login_required
def vehicle_report_view(request):
    return render(request, 'cameras/vehicle_report.html', {'vehicles': VehicleLog.objects.all()})

@login_required
def footprint_map_view(request):
    return render(request, 'cameras/footprint_map.html', {'cameras': CameraNode.objects.all()})

@login_required
def api_endpoints_view(request):
    return render(request, 'core/api_endpoints.html')

@login_required
def network_scanner_view(request):
    return render(request, 'cameras/network_scanner.html')

@login_required
def settings_view(request):
    return render(request, 'cameras/settings.html')

@csrf_exempt
def toggle_camera_ai(request, camera_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        cam = CameraNode.objects.get(id=camera_id)
        setattr(cam, data.get('feature'), data.get('state'))
        cam.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
def trigger_manual_alarm(request, camera_id):
    if request.method == 'POST':
        cam = CameraNode.objects.filter(id=camera_id).first()
        AlertLog.objects.create(camera=cam, message='🚨 MANUAL ALARM TRIGGERED!', status='Critical')
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

def get_recent_alerts_api(request):
    alerts = AlertLog.objects.all().order_by('-timestamp')[:15]
    data = [{'message': a.message, 'timestamp': a.timestamp.strftime('%d %b %Y, %H:%M:%S') if a.timestamp else ''} for a in alerts]
    return JsonResponse({'status': 'success', 'alerts': data})

def scan_network_cameras(request):
    return JsonResponse({'status': 'success', 'cameras': []})

def custom_login_view(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            login(request, user)
            return redirect('dashboard')
    return render(request, 'core/login.html')

def custom_logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def add_camera_view(request):
    return render(request, 'cameras/add_camera.html')

@login_required
def vehicle_movement_view(request):
    return render(request, 'cameras/vehicle_movement.html', {'check_in_logs': VehicleLog.objects.filter(direction='IN'), 'check_out_logs': VehicleLog.objects.filter(direction='OUT')})

from django.shortcuts import get_object_or_404, redirect
from core.models import CameraNode

def save_camera_rules(request, camera_id):
    if request.method == 'POST':
        camera = get_object_or_404(CameraNode, id=camera_id)
        
        # Capture task states from checkboxes
        camera.enable_anpr = 'anpr' in request.POST or 'enable_anpr' in request.POST
        camera.enable_intrusion = 'intrusion' in request.POST or 'enable_intrusion' in request.POST
        camera.enable_fence = 'fence' in request.POST or 'enable_fence' in request.POST
        camera.enable_mobile_detection = 'mobile' in request.POST or 'enable_mobile_detection' in request.POST
        camera.enable_threat_detection = 'threat' in request.POST or 'enable_threat_detection' in request.POST
        camera.enable_crowd = 'crowd' in request.POST or 'enable_crowd' in request.POST
        
        camera.save()
        return redirect('camera_management')

from django.shortcuts import get_object_or_404, redirect
from core.models import CameraNode

def save_camera_rules_view(request, camera_id):
    if request.method == 'POST':
        camera = get_object_or_404(CameraNode, id=camera_id)
        
        # Capture checkbox flags accurately from POST request
        camera.enable_anpr = request.POST.get('anpr') == 'on' or request.POST.get('enable_anpr') == 'on'
        camera.enable_intrusion = request.POST.get('intrusion') == 'on' or request.POST.get('enable_intrusion') == 'on'
        camera.enable_fence = camera.enable_intrusion or request.POST.get('fence') == 'on'
        camera.enable_mobile_detection = request.POST.get('mobile') == 'on' or request.POST.get('enable_mobile_detection') == 'on'
        camera.enable_threat_detection = request.POST.get('threat') == 'on' or request.POST.get('enable_threat_detection') == 'on'
        camera.enable_crowd = request.POST.get('crowd') == 'on' or request.POST.get('enable_crowd') == 'on'
        
        camera.save()
        return redirect('camera_management')