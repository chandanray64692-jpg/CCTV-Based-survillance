# logs/admin.py
from django.contrib import admin
from .models import GateLog

@admin.register(GateLog)
class GateLogAdmin(admin.ModelAdmin):
    list_display = ('visitor', 'camera', 'status', 'timestamp')
    list_filter = ('status', 'camera')
    search_fields = ('visitor__name',)
    readonly_fields = ('timestamp',)