import cv2
import os

# RTSP connection ko TCP par force karne ke liye (video drop nahi hoga)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# Yahan apna NVR ya Camera ka RTSP URL daalein
rtsp_url = "rtsp://admin:Security_54idsr@192.168.1.101:554/cam/realmonitor?channel=1&subtype=1"

print(f"🔄 Connecting to: {rtsp_url}...")
cap = cv2.VideoCapture(rtsp_url)

if cap.isOpened():
    ret, frame = cap.read()
    if ret:
        print("\n✅ SUCCESS: Camera connect ho gaya aur video feed aa rahi hai!")
        # Agar aap chahein toh frame ko screen par dekhne ke liye niche wali lines uncomment kar sakte hain
        # cv2.imshow("Camera Test", frame)
        # cv2.waitKey(3000) # 3 second ke liye window khulegi
    else:
        print("\n⚠️ WARNING: Camera connect hua par video blank aa raha hai.")
else:
    print("\n❌ ERROR: Camera connect nahi ho paya. URL, Password ya IP check karein.")

cap.release()
# cv2.destroyAllWindows()