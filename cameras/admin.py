from django.contrib import admin
from .models import CameraNode, AlertLog

@admin.register(CameraNode)
class CameraNodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'zone_category', 'rtsp_url')
    search_fields = ('name', 'zone_category')

@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'camera', 'message', 'status', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('message', 'status')