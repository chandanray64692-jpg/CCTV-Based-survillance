# cameras/management/commands/run_surveillance.py
import time
from django.core.management.base import BaseCommand
from cameras.models import CameraNode
from visitors.tasks import run_ai_surveillance_task

class Command(BaseCommand):
    help = 'Continuously triggers background AI face recognition tasks for all active camera nodes.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Secure Vision Continuous AI Surveillance Loop Started..."))

        while True:
            active_cameras = CameraNode.objects.filter(is_active=True)
            if not active_cameras.exists():
                self.stdout.write(self.style.WARNING("⚠️ No active cameras found. Waiting..."))
                time.sleep(5)
                continue

            for camera in active_cameras:
                # Trigger Celery background asynchronous task for each camera node
                run_ai_surveillance_task.delay(camera.id, camera.rtsp_url)
                self.stdout.write(f"-> Dispatched frame task for Camera: {camera.name}")

            # Control frequency (e.g., process frames every 2 seconds per camera)
            time.sleep(2)