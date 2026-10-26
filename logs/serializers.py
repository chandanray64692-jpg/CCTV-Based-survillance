# logs/serializers.py
from rest_framework import serializers
from .models import GateLog

class GateLogSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source='visitor.name', read_only=True)
    camera_name = serializers.CharField(source='camera.name', read_only=True)

    class Meta:
        model = GateLog
        fields = '__all__'