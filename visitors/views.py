# visitors/views.py
from rest_framework import viewsets
from .models import Visitor
from .serializers import VisitorSerializer

class VisitorViewSet(viewsets.ModelViewSet):
    queryset = Visitor.objects.all()
    serializer_class = VisitorSerializer