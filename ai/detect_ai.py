from ultralytics import YOLO
import cv2

# Load YOLO model
model = YOLO("yolov8n.pt")

# Open camera
cap = cv2.VideoCapture(0)

ret, frame = cap.read()

if not ret:
    print("Failed to capture image")
    cap.release()
    exit()

# Run AI detection
results = model(frame)

# Draw bounding boxes
annotated = results[0].plot()

# Save detected image
cv2.imwrite("static/uploads/detected_vehicle.jpg", annotated)

print("✅ Vehicle detected successfully!")
print("Image saved to static/uploads/detected_vehicle.jpg")

cap.release()