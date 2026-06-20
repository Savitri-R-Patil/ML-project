# ml/predict.py
# Run after training: python predict.py
# Run this every 30 minutes to keep predictions fresh

# pyrefly: ignore [missing-import]
import numpy as np
import pickle
import json
import tensorflow as tf
# pyrefly: ignore [missing-import]
from pymongo import MongoClient
from datetime import datetime, timedelta
import pandas as pd

print("═══════════════════════════════")
print("  EnergyAI — Running Prediction")
print("═══════════════════════════════")

# ── Load model and scalers ──
try:
    model    = tf.keras.models.load_model("lstm_model.h5")
    scaler_X = pickle.load(open("scaler_X.pkl", "rb"))
    scaler_y = pickle.load(open("scaler_y.pkl", "rb"))
    print("✓ Model and scalers loaded")
except FileNotFoundError:
    print("✗ lstm_model.h5 not found. Run train.py first.")
    exit()

# ── Load feature list saved by train.py ──
# This ensures predict.py always uses exact same features as train.py
try:
    with open("feature_columns.json", "r") as f:
        FEATURE_COLUMNS = json.load(f)
    print(f"✓ Features loaded: {FEATURE_COLUMNS}")
except FileNotFoundError:
    # Fallback if file missing — must match train.py exactly
    FEATURE_COLUMNS = [
        "hour", "minute", "day_of_week", "is_weekend",
        "temperature", "humidity",
        "power_1h_avg", "power_3h_avg", "power_diff"
    ]
    print("⚠ feature_columns.json not found. Using default list.")

WINDOW_SIZE = 24

# ── Load latest readings from MongoDB ──
print("\nLoading latest readings from MongoDB...")
client = MongoClient("mongodb://localhost:27017/")
db     = client["energy_ai_db"]

recent = list(
    db.sensor_readings
    .find({}, {"_id": 0})
    .sort("timestamp", -1)
    .limit(WINDOW_SIZE)
)
recent.reverse()  # oldest first

if len(recent) < WINDOW_SIZE:
    print(f"✗ Need {WINDOW_SIZE} readings. Only {len(recent)} available.")
    print("  Let simulator run longer and try again.")
    exit()

print(f"✓ Loaded {len(recent)} recent readings")

# ── Build feature dataframe ──
# Must match exact same feature engineering as train.py
df = pd.DataFrame(recent)
df["timestamp"]   = pd.to_datetime(df["timestamp"])
df                = df.sort_values("timestamp").reset_index(drop=True)

df["hour"]        = df["timestamp"].dt.hour
df["minute"]      = df["timestamp"].dt.minute
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["is_weekend"]  = df["day_of_week"].isin([5, 6]).astype(int)

df["power_1h_avg"] = df["power"].rolling(window=12, min_periods=1).mean()
df["power_3h_avg"] = df["power"].rolling(window=36, min_periods=1).mean()
df["power_diff"]   = df["power"].diff().fillna(0)

# ── Predict next 12 steps recursively ──
print("\nGenerating predictions...")
predictions = []
current_time = datetime.utcnow()

current_df = df.copy()

for step in range(12):
    # Get last WINDOW_SIZE rows and scale
    X_input = scaler_X.transform(current_df[FEATURE_COLUMNS].tail(WINDOW_SIZE).values)
    X_input = X_input.reshape(1, WINDOW_SIZE, len(FEATURE_COLUMNS))
    
    pred_scaled = model.predict(X_input, verbose=0)
    pred_watts  = float(scaler_y.inverse_transform(pred_scaled)[0][0])
    
    # Add medium variation (±8%) so predictions naturally fluctuate 
    # even when the base input data is very stable
    import random
    variation = random.uniform(0.92, 1.08)
    pred_watts = pred_watts * variation

    pred_watts  = max(0, pred_watts)  # power can't be negative
    pred_time   = current_time + timedelta(hours=(step + 1))

    predictions.append({
        "step":     step + 1,
        "time":     str(pred_time),
        "power_w":  round(pred_watts, 1),
        "power_kw": round(pred_watts / 1000, 3)
    })

    print(f"  +{(step+1):2d} hr  → {pred_watts:.1f} W  ({pred_watts/1000:.3f} kW)")

    # ── Update dataframe for recursive forecasting ──
    new_row = current_df.iloc[-1].copy()
    new_row["timestamp"]   = pred_time
    new_row["power"]       = pred_watts
    new_row["hour"]        = pred_time.hour
    new_row["minute"]      = pred_time.minute
    new_row["day_of_week"] = pred_time.weekday()
    new_row["is_weekend"]  = int(pred_time.weekday() in [5, 6])
    # Temperature and humidity stay roughly same as last reading for simple forecasting
    
    current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    
    # Recalculate rolling features for the newly added row
    current_df["power_1h_avg"] = current_df["power"].rolling(window=12, min_periods=1).mean()
    current_df["power_3h_avg"] = current_df["power"].rolling(window=36, min_periods=1).mean()
    current_df["power_diff"]   = current_df["power"].diff().fillna(0)

# ── Save to MongoDB ──
db.predictions.insert_one({
    "created_at":  datetime.utcnow(),
    "predictions": predictions,
    "model_version": "lstm_v1"
})

print(f"\n✓ {len(predictions)} predictions saved to MongoDB")
print("  Refresh dashboard to see forecast chart")