# simulator.py
# Replaces ESP32 hardware
# Generates realistic electricity data

import requests
import time
import math
import random
import os
from datetime import datetime

port = os.getenv("PORT", "8000")
SERVER_URL = os.getenv("SERVER_URL", f"http://localhost:{port}/api/sensor")

reading_count = 0

def get_realistic_power(hour, minute, day_of_week):
    base = 800
    time_decimal = hour + minute / 60.0

    if 0 <= time_decimal < 6:
        time_factor = 0.1 + 0.05 * math.sin(time_decimal * math.pi / 6)
    elif 6 <= time_decimal < 9:
        time_factor = 0.1 + 0.6 * ((time_decimal - 6) / 3)
    elif 9 <= time_decimal < 17:
        if 12 <= time_decimal < 13:
            time_factor = 0.7
        else:
            time_factor = 0.85 + 0.1 * math.sin(time_decimal * math.pi / 8)
    elif 17 <= time_decimal < 21:
        time_factor = 0.9 + 0.1 * math.sin((time_decimal - 17) * math.pi / 4)
    else:
        time_factor = 0.9 - 0.8 * ((time_decimal - 21) / 3)

    if day_of_week >= 5:
        time_factor *= 0.6

    max_power = 8000
    power = base + (max_power - base) * time_factor
    noise = random.uniform(-0.05, 0.05)
    power = power * (1 + noise)
    return round(power, 1)

def get_realistic_voltage():
    return round(random.uniform(218.0, 223.5), 1)

def get_realistic_temperature(hour):
    base_temp = 26.0
    variation = 5.0 * math.sin((hour - 6) * math.pi / 12)
    noise = random.uniform(-0.5, 0.5)
    return round(base_temp + variation + noise, 1)

def get_realistic_humidity(hour, temperature):
    base_humidity = 65.0
    temp_effect = -(temperature - 26) * 1.5
    noise = random.uniform(-2, 2)
    humidity = base_humidity + temp_effect + noise
    return round(max(30, min(95, humidity)), 1)

def inject_anomaly(power):
    if random.random() < 0.05:
        anomaly_type = random.choice(["spike", "drop"])
        if anomaly_type == "spike":
            factor = random.uniform(1.3, 1.5)
            print(f"  \u26a0\ufe0f  ANOMALY INJECTED: Power spike ({factor:.1f}x normal)")
        else:
            factor = random.uniform(0.3, 0.6)
            print(f"  \u26a0\ufe0f  ANOMALY INJECTED: Power drop ({factor:.1f}x normal)")
        return round(power * factor, 1)
    return power

def generate_one_reading():
    """Generate a single simulated reading - used when main.py imports this directly."""
    now = datetime.now()
    hour, minute, day_of_week = now.hour, now.minute, now.weekday()

    power = get_realistic_power(hour, minute, day_of_week)
    power = inject_anomaly(power)
    voltage = get_realistic_voltage()
    current = round(power / voltage, 3)
    energy_kwh = round(power / 1000, 4)
    temperature = get_realistic_temperature(hour)
    humidity = get_realistic_humidity(hour, temperature)

    return {
        "device_id": "simulator_block_a",
        "voltage": voltage,
        "current": current,
        "power": power,
        "energy_kwh": energy_kwh,
        "temperature": temperature,
        "humidity": humidity
    }

def send_reading(data):
    """Only used when running simulator.py standalone (local testing)"""
    try:
        response = requests.post(SERVER_URL, json=data, timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("  \u2717 Cannot connect to server. Is FastAPI running?")
        return False
    except Exception as e:
        print(f"  \u2717 Error: {e}")
        return False

# MAIN LOOP - only runs when you do `python simulator.py` directly
if __name__ == "__main__":
    print("===================================")
    print("  EnergyAI - Data Simulator")
    print("===================================")
    print(f"Sending to: {SERVER_URL}")
    print("Press Ctrl+C to stop\n")

    while True:
        data = generate_one_reading()
        reading_count += 1
        success = send_reading(data)
        status_icon = "\u2713" if success else "\u2717"
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] #{reading_count} {status_icon} | "
            f"{data['power']}W | {data['voltage']}V | {data['current']}A | "
            f"{data['temperature']}\u00b0C | {data['humidity']}%"
        )
        time.sleep(1)