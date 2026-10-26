# cameras/services/onvif_client.py
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
import time

def discover_network_cameras():
    """
    Scans the local network for active ONVIF/RTSP IP Cameras.
    """
    wsd = WSDiscovery()
    wsd.start()
    time.sleep(3) # 3 seconds tak network par cameras ka wait karein
    services = wsd.searchServices()
    wsd.stop()

    cameras = []
    for service in services:
        # Filter and extract IP addresses
        types = [str(t) for t in service.getTypes()]
        if any("NetworkVideo" in t or "Device" in t for t in types):
            ip_address = service.getXAddrs()[0] if service.getXAddrs() else None
            if ip_address:
                clean_ip = ip_address.split('//')[-1].split('/')[0]
                cameras.append({
                    "name": f"Detected Camera ({clean_ip})",
                    "ip": clean_ip,
                    "rtsp_url": f"rtsp://admin:password@{clean_ip}:554/stream", # Default format
                    "location": "Local Network"
                })
    
    # Fallback/Dummy for testing if no physical IP camera is found on the network
    if not cameras:
        cameras.append({
            "name": "Laptop Webcam (Default)",
            "ip": "localhost",
            "rtsp_url": "0",
            "location": "Internal"
        })
        cameras.append({
            "name": "Demo IP Camera (Hikvision)",
            "ip": "192.168.1.100",
            "rtsp_url": "rtsp://admin:admin123@192.168.1.100:554/Streaming/Channels/101",
            "location": "Main Gate"
        })

    return cameras