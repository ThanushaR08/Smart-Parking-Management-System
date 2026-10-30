import cv2

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("Cannot open camera")
    exit()

print("Press 'S' to capture vehicle")
print("Press 'Q' to quit")

while True:

    success, frame = camera.read()

    if not success:
        break

    cv2.imshow("Smart Parking AI Camera", frame)

    key = cv2.waitKey(1)

    if key == ord("s"):

        cv2.imwrite("static/uploads/vehicle.jpg", frame)

        print("Vehicle image saved.")

        break

    elif key == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()