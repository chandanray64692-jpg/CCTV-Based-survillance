# visitors/services/liveness.py
import cv2
import numpy as np

def check_liveness(frame):
    """
    Basic Anti-Spoofing & Liveness Detection heuristic check.
    In production, deep learning models like MiniFASNet are used.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 1. Texture Analysis (Laplacian Variance for Blur/Print Detection)
    # Printed photos or mobile screens often lack micro-texture variance compared to real skin.
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Threshold for blur/print spoofing (adjust based on camera quality)
    if laplacian_var < 15.0:
        return False, "⚠️ *SECURITY ALERT*: Possible Spoof Attack (Printed Photo/Screen detected)!"
        
    return True, "Real Human Verified"