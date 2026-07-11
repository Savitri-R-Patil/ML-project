# backend/main.py
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from database import (save_reading, get_latest_readings,
                      save_alert, get_active_alerts)
from datetime import datetime
import statistics
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

try:
    # pyrefly: ignore [missing-import]
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

app = FastAPI(title="EnergyAI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



# Tracks last time simulator sent data
last_simulator_ping = {"time": None}

class SensorReading(BaseModel):
    device_id:   str
    voltage:     float
    current:     float
    power:       float
    energy_kwh:  float
    temperature: float
    humidity:    float

# ── Route 1: Simulator posts data here ──
@app.post("/api/sensor")
async def receive_sensor_data(reading: SensorReading):
    data = reading.dict()

    # Record simulator is alive
    last_simulator_ping["time"] = datetime.utcnow()

    # Detect anomaly before saving
    check_anomaly(data)

    # Save to MongoDB
    doc_id = save_reading(data)

    print(f"✓ [{data['device_id']}] {data['power']}W")
    return {"status": "saved", "id": doc_id}

# ── Route 2: Live status for dashboard ──
@app.get("/api/status")
async def get_status():
    readings = get_latest_readings(10)

    if not readings:
        return {
            "error": "No data yet",
            "hint": "Make sure simulator.py is running"
        }

    latest = readings[0]
    powers = [r["power"] for r in readings if "power" in r]

    # Check if simulator is still sending
    sim_alive = False
    if last_simulator_ping["time"]:
        diff = (datetime.utcnow() - last_simulator_ping["time"]).seconds
        sim_alive = diff < 15  # alive if sent data in last 15 seconds

    return {
        "current_power_w":   latest.get("power", 0),
        "current_power_kw":  round(latest.get("power", 0) / 1000, 2),
        "voltage":           latest.get("voltage", 0),
        "current_amps":      latest.get("current", 0),
        "temperature":       latest.get("temperature", 0),
        "humidity":          latest.get("humidity", 0),
        "avg_power_10min":   round(statistics.mean(powers), 1) if powers else 0,
        "simulator_active":  sim_alive,
        "last_updated":      str(latest.get("timestamp", ""))
    }

# ── Route 3: Latest readings for history table ──
@app.get("/api/readings")
async def get_readings(limit: int = 50):
    readings = get_latest_readings(limit)
    for r in readings:
        if "timestamp" in r:
            r["timestamp"] = str(r["timestamp"])
    return {"readings": readings, "count": len(readings)}

# ── Route 4: Active alerts ──
@app.get("/api/alerts")
async def get_alerts():
    alerts = get_active_alerts()
    for a in alerts:
        if "timestamp" in a:
            a["timestamp"] = str(a["timestamp"])
    return {"alerts": alerts, "count": len(alerts)}

# ── Route 5: Latest prediction ──
@app.get("/api/prediction")
async def get_prediction():
    from database import predictions_collection
    pred = predictions_collection.find_one(
        {}, {"_id": 0},
        sort=[("created_at", -1)]
    )
    if pred and "created_at" in pred:
        pred["created_at"] = str(pred["created_at"])
    return pred or {
        "message": "No predictions yet. Run ml/predict.py first."
    }

# ── Route 6: Gemini AI Insights ──
class PredictionData(BaseModel):
    predictions: list

@app.post("/api/ai-insights")
async def generate_ai_insights(data: PredictionData):
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not HAS_GENAI or not api_key:
        return {
            "html": """
            <div class="suggest-item" style="border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.05); margin-bottom: 10px;">
              <span class="suggest-icon">⚠️</span>
              <div><strong>Gemini AI Not Configured:</strong> The system is currently using fallback logic. To get dynamic AI insights, set your <code>GEMINI_API_KEY</code> environment variable.</div>
            </div>
            """
        }
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        prompt = f"""
        You are an AI energy advisor analyzing a building's 12-hour energy forecast.
        The user has predicted hourly power consumption (in kW): {data.predictions}.
        Provide exactly 3 very short, 1-sentence recommendations for saving money based on this data.
        Keep it extremely concise. Do not write long paragraphs.
        Format your response as pure HTML using this structure for each point:
        <div class="suggest-item" style="border-left: 4px solid #3b82f6; background: rgba(59, 130, 246, 0.05); margin-bottom: 10px;">
          <span class="suggest-icon">💡</span>
          <div><strong>[Catchy Title]:</strong> [1-sentence recommendation]</div>
        </div>
        Do not include ```html or any markdown wrappers, just return the raw HTML string.
        """
        response = model.generate_content(prompt)
        return {"html": response.text.replace("```html", "").replace("```", "").strip()}
    except Exception as e:
        return {"error": str(e), "html": f"<div style='color:red'>AI Error: {str(e)}</div>"}

# ── Anomaly detection ──
def check_anomaly(new_reading: dict):
    recent = get_latest_readings(50)
    if len(recent) < 10:
        return

    powers = [r["power"] for r in recent if "power" in r]
    if not powers:
        return

    mean  = statistics.mean(powers)
    stdev = statistics.stdev(powers) if len(powers) > 1 else 1

    if stdev > 0:
        z = (new_reading["power"] - mean) / stdev
        if z > 2.5:
            severity = "HIGH" if z > 3.5 else "MEDIUM"
            save_alert(
                device   = new_reading.get("device_id", "simulator"),
                message  = (
                    f"Power {new_reading['power']}W is {z:.1f}σ "
                    f"above normal ({mean:.1f}W avg)"
                ),
                severity = severity
            )
            print(f"🚨 Anomaly: {severity} — {new_reading['power']}W")

# Serve frontend directly on root using absolute paths to prevent directory errors on cloud hosting
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Get the absolute path to the frontend folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")

if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)