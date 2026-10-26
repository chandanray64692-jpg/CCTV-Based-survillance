# visitors/services/tracker.py
from logs.models import VisitorFootprint
from django.utils import timezone
from datetime import timedelta

def update_visitor_footprint(visitor, camera, snapshot_file):
    """
    Tracks movement of a person across multiple cameras and builds a footprint trail.
    """
    if not visitor:
        return "Unknown Track"

    # Pichle 1 ghante ke andar ke tracks check karein
    recent_time = timezone.now() - timedelta(hours=1)
    last_tracks = VisitorFootprint.objects.filter(visitor=visitor, timestamp__gte=recent_time).order_by('-timestamp')

    sequence_list = [camera.name]
    for track in last_tracks:
        if track.camera and track.camera.name not in sequence_list:
            sequence_list.append(track.camera.name)

    # Sequence ko reverse karein taaki chronological order bane (Gate ➔ Ground ➔ Mess)
    sequence_list.reverse()
    path_string = " ➔ ".join(sequence_list)

    # Save new footprint log
    VisitorFootprint.objects.create(
        visitor=visitor,
        camera=camera,
        action_sequence=path_string,
        snapshot=snapshot_file
    )

    return path_string