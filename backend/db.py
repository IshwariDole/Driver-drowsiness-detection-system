import os
import pymongo
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from datetime import datetime
from bson import ObjectId
# Load environment variables from .env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "drowsiness")
COLLECTION_DRIVERS = os.getenv("COLLECTION_DRIVERS", "drivers")
COLLECTION_LOGS = os.getenv("COLLECTION_LOGS", "logs")

# MongoDB client with timeout (to avoid hanging if Atlas is unreachable)
client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

# Test connection
try:
    client.server_info()
    print("✅ MongoDB connected successfully")
except Exception as e:
    print("❌ MongoDB connection failed:", e)

# Database and collections
db = client[DB_NAME]
drivers_collection = db[COLLECTION_DRIVERS]
logs_collection = db[COLLECTION_LOGS]

# ---------------- Driver Registration/Login ----------------
def add_driver_account(driver: dict):
    """Register a new driver with hashed password."""
    driver["password"] = generate_password_hash(driver["password"])
    driver["created_at"] = datetime.utcnow()
    return drivers_collection.insert_one(driver).inserted_id

def get_driver_by_vehicle(vehicle: str):
    """Fetch driver by vehicle number."""
    return drivers_collection.find_one({"vehicle": vehicle})

def verify_driver(vehicle: str, password: str):
    """Verify driver login using vehicle number and password."""
    driver = get_driver_by_vehicle(vehicle)
    if driver and check_password_hash(driver["password"], password):
        return driver
    return None

def get_driver(driver_id: str):
    """Fetch driver by ID."""
    try:
        return drivers_collection.find_one({"_id": ObjectId(driver_id)})
    except Exception:
        return None

def get_drivers():
    """Fetch all registered drivers."""
    return list(drivers_collection.find())

# ---------------- Logs ----------------
def insert_log(event: str, driver_id: str = None):
    """Insert a log entry (e.g., Drowsy, Yawning, etc.)."""
    log_entry = {
        "event": event,
        "timestamp": datetime.utcnow()
    }
    if driver_id:
        log_entry["driver_id"] = str(driver_id)
    return logs_collection.insert_one(log_entry).inserted_id

def get_logs(limit: int = 50, driver_id: str = None):
    """Fetch logs (optionally filter by driver)."""
    query = {}
    if driver_id:
        query["driver_id"] = str(driver_id)
    return list(logs_collection.find(query).sort("_id", -1).limit(limit))



# ---------------- Emergency Contact ----------------
def get_emergency_contact(driver_id: str):
    """Return emergency contact number for a driver."""
    try:
        driver = drivers_collection.find_one({"_id": ObjectId(driver_id)})
        if driver:
            return driver.get("emergency_contact")
    except Exception as e:
        print("Error fetching emergency contact:", e)
    return None
