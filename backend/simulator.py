# simulator.py
# Replaces ESP32 hardware
# Generates realistic electricity data and sends to FastAPI
# Run: python simulator.py

import requests
import time
import math
import random
from datetime import datetime, timedelta

SERVER_URL = "http://localhost:8000/api/sensor"

print("═══════════════════════════════════")
print("  EnergyAI — Data Simulator")
print("  Replaces ESP32 Hardware")
print("═══════════════════════════════════")
print(f"Sending to: {SERVER_URL}")
print("Press Ctrl+C to stop\n")

reading_count = 0

def get_realistic_power(hour, minute, day_of_week):
    """
    Generates realistic power based on time of day.
    Mimics a real college building's consumption pattern.
    """
    # Base load (always on: servers, fridges, emergency lights)
    base = 800  # 800 Watts always

    # Time-based pattern
    time_decimal = hour + minute / 60.0

    # Early morning (12am - 6am): very low
    if 0 <= time_decimal < 6:
        time_factor = 0.1 + 0.05 * math.sin(time_decimal * math.pi / 6)

    # Morning ramp up (6am - 9am): people arriving
    elif 6 <= time_decimal < 9:
        time_factor = 0.1 + 0.6 * ((time_decimal - 6) / 3)

    # Working hours (9am - 5pm): full load
    elif 9 <= time_decimal < 17:
        # Slight dip at lunch (12pm - 1pm)
        if 12 <= time_decimal < 13:
            time_factor = 0.7
        else:
            time_factor = 0.85 + 0.1 * math.sin(time_decimal * math.pi / 8)

    # Evening peak (5pm - 9pm): max load
    elif 17 <= time_decimal < 21:
        time_factor = 0.9 + 0.1 * math.sin((time_decimal - 17) * math.pi / 4)

    # Night wind down (9pm - 12am)
    else:
        time_factor = 0.9 - 0.8 * ((time_decimal - 21) / 3)

    # Weekend: lower usage (40% less)
    if day_of_week >= 5:  # Saturday=5, Sunday=6
        time_factor *= 0.6

    # Max power capacity of building
    max_power = 8000  # 8 kW

    power = base + (max_power - base) * time_factor

    # Add realistic random noise (±5%)
    noise = random.uniform(-0.05, 0.05)
    power = power * (1 + noise)

    return round(power, 1)

def get_realistic_voltage():
    """Indian AC voltage: 220V ± small fluctuation"""
    return round(random.uniform(218.0, 223.5), 1)

def get_realistic_temperature(hour):
    """Temperature follows daily cycle"""
    # Cooler at night, hotter in afternoon
    base_temp = 26.0
    variation = 5.0 * math.sin((hour - 6) * math.pi / 12)
    noise = random.uniform(-0.5, 0.5)
    return round(base_temp + variation + noise, 1)

def get_realistic_humidity(hour, temperature):
    """Humidity inversely related to temperature"""
    base_humidity = 65.0
    temp_effect = -(temperature - 26) * 1.5
    noise = random.uniform(-2, 2)
    humidity = base_humidity + temp_effect + noise
    return round(max(30, min(95, humidity)), 1)

def inject_anomaly(power):
    """
    Randomly inject anomalies (5% chance).
    Simulates: AC fault, equipment left on, power spike
    """
    if random.random() < 0.05:  # 5% chance
        anomaly_type = random.choice(["spike", "drop"])
        if anomaly_type == "spike":
            # Sudden 30-50% increase
            factor = random.uniform(1.3, 1.5)
            print(f"  ⚠️  ANOMALY INJECTED: Power spike ({factor:.1f}x normal)")
        else:
            # Sudden drop (equipment failure simulation)
            factor = random.uniform(0.3, 0.6)
            print(f"  ⚠️  ANOMALY INJECTED: Power drop ({factor:.1f}x normal)")
        return round(power * factor, 1)
    return power

def send_reading(data):
    """Send one reading to FastAPI server"""
    try:
        response = requests.post(
            SERVER_URL,
            json=data,
            timeout=5
        )
        if response.status_code == 200:
            return True
        else:
            print(f"  ✗ Server error: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot connect to server. Is FastAPI running?")
        print("    Run: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

# ── MAIN LOOP ──
while True:
    now        = datetime.now()
    hour       = now.hour
    minute     = now.minute
    day_of_week= now.weekday()

    # Generate sensor values
    power       = get_realistic_power(hour, minute, day_of_week)
    power       = inject_anomaly(power)
    voltage     = get_realistic_voltage()
    current     = round(power / voltage, 3)
    energy_kwh  = round(power / 1000, 4)
    temperature = get_realistic_temperature(hour)
    humidity    = get_realistic_humidity(hour, temperature)

    data = {
        "device_id":   "simulator_block_a",
        "voltage":     voltage,
        "current":     current,
        "power":       power,
        "energy_kwh":  energy_kwh,
        "temperature": temperature,
        "humidity":    humidity
    }

    reading_count += 1
    success = send_reading(data)

    # Print status
    status_icon = "✓" if success else "✗"
    print(
        f"[{now.strftime('%H:%M:%S')}] #{reading_count} {status_icon} | "
        f"{power}W | {voltage}V | {current}A | "
        f"{temperature}°C | {humidity}%"
    )

    time.sleep(1)  # send every 5 seconds, same as ESP32