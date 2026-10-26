# cameras/serializers.py
from rest_framework import serializers
from .models import CameraNode

class CameraNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CameraNode
        fields = '__all__'