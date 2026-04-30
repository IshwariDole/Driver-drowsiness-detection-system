from flask import Flask, Response, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
# Import the module and the functions you need
import drowsiness
from drowsiness import gen_frames, start_detection, stop_detection, is_running

from db import add_driver_account, verify_driver, get_logs, get_drivers, get_driver


app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.route("/")
def home():
    return jsonify({"message": "Driver Drowsiness Detection API Running!"})

# ---------- Auth / Data ----------
@app.route("/register", methods=["POST"])
def register_driver():
    data = request.json or {}
    required = ["name", "vehicle", "contact", "emergency_contact", "password"]
    if not all(data.get(k) for k in required):
        return jsonify({"success": False, "message": "All fields required"}), 400

    driver_id = add_driver_account({
        "name": data["name"],
        "vehicle": data["vehicle"],
        "contact": data["contact"],
        "emergency_contact": data["emergency_contact"],
        "password": data["password"],
    })
    return jsonify({"success": True, "message": "Driver registered", "driver_id": str(driver_id)})

@app.route("/login", methods=["POST"])
def login_driver():
    data = request.json or {}
    driver = verify_driver(data.get("vehicle"), data.get("password"))
    if driver:
        return jsonify({"success": True, "message": "Login successful", "driver_id": str(driver["_id"])})
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route("/drivers", methods=["GET"])
def list_drivers():
    drivers = get_drivers()
    for d in drivers:
        d["_id"] = str(d["_id"])
    return jsonify(drivers)

@app.route("/logs", methods=["GET"])
def logs():
    driver_id = request.args.get("driver_id")
    logs = get_logs(driver_id=driver_id)
    return jsonify([
        {
            "time": str(log["_id"].generation_time),
            "event": log["event"],
            "driver_id": log.get("driver_id")
        }
        for log in logs
    ])


# //changes
# ---------- Detection control ----------

@app.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True) or {}
    driver_id = data.get("driver_id")

    driver = get_driver(driver_id)
    if not driver:
        return jsonify({"ok": False, "message": "Driver not found"}), 404

    # Start detection for the driver
    drowsiness.start_detection(driver_id=driver_id)

    return jsonify({"ok": True, "running": True})


@app.route("/stop", methods=["POST"])
def stop():
    stop_detection()   # from drowsiness.py
    return jsonify({"ok": True, "running": False})

@app.route("/video_feed")
def video_feed():
    driver_id = request.args.get("driver_id")
    if not is_running():   # from drowsiness.py
        return jsonify({"ok": False, "message": "Detection stopped"}), 503
    return Response(
        gen_frames(socketio=socketio, driver_id=driver_id),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

if __name__ == "__main__":
    print("✅ Flask app running at http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
