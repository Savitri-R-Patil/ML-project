# database.py
# pyrefly: ignore [missing-import]
from pymongo import MongoClient
from datetime import datetime

# Connect to MongoDB (must be running on your PC)
# Install MongoDB from: https://www.mongodb.com/try/download/community
client = MongoClient("mongodb://localhost:27017/")

# This creates the database and collections automatically
db = client["energy_ai_db"]

readings_collection    = db["sensor_readings"]
predictions_collection = db["predictions"]
alerts_collection      = db["alerts"]

def save_reading(data: dict):
    """Save one sensor reading to MongoDB"""
    data["timestamp"] = datetime.utcnow()
    data["is_anomaly"] = False  # anomaly detection adds this later
    result = readings_collection.insert_one(data)
    return str(result.inserted_id)

def get_latest_readings(limit=100):
    """Get last N readings, newest first"""
    readings = readings_collection.find(
        {},
        {"_id": 0}  # don't return MongoDB internal ID
    ).sort("timestamp", -1).limit(limit)
    return list(readings)

def get_readings_for_training():
    """Get all readings for ML training"""
    readings = readings_collection.find({}, {"_id": 0})
    return list(readings)

def save_prediction(predicted_values: list):
    """Save LSTM prediction result"""
    predictions_collection.insert_one({
        "created_at": datetime.utcnow(),
        "predictions": predicted_values
    })

def save_alert(device, message, severity):
    """Save anomaly alert"""
    alerts_collection.insert_one({
        "timestamp": datetime.utcnow(),
        "device": device,
        "message": message,
        "severity": severity,
        "resolved": False
    })

def get_active_alerts():
    """Get unresolved alerts"""
    return list(alerts_collection.find(
        {"resolved": False},
        {"_id": 0}
    ))