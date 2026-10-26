path = 'core/views.py'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1. Sabhi tabs ko spaces mein badal do taaki mixed indentation ka namo-nishan na rahe
content = content.replace('\t', '    ')

# 2. play_manual_alarm aur uske baad ke APIs ka block dhundh kar use ekdam clean likhenge
# Pehle check karte hain ki play_manual_alarm kahan hai, agar hai toh uske upar ka hissa alag kar lo
if 'def play_manual_alarm' in content:
    parts = content.split('def play_manual_alarm')
    base_part = parts[0]
else:
    base_part = content

# 3. Ekdam flawless aur properly indented AJAX & Alarm block
clean_tail_block = '''def play_manual_alarm(cam_name):
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

# Base part ke sath clean tail block ko jod do (authentication views se pehle ya aakhir mein)
if 'def custom_login_view' in base_part:
    auth_parts = base_part.split('def custom_login_view')
    final_content = auth_parts[0] + clean_tail_block + '\n\ndef custom_login_view' + auth_parts[1]
else:
    final_content = base_part + '\n\n' + clean_tail_block

with open(path, 'w', encoding='utf-8') as f:
    f.write(final_content)

print('SUCCESS: core/views.py completely rebuilt from root with uniform indentation!')
