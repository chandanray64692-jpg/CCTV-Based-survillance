from django.db import models

class CameraNode(models.Model):
    # 1. Basic Identification & Stream URL
    name = models.CharField(max_length=100, unique=True)
    rtsp_url = models.CharField(max_length=255, default="0")
    location = models.CharField(max_length=150, blank=True, null=True)
    
    zone_category = models.CharField(max_length=50, default="Perimeter", choices=[
        ('Gate', 'Main/Secondary Gate'),
        ('Perimeter', 'Perimeter/Boundary'),
        ('Indoor', 'Indoor/Corridor'),
        ('Mess', 'Dining/Mess Area'),
        ('Headquarters', 'Headquarters')
    ])

    # 2. Credentials & Network Authentication
    username = models.CharField(max_length=50, blank=True, null=True)
    password = models.CharField(max_length=50, blank=True, null=True)
    
    # 3. Geo-Spatial Location
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)

    # 4. Per-Camera AI Feature Toggles & Rules
    enable_face_recognition = models.BooleanField(default=True)
    enable_anpr = models.BooleanField(default=False)
    enable_threat_detection = models.BooleanField(default=True)
    enable_liveness = models.BooleanField(default=True)
    enable_mobile_detection = models.BooleanField(default=True)
    enable_crowd_detection = models.BooleanField(default=True)
    enable_fence_alert = models.BooleanField(default=False)
    
    zone_name = models.CharField(max_length=100, blank=True, null=True)
    zone_type = models.CharField(max_length=50, default='Intrusion Zone')
    trigger_mode = models.CharField(max_length=50, default='Instant')
    zone_description = models.TextField(blank=True, null=True)
    polygon_points = models.JSONField(default=list, blank=True, null=True)
    
    # Granular AI Rules for Control Center
    rule_intrusion = models.BooleanField(default=False)
    rule_anpr = models.BooleanField(default=True)
    rule_fire = models.BooleanField(default=False)
    rule_face = models.BooleanField(default=False)
    
    # 5. Tripwire Coordinates for Occupancy / Line Crossing
    line_x1 = models.IntegerField(default=50)
    line_y1 = models.IntegerField(default=200)
    line_x2 = models.IntegerField(default=500)
    line_y2 = models.IntegerField(default=128)

    # 6. Stream Quality & Performance Settings
    stream_quality = models.CharField(max_length=20, default="Sub-Stream", choices=[
        ('Main-Stream', 'Main-Stream (1080p HD)'),
        ('Sub-Stream', 'Sub-Stream (720p Optimized)')
    ])
    fps_limit = models.IntegerField(default=15)

    # 7. System Status & Timestamps
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.zone_category})"


class AlertLog(models.Model):
    camera = models.ForeignKey(CameraNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='camera_alert_logs')
    message = models.TextField()
    status = models.CharField(max_length=50, default="Critical")
    image_path = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp}] {self.camera.name if self.camera else 'System'} - {self.message}"


class VehicleLog(models.Model):
    DIRECTION_CHOICES = [
        ('IN', 'Entry (IN)'),
        ('OUT', 'Exit (OUT)'),
        ('UNKNOWN', 'Unknown')
    ]
    
    camera = models.ForeignKey(CameraNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='camera_veh_logs')
    plate_number = models.CharField(max_length=50, default="UNKNOWN")
    vehicle_type = models.CharField(max_length=50, default="Car")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='IN')
    confidence = models.FloatField(default=0.0)
    
    # Dual Image Storage & Legacy path compatibility
    image_path = models.CharField(max_length=255, blank=True, null=True)
    vehicle_image = models.ImageField(upload_to='vehicle_snapshots/', blank=True, null=True)
    plate_image = models.ImageField(upload_to='plate_snapshots/', blank=True, null=True)
    
    status = models.CharField(max_length=50, default="Authorized")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plate_number} - {self.direction} ({self.timestamp.strftime('%d-%m-%Y %H:%M')})"


class KnownFace(models.Model):
    name = models.CharField(max_length=100)
    face_type = models.CharField(max_length=50, choices=[('Employee', 'Employee'), ('Suspect', 'Suspect')])
    image = models.ImageField(upload_to='known_faces/')
    encoding = models.TextField(blank=True, null=True) 

    def __str__(self):
        return f"{self.name} ({self.face_type})"


class VehicleWatchlist(models.Model):
    plate_number = models.CharField(max_length=50, unique=True)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    vehicle_type = models.CharField(max_length=50, blank=True, null=True)
    risk_level = models.CharField(max_length=20, default="High") # High, Medium, Low
    reason = models.CharField(max_length=255, blank=True, null=True)
    owner = models.CharField(max_length=100, blank=True, null=True)
    is_suspect = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plate_number} ({self.owner_name or self.owner or 'Suspect'})"