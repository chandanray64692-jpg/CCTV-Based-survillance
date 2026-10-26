# logs/models.py
from django.db import models
from cameras.models import CameraNode
from visitors.models import Visitor

class GateLog(models.Model):
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, null=True, blank=True)
    camera = models.ForeignKey(CameraNode, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[('Entry', 'Entry'), ('Exit', 'Exit'), ('Unknown', 'Unknown')])
    timestamp = models.DateTimeField(auto_now_add=True)
    snapshot = models.ImageField(upload_to='log_snapshots/', blank=True, null=True)

    def __str__(self):
        visitor_name = self.visitor.name if self.visitor else "Unknown"
        return f"{visitor_name} - {self.status} at {self.timestamp}"

    # logs/models.py (Add this below your existing GateLog model)

class VehicleLog(models.Model):
    license_plate = models.CharField(max_length=20)
    camera = models.ForeignKey('cameras.CameraNode', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=[('Entry', 'Entry'), ('Exit', 'Exit'), ('Unknown', 'Unknown')])
    timestamp = models.DateTimeField(auto_now_add=True)
    snapshot = models.ImageField(upload_to='vehicle_snapshots/', blank=True, null=True)

    def __str__(self):
        return f"Vehicle {self.license_plate} - {self.status} at {self.timestamp}"
# logs/models.py (Add Footprint Track model)
class VisitorFootprint(models.Model):
    visitor = models.ForeignKey('visitors.Visitor', on_delete=models.CASCADE, null=True, blank=True)
    camera = models.ForeignKey('cameras.CameraNode', on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    action_sequence = models.CharField(max_length=255) # e.g., "Main Gate ➔ Ground ➔ Mess"
    snapshot = models.ImageField(upload_to='footprints/', blank=True, null=True)

    def __str__(self):
        v_name = self.visitor.name if self.visitor else "Unknown"
        return f"Track: {v_name} at {self.camera.name} ({self.timestamp})"