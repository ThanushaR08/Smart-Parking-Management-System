import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Camera not opened")
else:
    ret, frame = cap.read()

    if ret:
        cv2.imwrite("test.jpg", frame)
        print("✅ Image captured successfully.")
    else:
        print("❌ Failed to capture image.")

cap.release()