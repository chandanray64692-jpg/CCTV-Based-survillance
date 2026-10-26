# logs/views.py
from rest_framework import viewsets
from .models import GateLog
from .serializers import GateLogSerializer

class GateLogViewSet(viewsets.ModelViewSet):
    queryset = GateLog.objects.all().order_by('-timestamp')
    serializer_class = GateLogSerializer# logs/views.py
import io
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from .models import GateLog
from .serializers import GateLogSerializer

class GateLogViewSet(viewsets.ModelViewSet):
    queryset = GateLog.objects.all().order_by('-timestamp')
    serializer_class = GateLogSerializer

    @action(detail=False, methods=['get'])
    def export_pdf(self, request):
        """
        Export all Gate Logs into a clean PDF report format.
        """
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title & Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "Secure Vision - Daily Gate Logs Report")
        
        p.setFont("Helvetica", 10)
        p.drawString(50, height - 70, "Automated AI Security Guard System")
        p.line(50, height - 80, width - 50, height - 80)

        # Table Headers
        y = height - 110
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, y, "Visitor Name")
        p.drawString(200, y, "Camera Node")
        p.drawString(350, y, "Status")
        p.drawString(450, y, "Timestamp")
        y -= 20

        # Fetch Logs
        p.setFont("Helvetica", 9)
        logs = GateLog.objects.all().order_by('-timestamp')[:50] # Last 50 logs

        for log in logs:
            if y < 50:  # Add new page if space runs out
                p.showPage()
                y = height - 50
            
            visitor_name = log.visitor.name if log.visitor else "Unknown"
            camera_name = log.camera.name if log.camera else "N/A"
            
            p.drawString(50, y, visitor_name)
            p.drawString(200, y, camera_name)
            p.drawString(350, y, log.status)
            p.drawString(450, y, log.timestamp.strftime('%Y-%m-%d %H:%M:%S'))
            y -= 18

        p.showPage()
        p.save()

        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="gate_logs_report.pdf"'})