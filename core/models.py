from django.db import models

class CameraNode(models.Model):
    name = models.CharField(max_length=100)
    rtsp_url = models.CharField(max_length=255)
    zone_category = models.CharField(max_length=100, default='Perimeter')
    is_active = models.BooleanField(default=True)
    
    # AI Task Assignment Flags
    enable_anpr = models.BooleanField(default=False)
    enable_intrusion = models.BooleanField(default=False)
    enable_fence = models.BooleanField(default=False)
    enable_mobile_detection = models.BooleanField(default=False)
    enable_threat_detection = models.BooleanField(default=False)
    enable_crowd = models.BooleanField(default=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    from django.db import models

class AlertLog(models.Model):
    camera = models.ForeignKey('CameraNode', on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default='Critical')
    image_path = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message} - {self.timestamp}"

from django.db import models

class CameraNode(models.Model):
    name = models.CharField(max_length=100)
    rtsp_url = models.CharField(max_length=255)
    zone_category = models.CharField(max_length=100, default='Perimeter')
    is_active = models.BooleanField(default=True)
    
    # AI Task Assignment Flags
    enable_anpr = models.BooleanField(default=False)
    enable_intrusion = models.BooleanField(default=False)
    enable_fence = models.BooleanField(default=False)
    enable_mobile_detection = models.BooleanField(default=False)
    enable_threat_detection = models.BooleanField(default=False)
    enable_crowd = models.BooleanField(default=False)
    # CameraNode mein yeh fields jodein
    tripwire_line = models.CharField(max_length=255, blank=True, null=True) # Format: "x1,y1,x2,y2"
    roi_polygon = models.TextField(blank=True, null=True) # JSON format for polygon points
    enable_loitering = models.BooleanField(default=False)
    enable_clahe = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class AlertLog(models.Model):
    camera = models.ForeignKey(CameraNode, on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default='Critical')
    image_path = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message} - {self.timestamp}"

class VehicleLog(models.Model):
    camera = models.ForeignKey(CameraNode, on_delete=models.CASCADE, null=True, blank=True)
    plate_number = models.CharField(max_length=50, default="UNKNOWN")
    confidence = models.FloatField(default=0.0)
    direction = models.CharField(max_length=10, default="IN") # IN or OUT
    snapshot = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plate_number} ({self.direction}) at {self.timestamp}"

class VehicleWatchlist(models.Model):
    plate_number = models.CharField(max_length=50, unique=True)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    vehicle_type = models.CharField(max_length=50, blank=True, null=True)
    threat_level = models.CharField(max_length=50, default='Medium')
    added_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.plate_number

