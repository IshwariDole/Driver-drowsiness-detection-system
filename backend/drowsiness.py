# import time
# import cv2
# import dlib
# import numpy as np
# from imutils import face_utils
# from db import insert_log

# # ---------- Models ----------
# detector = dlib.get_frontal_face_detector()
# predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# # ---------- Global state ----------
# sleep = drowsy = active = 0
# status = "Active"
# last_status = None

# cap = None
# running = False
# current_driver_id = None

# # timers for delayed alerts
# no_face_since = None
# tilt_since = None

# # ---------- Helpers ----------
# def eye_blink_ratio(eye_pts, lm):
#     # horizontal
#     left = np.array(lm[eye_pts[0]])
#     right = np.array(lm[eye_pts[3]])
#     # vertical (avg of 2 vertical lines)
#     top = np.mean([lm[eye_pts[1]], lm[eye_pts[2]]], axis=0)
#     bottom = np.mean([lm[eye_pts[5]], lm[eye_pts[4]]], axis=0)

#     hor = np.linalg.norm(left - right)
#     ver = np.linalg.norm(top - bottom)
#     # higher ratio => more closed eye (matches your previous logic)
#     return hor / (ver + 1e-6)

# def mouth_aspect_ratio(lm):
#     """
#     Inner-mouth MAR using points 60..67 (68-point model).
#     MAR = (||61-67|| + ||63-65||) / (2*||60-64||)
#     Larger MAR => mouth open (yawn).
#     """
#     p = lm
#     A = np.linalg.norm(p[61] - p[67])
#     B = np.linalg.norm(p[63] - p[65])
#     C = np.linalg.norm(p[60] - p[64])
#     return (A + B) / (2.0 * C + 1e-6)

# def eye_line_tilt_deg(lm):
#     """Angle (deg) of the line between eye centers. > ~15° means head tilt."""
#     left_eye_pts = lm[36:42]
#     right_eye_pts = lm[42:48]
#     left_center = left_eye_pts.mean(axis=0)
#     right_center = right_eye_pts.mean(axis=0)
#     dy = right_center[1] - left_center[1]
#     dx = right_center[0] - left_center[0]
#     return float(np.degrees(np.arctan2(dy, dx)))

# def emit_and_log(new_status, socketio=None, driver_id=None):
#     """Emit socket event and log to DB only when status changes."""
#     global last_status, status
#     status = new_status
#     if socketio:
#         socketio.emit("alert", {"status": status, "driver_id": driver_id})
#     if status != last_status:
#         insert_log(status, driver_id)
#         last_status = status

# # ---------- Streaming ----------
# def gen_frames(socketio=None, driver_id=None):
#     """
#     Main generator for MJPEG stream. Evaluates states and emits alerts.
#     """
#     global cap, running
#     global sleep, drowsy, active, status, last_status
#     global no_face_since, tilt_since

#     # reset per-run counters/timers
#     sleep = drowsy = active = 0
#     status = "Active"
#     last_status = None
#     no_face_since = None
#     tilt_since = None

#     cap = cv2.VideoCapture(0)
#     if not cap.isOpened():
#         print("❌ Error: Camera not accessible")
#         emit_and_log("Camera Error", socketio, driver_id)
#         return

#     while running:
#         ok, frame = cap.read()
#         if not ok:
#             break

#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         faces = detector(gray)

#         # Defaults each frame
#         frame_status = "Active"
#         now = time.time()

#         if len(faces) == 0:
#             # track "looking away" time (no face)
#             if no_face_since is None:
#                 no_face_since = now
#             if (now - no_face_since) >= 3.0:
#                 frame_status = "Looking Away"
#         else:
#             # face detected -> reset "looking away" timer
#             no_face_since = None

#             for face in faces:
#                 lm_shape = predictor(gray, face)
#                 lm = face_utils.shape_to_np(lm_shape)

#                 # ---------- EYES ----------
#                 left_ratio = eye_blink_ratio([36, 37, 38, 39, 40, 41], lm)
#                 right_ratio = eye_blink_ratio([42, 43, 44, 45, 46, 47], lm)
#                 blink_ratio = (left_ratio + right_ratio) / 2.0

#                 # ---------- MOUTH (Yawn) ----------
#                 mar = mouth_aspect_ratio(lm)

#                 # ---------- HEAD TILT ----------
#                 tilt_deg = abs(eye_line_tilt_deg(lm))
#                 if tilt_deg > 15:
#                     if tilt_since is None:
#                         tilt_since = now
#                 else:
#                     tilt_since = None

#                 # ---------- Decision logic & priorities ----------
#                 # 1) Sleeping (eyes closed) -> IMMEDIATE
#                 if blink_ratio > 5.7:
#                     frame_status = "SLEEPING !!!"

#                 # 2) Yawning -> IMMEDIATE
#                 elif mar > 0.70:
#                     frame_status = "Yawning"

#                 # 3) Head Tilt held for >= 3s
#                 elif tilt_since is not None and (now - tilt_since) >= 3.0:
#                     frame_status = "Head Tilt"

#                 # 4) Drowsy (slower eyes) -> stabilize with a few frames
#                 elif blink_ratio > 4.8:
#                     drowsy += 1
#                     sleep = 0
#                     active = 0
#                     if drowsy > 6:
#                         frame_status = "Drowsy"
#                 else:
#                     active += 1
#                     sleep = 0
#                     drowsy = 0
#                     if active > 6:
#                         frame_status = "Active"

#                 # Only evaluate first detected face (keep simple)
#                 break

#         # Emit & log (only on change), plus always overlay
#         emit_and_log(frame_status, socketio, driver_id)

#         # Overlay info
#         cv2.putText(frame, frame_status, (24, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
#         # (Optional) debug values:
#         # cv2.putText(frame, f"blink: {blink_ratio:.2f}  MAR: {mar:.2f}  tilt: {tilt_deg:.1f}",
#         #             (24, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

#         # stream frame
#         ok, buf = cv2.imencode(".jpg", frame)
#         if not ok:
#             continue
#         frame_bytes = buf.tobytes()

#         yield (
#             b"--frame\r\n"
#             b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
#         )

#     # cleanup
#     if cap:
#         cap.release()
#     cv2.destroyAllWindows()

# # ---------- Control API used by app.py ----------
# def start_detection(driver_id=None):
#     """Arm the detector; actual capture happens in gen_frames when /video_feed is requested."""
#     global running, current_driver_id
#     current_driver_id = driver_id
#     running = True
#     print(f"✅ Detection armed for driver: {driver_id}")

# def stop_detection():
#     """Gracefully stop running loop (gen_frames will exit)."""
#     global running, cap
#     running = False
#     if cap:
#         cap.release()
#         cap = None
#     cv2.destroyAllWindows()
#     print("🛑 Detection stopped")

# def is_running():
#     return running
# drowsiness.py
import time
import cv2
import dlib
import numpy as np
from imutils import face_utils
from db import insert_log,get_emergency_contact
import pywhatkit
alert_start_time = None
alert_sent = False


# ---------- Models ----------
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# ---------- Global state ----------
sleep = drowsy = active = 0
status = "Active"
last_status = None

cap = None
running = False
current_driver_id = None

# timers for delayed alerts
no_face_since = None
tilt_since = None
gaze_since = None
eyes_closed_since = None

# thresholds (tweak if needed)
BLINK_RATIO_SLEEP = 5.7
BLINK_RATIO_DROWSY = 4.8
MAR_YAWN = 0.70
TILT_DEG_THRESHOLD = 15.0
HOLD_HEADSEC = 4.0        # seconds to hold tilt/gaze to trigger
NO_FACE_HOLD_SEC = 3.0
EYES_CLOSED_HOLD_SEC = 3.0
GAZE_THRESHOLD = 0.16     # nose offset normalized threshold for considering "looking away"

# ---------- Helpers ----------
def eye_blink_ratio(eye_pts, lm):
    left = np.array(lm[eye_pts[0]])
    right = np.array(lm[eye_pts[3]])
    top = np.mean([lm[eye_pts[1]], lm[eye_pts[2]]], axis=0)
    bottom = np.mean([lm[eye_pts[5]], lm[eye_pts[4]]], axis=0)
    hor = np.linalg.norm(left - right)
    ver = np.linalg.norm(top - bottom)
    return hor / (ver + 1e-6)

def mouth_aspect_ratio(lm):
    p = lm
    A = np.linalg.norm(p[61] - p[67])
    B = np.linalg.norm(p[63] - p[65])
    C = np.linalg.norm(p[60] - p[64])
    return (A + B) / (2.0 * C + 1e-6)

def eye_line_tilt_deg(lm):
    left_eye_pts = lm[36:42]
    right_eye_pts = lm[42:48]
    left_center = left_eye_pts.mean(axis=0)
    right_center = right_eye_pts.mean(axis=0)
    dy = right_center[1] - left_center[1]
    dx = right_center[0] - left_center[0]
    return float(np.degrees(np.arctan2(dy, dx)))

def nose_gaze_offset(lm):
    nose = np.array(lm[33])
    xs = lm[:, 0]
    ys = lm[:, 1]
    center = np.array([xs.mean(), ys.mean()])
    w = xs.max() - xs.min() + 1e-6
    h = ys.max() - ys.min() + 1e-6
    dx = (nose[0] - center[0]) / w
    dy = (nose[1] - center[1]) / h
    return float(dx), float(dy)

def emit_and_log(new_status, socketio=None, driver_id=None):
    global last_status, status
    status = new_status
    if socketio:
        try:
            socketio.emit("alert", {"status": status, "driver_id": driver_id})
        except Exception as e:
            print("Socket emit error:", e)
    if status != last_status:
        try:
            insert_log(status, driver_id)
        except Exception as e:
            print("Log insert error:", e)
        last_status = status


def format_phone_number(number):
    """Convert number to WhatsApp international format"""
    if not number:
        return None

    number = str(number).replace(" ", "").replace("-", "")

    if number.startswith("+"):
        return number
    if number.startswith("0"):
        return "+91" + number[1:]
    if len(number) == 10:
        return "+91" + number

    return "+" + number
# ---------- Streaming ----------
def gen_frames(socketio=None, driver_id=None):
    global cap, running
    global sleep, drowsy, active, status, last_status
    global no_face_since, tilt_since, gaze_since, eyes_closed_since

    # reset per-run counters/timers
    sleep = drowsy = active = 0
    status = "Active"
    last_status = None
    no_face_since = None
    tilt_since = None
    gaze_since = None
    eyes_closed_since = None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Error: Camera not accessible")
        emit_and_log("Camera Error", socketio, driver_id)
        return

    while running:
        ok, frame = cap.read()
        if not ok:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector(gray)

        frame_status = "Active"
        now = time.time()

        # No face detected -> count as looking away after NO_FACE_HOLD_SEC
        if len(faces) == 0:
            if no_face_since is None:
                no_face_since = now
            if (now - no_face_since) >= NO_FACE_HOLD_SEC:
                frame_status = "Looking Away"
            # reset in-frame timers
            tilt_since = None
            gaze_since = None
            eyes_closed_since = None
        else:
            no_face_since = None
            # Evaluate first face only
            face = faces[0]
            lm_shape = predictor(gray, face)
            lm = face_utils.shape_to_np(lm_shape)

            # EYES
            left_ratio = eye_blink_ratio([36,37,38,39,40,41], lm)
            right_ratio = eye_blink_ratio([42,43,44,45,46,47], lm)
            blink_ratio = (left_ratio + right_ratio) / 2.0

            # MOUTH (yawn)
            mar = mouth_aspect_ratio(lm)
            if mar > MAR_YAWN:
                frame_status = "Yawning"
                # yawning is immediate; we can prioritize it
            # EYES CLOSED -> require continuous closure for EYES_CLOSED_HOLD_SEC
            if blink_ratio > BLINK_RATIO_SLEEP:
                if eyes_closed_since is None:
                    eyes_closed_since = now
                elif (now - eyes_closed_since) >= EYES_CLOSED_HOLD_SEC:
                    frame_status = "SLEEPING !!!"
            else:
                eyes_closed_since = None

            # HEAD ROLL (left/right tilt)
            tilt_deg = abs(eye_line_tilt_deg(lm))
            tilt_active = tilt_deg > TILT_DEG_THRESHOLD

            # GAZE (nose offset detects left/right/up/down)
            dx, dy = nose_gaze_offset(lm)
            gaze_active = (abs(dx) > GAZE_THRESHOLD) or (abs(dy) > GAZE_THRESHOLD)

            # If either tilt_active or gaze_active, start their respective timers (we unify them)
            if tilt_active or gaze_active:
                # we want to trigger alarm when *either* is held for HOLD_HEADSEC
                if tilt_since is None:
                    tilt_since = now
                # if gaze started earlier or tilt, we use tilt_since as anchor (unified)
                if (now - tilt_since) >= HOLD_HEADSEC:
                    frame_status = "Head Tilt" if tilt_active else "Looking Away"
            else:
                tilt_since = None

            # Drowsy (slower eyes) fallback only if no higher-priority status set
            if frame_status == "Active":
                if blink_ratio > BLINK_RATIO_DROWSY:
                    drowsy += 1
                    sleep = 0
                    active = 0
                    if drowsy > 6:
                        frame_status = "Drowsy"
                else:
                    active += 1
                    sleep = 0
                    drowsy = 0
                    if active > 6:
                        frame_status = "Active"

        # Emit & log (only on change)
        emit_and_log(frame_status, socketio, driver_id)
        # --- WHATSAPP ALERT CHECK ---
        danger_states = ["SLEEPING !!!", "Drowsy", "Yawning", "Looking Away"]

        if frame_status in danger_states:
            if alert_start_time is None:
                alert_start_time = now  # Start counting time in danger
            elif (now - alert_start_time) >= 10 and not alert_sent:  # 2 minutes
                try:
                    # ⭐ Get driver's emergency contact from DB
                    emergency_number = get_emergency_contact(driver_id)
                    emergency_number = format_phone_number(emergency_number)

                    if emergency_number:
                        pywhatkit.sendwhatmsg(
                            emergency_number,
                            f"⚠️ DRIVER EMERGENCY ALERT!\nStatus: {frame_status}\nDriver ID: {driver_id}",
                            time.localtime().tm_hour,
                            (time.localtime().tm_min + 1) % 60
                        )
                        print(f"✅ WhatsApp Alert Sent to {emergency_number}")
                        alert_sent = True
                    else:
                        print("❌ No emergency contact found for this driver")

                    print("✅ WhatsApp Alert Sent!")
                    alert_sent = True
                except Exception as e:
                    print("❌ WhatsApp Error:", e)
        else:
            # Reset if safe again
            alert_start_time = None
            alert_sent = False
        # Overlay status on frame and optional debug info
        try:
            cv2.putText(frame, frame_status, (24,48), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)
            # Debug overlays (uncomment for tuning)
            # cv2.putText(frame, f"tilt:{tilt_deg:.1f} dx:{dx:.2f} dy:{dy:.2f}", (24,84), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255),1)
            # if tilt_since: cv2.putText(frame, f"tilt_since:{int(time.time()-tilt_since)}s", (24,110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255),1)
        except Exception:
            pass

        # Stream frame
        try:
            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            frame_bytes = buf.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        except Exception as e:
            print("Frame encoding error:", e)
            continue

    # cleanup
    if cap:
        cap.release()
    cv2.destroyAllWindows()

# Control API used by app.py
def start_detection(driver_id=None):
    global running, current_driver_id
    current_driver_id = driver_id
    running = True
    print(f"✅ Detection armed for driver: {driver_id}")

def stop_detection():
    global running, cap
    running = False
    if cap:
        cap.release()
        cap = None
    cv2.destroyAllWindows()
    print("🛑 Detection stopped")

def is_running():
    return running