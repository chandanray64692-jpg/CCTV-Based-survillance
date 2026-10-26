# core/management/commands/archive_logs.py
import os
import shutil
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from logs.models import GateLog, VehicleLog

class Command(BaseCommand):
    help = 'Automatically archives old logs and snapshots to save disk space.'

    def handle(self, *args, **options):
        self.stdout.write("📦 Starting Secure Vision Log & Snapshot Archiving...")

        # 30 din purane logs ko archive karna
        threshold_date = timezone.now() - timedelta(days=30)
        
        media_root = settings.MEDIA_ROOT
        archive_dir = os.path.join(media_root, 'archives')
        os.makedirs(archive_dir, exist_ok=True)

        # Create a zip archive of old snapshots
        date_str = datetime.now().strftime('%Y-%m-%d')
        backup_zip_path = os.path.join(archive_dir, f"backup_logs_{date_str}")

        snapshots_folder = os.path.join(media_root, 'log_snapshots')
        if os.path.exists(snapshots_folder):
            shutil.make_archive(backup_zip_path, 'zip', snapshots_folder)
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully created archive: {backup_zip_path}.zip"))

        # Database se purane logs clean karne ki query (Optional)
        old_gates = GateLog.objects.filter(timestamp__lt=threshold_date)
        count = old_gates.count()
        # old_gates.delete() # Uncomment if you want to delete records older than 30 days

        self.stdout.write(self.style.SUCCESS(f"🎯 Archiving process completed. Checked {count} old records."))