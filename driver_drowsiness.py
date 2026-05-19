# Importing required libraries
import cv2
import numpy as np
import dlib
from imutils import face_utils
from playsound import playsound
import threading

# Initialize the camera
cap = cv2.VideoCapture(0)

# Initialize dlib's face detector and facial landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# Status variables
sleep = 0
drowsy = 0
active = 0
status = ""
color = (0, 0, 0)

# Head-turn detection parameters and counters
LOOK_OFFSET_THRESHOLD = 0.15  # normalized horizontal nose offset vs. inter-ocular distance
LOOK_CONSEC_FRAMES = 6        # frames to confirm a left/right look
look_left = 0
look_right = 0

# Function to compute Euclidean distance
def compute(ptA, ptB):
    dist = np.linalg.norm(ptA - ptB)
    return dist

# Function to determine if eyes are closed or open
def blinked(a, b, c, d, e, f):
    up = compute(b, d) + compute(c, e)
    down = compute(a, f)
    ratio = up / (2.0 * down)

    if ratio > 0.25:
        return 2  # open
    elif 0.21 < ratio <= 0.25:
        return 1  # drowsy
    else:
        return 0  # closed

# Head-turn helpers
def nose_horizontal_offset_ratio(landmarks: np.ndarray) -> float:
    """Return normalized horizontal offset of nose tip from eyes midpoint.

    Positive => nose to the right of midpoint; Negative => to the left.
    Normalized by inter-ocular distance to be scale-invariant.
    """
    left_eye_pts = landmarks[36:42]
    right_eye_pts = landmarks[42:48]
    left_center = left_eye_pts.mean(axis=0)
    right_center = right_eye_pts.mean(axis=0)
    eyes_center_x = (left_center[0] + right_center[0]) / 2.0
    interocular_distance = float(np.linalg.norm(right_center - left_center))

    # Using landmark index 30 for nose tip in 68-point model
    nose_tip_x = float(landmarks[30][0])

    return (nose_tip_x - eyes_center_x) / (interocular_distance + 1e-6)

def head_turn_direction(landmarks: np.ndarray, threshold: float = LOOK_OFFSET_THRESHOLD):
    """Classify head turn as ('left'|'right'|'center'), plus raw offset ratio."""
    offset = nose_horizontal_offset_ratio(landmarks)
    if offset <= -threshold:
        return "left", offset
    if offset >= threshold:
        return "right", offset
    return "center", offset

# Function to play alert sound in a separate thread
def play_alert():
    threading.Thread(target=playsound, args=("alarm.wav",), daemon=True).start()

# Main loop
while True:
    _, frame = cap.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = detector(gray)
    face_frame = frame.copy()

    for face in faces:
        x1 = face.left()
        y1 = face.top()
        x2 = face.right()
        y2 = face.bottom()

        cv2.rectangle(face_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        landmarks = predictor(gray, face)
        landmarks = face_utils.shape_to_np(landmarks)

        left_blink = blinked(landmarks[36], landmarks[37],
                             landmarks[38], landmarks[41], landmarks[40], landmarks[39])
        right_blink = blinked(landmarks[42], landmarks[43],
                              landmarks[44], landmarks[47], landmarks[46], landmarks[45])

        if left_blink == 0 or right_blink == 0:
            sleep += 1
            drowsy = 0
            active = 0
            if sleep > 6:
                status = "SLEEPING !!!"
                color = (255, 0, 0)
                play_alert()

        elif left_blink == 1 or right_blink == 1:
            sleep = 0
            active = 0
            drowsy += 1
            if drowsy > 6:
                status = "Drowsy !"
                color = (0, 0, 255)
                play_alert()

        else:
            drowsy = 0
            sleep = 0
            active += 1
            if active > 6:
                status = "Active :)"
                color = (0, 255, 0)

        # ---- Head turn detection (left/right looking away) ----
        direction, _ = head_turn_direction(landmarks)

        if direction == "left":
            look_left += 1
            look_right = 0
        elif direction == "right":
            look_right += 1
            look_left = 0
        else:
            look_left = 0
            look_right = 0

        # Only override status if not already in sleep/drowsy state
        if status not in ("SLEEPING !!!", "Drowsy !"):
            if look_left > LOOK_CONSEC_FRAMES:
                status = "Looking Left"
                color = (0, 0, 255)
                play_alert()
            elif look_right > LOOK_CONSEC_FRAMES:
                status = "Looking Right"
                color = (0, 0, 255)
                play_alert()

        # Display status text
        cv2.putText(frame, status, (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        # Draw facial landmarks
        for n in range(0, 68):
            (x, y) = landmarks[n]
            cv2.circle(face_frame, (x, y), 1, (255, 255, 255), -1)

    # Show video frames
    cv2.imshow("Frame", frame)
    cv2.imshow("Result of detector", face_frame)

    # Exit on ESC key
    key = cv2.waitKey(1)
    if key == 27:
        break

# Release the camera and close windows
cap.release()
cv2.destroyAllWindows()
