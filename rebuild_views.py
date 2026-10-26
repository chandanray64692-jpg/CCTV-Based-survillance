import re

path = 'core/views.py'
try:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 1. Sabhi weird whitespace aur tabs ko standardize karo
    content = content.replace('\r\n', '\n').replace('\t', '    ')
    
    # 2. play_manual_alarm function aur uske aas-paas ke indentation blocks ko strict 4-space par lock karo
    # Let's find where play_manual_alarm starts and clean it up completely
    if 'def play_manual_alarm' in content:
        parts = content.split('def play_manual_alarm')
        head = parts[0]
        tail = parts[1]
        
        # Next function tak ka hissa kaat kar naya clean function lagao
        tail_parts = tail.split('def custom_login_view')
        remainder = 'def custom_login_view' + tail_parts[1] if len(tail_parts) > 1 else ''
        
        clean_alarm_code = '''def play_manual_alarm(cam_name):
    try:
        import pythoncom
        pythoncom.CoInitialize()
        if pyttsx3:
            engine = pyttsx3.init()
            engine.say("Attention! Security Alert triggered at " + cam_name)
            engine.runAndWait()
    except Exception:
        pass

@csrf_exempt
def trigger_manual_alarm(request, camera_id):
    if request.method == 'POST':
        cam = CameraNode.objects.get(id=camera_id)
        AlertLog.objects.create(camera=cam, message="?? MANUAL ALARM TRIGGERED!", status="Critical")
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

'''
        final_code = head + '\n\n' + clean_alarm_code + '\n\n' + remainder
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(final_code)
        print('SUCCESS: views.py successfully rewritten with clean line breaks!')
except Exception as e:
    print(f'Error: {e}')
