# ml/train.py
# Run after collecting data: python train.py

import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
from pymongo import MongoClient
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (LSTM, Dense, Dropout,
                                     Bidirectional, BatchNormalization)
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
# pyrefly: ignore [missing-import]
import matplotlib.pyplot as plt
import pickle

print("═══════════════════════════")
print("  EnergyAI LSTM Training   ")
print("═══════════════════════════")

# ── STEP 1: Load from MongoDB ──
print("\n1. Loading data from MongoDB...")
client = MongoClient("mongodb://localhost:27017/")
db     = client["energy_ai_db"]

data = list(db.sensor_readings.find({}, {"_id": 0}))

if len(data) == 0:
    print("✗ No data found. Is simulator.py running?")
    exit()

df = pd.DataFrame(data)
print(f"   Total readings loaded: {len(df)}")

if len(df) < 500:
    print("⚠ Warning: Very少 data. Run simulator for at least 1 week.")
    print("  Training will still run but accuracy may be low.")

# ── STEP 2: Feature Engineering ──
print("\n2. Engineering features...")

df["timestamp"]   = pd.to_datetime(df["timestamp"])
df                = df.sort_values("timestamp").reset_index(drop=True)

# Time features — simulator sends these patterns
df["hour"]        = df["timestamp"].dt.hour
df["minute"]      = df["timestamp"].dt.minute
df["day_of_week"] = df["timestamp"].dt.dayofweek   # 0=Mon, 6=Sun
df["is_weekend"]  = df["day_of_week"].isin([5,6]).astype(int)

# Rolling averages — use small windows that work even with less data
# window=12 means last 12 readings = last 1 minute of data
df["power_1h_avg"] = df["power"].rolling(window=12,  min_periods=1).mean()
df["power_3h_avg"] = df["power"].rolling(window=36,  min_periods=1).mean()
df["power_diff"]   = df["power"].diff().fillna(0)  # rate of change

df.dropna(inplace=True)
print(f"   Clean rows after processing: {len(df)}")

# ── STEP 3: Define features ──
# These must EXACTLY match what predict.py uses
FEATURE_COLUMNS = [
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "temperature",
    "humidity",
    "power_1h_avg",
    "power_3h_avg",
    "power_diff"
]
TARGET_COLUMN = "power"

print(f"   Features used: {FEATURE_COLUMNS}")

X_raw = df[FEATURE_COLUMNS].values
y_raw = df[[TARGET_COLUMN]].values

# ── STEP 4: Scale to 0–1 ──
print("\n3. Scaling data...")
scaler_X = MinMaxScaler()
scaler_y = MinMaxScaler()

X_scaled = scaler_X.fit_transform(X_raw)
y_scaled = scaler_y.fit_transform(y_raw)

# Save scalers — predict.py needs these exact same scalers
with open("scaler_X.pkl", "wb") as f:
    pickle.dump(scaler_X, f)
with open("scaler_y.pkl", "wb") as f:
    pickle.dump(scaler_y, f)

# Also save feature column names so predict.py can verify
import json
with open("feature_columns.json", "w") as f:
    json.dump(FEATURE_COLUMNS, f)

print("   ✓ Scalers saved: scaler_X.pkl, scaler_y.pkl")
print("   ✓ Feature list saved: feature_columns.json")

# ── STEP 5: Create sequences ──
print("\n4. Creating time sequences...")
WINDOW_SIZE = 24  # use last 24 readings as input context

def create_sequences(X, y, window):
    Xs, ys = [], []
    for i in range(len(X) - window):
        Xs.append(X[i : i + window])
        ys.append(y[i + window])
    return np.array(Xs), np.array(ys)

X_seq, y_seq = create_sequences(X_scaled, y_scaled, WINDOW_SIZE)
print(f"   Sequences created: {X_seq.shape}")

# ── STEP 6: Train/test split ──
X_train, X_test, y_train, y_test = train_test_split(
    X_seq, y_seq,
    test_size=0.2,
    shuffle=False   # IMPORTANT — never shuffle time series data
)
print(f"   Train size: {len(X_train)} | Test size: {len(X_test)}")

# ── STEP 7: Build model ──
print("\n5. Building LSTM model...")

model = Sequential([
    Bidirectional(
        LSTM(128, return_sequences=True),
        input_shape=(WINDOW_SIZE, len(FEATURE_COLUMNS))
    ),
    BatchNormalization(),
    Dropout(0.2),

    LSTM(64, return_sequences=True),
    BatchNormalization(),
    Dropout(0.2),

    LSTM(32),
    BatchNormalization(),
    Dropout(0.2),

    Dense(16, activation="relu"),
    Dense(1)
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="huber",
    metrics=["mae"]
)

model.summary()

# ── STEP 8: Train ──
print("\n6. Training... (may take 10–30 min depending on data size)")

callbacks = [
    EarlyStopping(
        monitor="val_loss",
        patience=10,
        restore_best_weights=True,
        verbose=1
    ),
    ModelCheckpoint(
        "lstm_model.h5",
        save_best_only=True,
        verbose=1
    )
]

history = model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=100,
    batch_size=32,
    callbacks=callbacks,
    verbose=1
)

# ── STEP 9: Evaluate ──
print("\n7. Evaluating model...")

y_pred_scaled = model.predict(X_test)
y_pred_real   = scaler_y.inverse_transform(y_pred_scaled)
y_test_real   = scaler_y.inverse_transform(y_test)

mae_real = np.mean(np.abs(y_test_real - y_pred_real))
mape     = np.mean(np.abs((y_test_real - y_pred_real) / (y_test_real + 1e-8))) * 100
accuracy = 100 - mape

print(f"   MAE:      {mae_real:.1f} Watts")
print(f"   Accuracy: {accuracy:.1f}%")

# ── STEP 10: Save plot ──
plt.figure(figsize=(14, 5))

plt.subplot(1, 2, 1)
plt.plot(history.history["loss"],     label="Train Loss", color="blue")
plt.plot(history.history["val_loss"], label="Val Loss",   color="orange")
plt.title("Training Loss Curve")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.legend()
plt.grid(True)

plt.subplot(1, 2, 2)
plt.plot(y_test_real[:200],  label="Actual",    color="green")
plt.plot(y_pred_real[:200],  label="Predicted", color="purple", linestyle="--")
plt.title(f"Actual vs Predicted  |  Accuracy: {accuracy:.1f}%")
plt.xlabel("Sample")
plt.ylabel("Power (W)")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig("training_results.png")
print("\n   ✓ Plot saved: training_results.png")
print(f"\n✓ Training complete!")
print(f"  Model:    lstm_model.h5")
print(f"  Accuracy: {accuracy:.1f}%")
print(f"  MAE:      {mae_real:.1f} Watts")