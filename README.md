# EnergyAI Dashboard

EnergyAI is a smart monitoring framework that uses Machine Learning (LSTM) and AI (Gemini) to track, forecast, and optimize energy consumption.

## Project Structure

- **`backend/`**: A FastAPI application that serves as the core of the system.
  - `main.py`: The main API server providing endpoints for data ingestion, dashboard status, and AI insights using Google Gemini.
  - `simulator.py`: A script that simulates live energy sensor data and sends it to the backend.
  - `database.py`: Handles data persistence using MongoDB.
- **`frontend/`**: A modern HTML/CSS/JS dashboard that visualizes real-time metrics, historical data, and AI predictions using Chart.js.
- **`ml/`**: The Machine Learning pipeline.
  - `train.py`: Trains an LSTM neural network on collected sensor data to predict future power consumption.
  - `predict.py`: Uses the trained model to generate hourly energy forecasts.

## Prerequisites

- Python 3.x
- MongoDB (running locally on `localhost:27017`)

## Running the Application

To run the full stack, you'll need multiple terminal instances.

### 1. Start the Data Simulator
This simulates an energy sensor sending data to the system.
```bash
cd backend
python simulator.py
```

### 2. Start the Backend API Server
This runs the main FastAPI application.
```bash
cd backend
uvicorn main:app --reload
```
Once running, the frontend dashboard is automatically served at:
[http://localhost:8000/dashboard/index.html](http://localhost:8000/dashboard/index.html)

### 3. Machine Learning (Optional, but required for Predictions)
After letting the simulator run for some time to collect data in MongoDB, you can train the prediction model:
```bash
cd ml
python train.py
```
To generate predictions for the dashboard:
```bash
cd ml
python predict.py
```

## Environment Variables

Create a `.env` file in the `backend/` directory to configure optional services:

- `GEMINI_API_KEY`: Set this to your Google Gemini API key to enable AI-generated energy saving suggestions on the dashboard.
