// frontend/script.js
const API = "";

// ── Tab titles ──
const tabTitles = {
  dashboard: "Overview Dashboard",
  prediction: "LSTM Prediction",
  history: "Energy History",
  alerts: "Active Alerts"
};

function showTab(name, btn) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  btn.classList.add("active");
  document.getElementById("tab-title").textContent = tabTitles[name];

  if (name === "history") loadHistory();
  if (name === "prediction") loadPrediction();
  if (name === "alerts") loadAlerts();
}

// ── Clock ──
setInterval(() => {
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString();
}, 1000);

// ── Live chart setup ──
const liveLabels = [];
const liveData = [];
const MAX_POINTS = 20;

const liveCtx = document.getElementById("liveChart").getContext("2d");
const liveChart = new Chart(liveCtx, {
  type: "line",
  data: {
    labels: liveLabels,
    datasets: [{
      label: "Power (W)",
      data: liveData,
      borderColor: "#00e5a0",
      backgroundColor: "rgba(0,229,160,0.08)",
      borderWidth: 2.5,
      pointRadius: 3,
      fill: true,
      tension: 0.4
    }]
  },
  options: {
    responsive: true,
    animation: { duration: 300 },
    plugins: { legend: { display: false } },
    scales: {
      x: {
        grid: { color: "rgba(255,255,255,0.05)" },
        ticks: { color: "#64748b", font: { size: 10 } }
      },
      y: {
        grid: { color: "rgba(255,255,255,0.05)" },
        ticks: {
          color: "#64748b",
          font: { size: 10 },
          callback: v => v + "W"
        }
      }
    }
  }
});

// ── Prediction chart (dashboard tab) ──
const predCtx = document.getElementById("predChart").getContext("2d");
const predChart = new Chart(predCtx, {
  type: "line",
  data: {
    labels: [],
    datasets: [{
      label: "Predicted (W)",
      data: [],
      borderColor: "#8b5cf6",
      backgroundColor: "rgba(139,92,246,0.08)",
      borderWidth: 2.5,
      borderDash: [5, 3],
      pointRadius: 4,
      fill: true,
      tension: 0.4
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: { color: "#64748b", font: { size: 10 } },
        grid: { color: "rgba(255,255,255,0.05)" }
      },
      y: {
        ticks: {
          color: "#64748b",
          font: { size: 10 },
          callback: v => v + "W"
        },
        grid: { color: "rgba(255,255,255,0.05)" }
      }
    }
  }
});

// ── Forecast chart (Prediction tab) ──
const forecastCtx = document.getElementById("forecastChart").getContext("2d");
const forecastChart = new Chart(forecastCtx, {
  type: "line",
  data: {
    labels: [],
    datasets: [{
      label: "Predicted (kW)",
      data: [],
      borderColor: "#8b5cf6",
      backgroundColor: "rgba(139,92,246,0.08)",
      borderWidth: 2.5,
      pointRadius: 4,
      fill: true,
      tension: 0.4
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: { color: "#64748b", font: { size: 10 } },
        grid: { color: "rgba(255,255,255,0.05)" }
      },
      y: {
        ticks: {
          color: "#64748b",
          font: { size: 10 },
          callback: v => v + "kW"
        },
        grid: { color: "rgba(255,255,255,0.05)" }
      }
    }
  }
});

// ══════════════════════════════════════
// FETCH LIVE STATUS
// ══════════════════════════════════════
async function fetchStatus() {
  try {
    const res = await fetch(`${API}/api/status`);
    const data = await res.json();

    if (data.error) {
      updateSystemStatus("server", true);
      updateSystemStatus("simulator", false);
      return;
    }

    // Update stat cards
    document.getElementById("stat-power").innerHTML =
      `${data.current_power_kw} <span>kW</span>`;
    document.getElementById("stat-voltage").innerHTML =
      `${data.voltage} <span>V</span>`;
    document.getElementById("stat-current").innerHTML =
      `${data.current_amps} <span>A</span>`;
    document.getElementById("stat-temp").innerHTML =
      `${data.temperature} <span>°C</span>`;
    document.getElementById("stat-humidity").textContent =
      `Humidity: ${data.humidity}%`;

    // Update live chart
    const label = new Date().toLocaleTimeString(
      [], { hour: "2-digit", minute: "2-digit", second: "2-digit" }
    );
    liveLabels.push(label);
    liveData.push(data.current_power_w);

    if (liveLabels.length > MAX_POINTS) {
      liveLabels.shift();
      liveData.shift();
    }
    liveChart.update();

    // Update system status sidebar
    updateSystemStatus("server", true);
    updateSystemStatus("simulator", data.simulator_active);

    // Generate AI suggestions
    generateSuggestions(data.current_power_kw, data.temperature);

  } catch (err) {
    // Server not reachable
    updateSystemStatus("server", false);
    updateSystemStatus("simulator", false);
  }
}

// ── Update sidebar status dots ──
function updateSystemStatus(component, isOnline) {
  let elId = `${component}-status`;
  if (component === "server") elId = "srv-status";
  if (component === "simulator") elId = "esp-status";

  const el = document.getElementById(elId);
  if (!el) return;

  if (component === "server") {
    el.textContent = isOnline ? "● Online" : "● Offline";
    el.className = isOnline ? "ok" : "warn";
  }
  if (component === "simulator") {
    el.textContent = isOnline ? "● Sending data" : "● Not running";
    el.className = isOnline ? "ok" : "warn";
  }
}

// ══════════════════════════════════════
// AI SUGGESTIONS
// ══════════════════════════════════════
function generateSuggestions(powerKw, temp) {
  const list = document.getElementById("suggestions-list");
  const suggestions = [];

  if (powerKw > 5) {
    suggestions.push({
      icon: "❄️", priority: "high",
      text: `High load detected (${powerKw} kW). Consider reducing
             AC temperature by 2°C. Estimated saving: ₹80–120/day.`
    });
  }

  if (temp > 30) {
    suggestions.push({
      icon: "🌡️", priority: "medium",
      text: `Room temperature is ${temp}°C. Cooling systems
             are working harder than usual.`
    });
  }

  const hour = new Date().getHours();
  if (hour >= 18 && hour <= 21) {
    suggestions.push({
      icon: "⚡", priority: "medium",
      text: `Peak billing hours active (6–9 PM). Postpone water heating
             and heavy equipment to after 10 PM to reduce tariff cost.`
    });
  }

  if (powerKw >= 1 && powerKw <= 3) {
    suggestions.push({
      icon: "✅", priority: "low",
      text: `Power usage is moderate (${powerKw} kW). 
             System running within normal range.`
    });
  }

  if (powerKw < 1) {
    suggestions.push({
      icon: "😴", priority: "low",
      text: `Very low consumption (${powerKw} kW). 
             Off-peak or night hours — good time to run scheduled tasks.`
    });
  }

  if (suggestions.length === 0) {
    suggestions.push({
      icon: "📊", priority: "low",
      text: "Energy usage is within normal range. No action needed."
    });
  }

  list.innerHTML = suggestions.map(s => `
    <div class="suggest-item ${s.priority}">
      <span class="suggest-icon">${s.icon}</span>
      <div>${s.text}</div>
    </div>
  `).join("");
}

// ══════════════════════════════════════
// ALERTS
// ══════════════════════════════════════
async function fetchAlerts() {
  try {
    const res = await fetch(`${API}/api/alerts`);
    const data = await res.json();

    const count = data.count || 0;
    document.getElementById("alert-count").textContent = count;

    const section = document.getElementById("alert-section");
    if (count > 0 && section) {
      section.style.display = "block";
      const first = data.alerts[0];
      document.getElementById("alert-msg").textContent = first.message;
    } else if (section) {
      section.style.display = "none";
    }
  } catch (err) {
    // server offline
  }
}

// ══════════════════════════════════════
// HISTORY TABLE
// ══════════════════════════════════════
async function loadHistory() {
  try {
    const res = await fetch(`${API}/api/readings?limit=20`);
    const data = await res.json();
    const tbody = document.getElementById("history-tbody");

    if (!data.readings || data.readings.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="color:#64748b;text-align:center">
            No data yet. Is simulator.py running?
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = data.readings.map(r => {
      const time = new Date(r.timestamp + "Z").toLocaleTimeString();
      return `<tr>
        <td>${time}</td>
        <td>${r.voltage ?? "--"}</td>
        <td>${r.current ?? "--"}</td>
        <td>${r.power ?? "--"}</td>
        <td>${r.temperature ?? "--"}</td>
      </tr>`;
    }).join("");

  } catch (err) {
    document.getElementById("history-tbody").innerHTML =
      `<tr><td colspan="5" style="color:#64748b">Server offline.</td></tr>`;
  }
}

// ══════════════════════════════════════
// PREDICTION TAB
// ══════════════════════════════════════
async function loadPrediction() {
  try {
    const res = await fetch(`${API}/api/prediction`);
    const data = await res.json();

    if (data.message || !data.predictions) {
      document.getElementById("pred-tbody").innerHTML =
        `<tr><td colspan="3" style="color:#64748b">
          ${data.message || "No predictions yet. Run ml/predict.py first."}
        </td></tr>`;
      return;
    }

    // Update small prediction chart on dashboard
    const labels = data.predictions.map(p => `+${p.step}h`);
    const valuesW = data.predictions.map(p => p.power_w);
    const valuesKW = data.predictions.map(p => p.power_kw);

    predChart.data.labels = labels;
    predChart.data.datasets[0].data = valuesW;
    predChart.update();

    // Update large forecast chart
    forecastChart.data.labels = labels;
    forecastChart.data.datasets[0].data = valuesKW;
    forecastChart.update();

    // Fill prediction table
    const tbody = document.getElementById("pred-tbody");

    // Dynamic logic based on Average + Variance (Standard Deviation)
    const sumKw = data.predictions.reduce((acc, p) => acc + p.power_kw, 0);
    const avgKw = sumKw / data.predictions.length;

    const variance = data.predictions.reduce((acc, p) => acc + Math.pow(p.power_kw - avgKw, 2), 0) / data.predictions.length;
    let stdDev = Math.sqrt(variance);
    if (stdDev < 0.02) stdDev = 0.02; // Minimum variation

    const thresholdPeak = avgKw + (stdDev * 1.5); // Peak is 1.5 standard deviations above average
    const thresholdHigh = avgKw + (stdDev * 0.8); // High is 0.8 standard deviations above average

    tbody.innerHTML = data.predictions.map((p, i, arr) => {
      let status = "Normal";
      let bg = "rgba(0, 229, 160, 0.15)";
      let color = "#00e5a0";

      if (stdDev <= 0.02 && Math.abs(p.power_kw - avgKw) < 0.05) {
        // Almost flat line, no real peaks
        status = "Normal";
      } else if (p.power_kw >= thresholdPeak) {
        status = "Peak"; color = "#ef4444"; bg = "rgba(239, 68, 68, 0.15)";
      } else if (p.power_kw >= thresholdHigh) {
        status = "High"; color = "#f97316"; bg = "rgba(249, 115, 22, 0.15)";
      } else if (i > 0 && p.power_kw > arr[i - 1].power_kw) {
        status = "Rising"; color = "#eab308"; bg = "rgba(234, 179, 8, 0.15)";
      }

      let estCost = (p.power_kw * 8.5).toFixed(2); // Assuming ₹8.5 per kWh

      return `
      <tr>
        <td>${new Date(p.time + "Z").toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
        <td>${p.power_kw.toFixed(3)} kW</td>
        <td>₹${estCost}</td>
        <td><span style="background: ${bg}; color: ${color}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">${status}</span></td>
      </tr>`;
    }).join("");

    // Calculate overall cost and AI insights
    let totalKwh = data.predictions.reduce((sum, p) => sum + p.power_kw, 0);
    let totalCost = totalKwh * 8.5; // Rs. 8.5 per kWh

    // Calculate meaningful savings based on peak/high threshold load shifting
    let potentialSavings = 0;
    let savingsReason = "";

    data.predictions.forEach(p => {
      if (p.power_kw >= thresholdPeak) {
        // Assume 25% savings by shifting peak load to off-peak hours
        potentialSavings += (p.power_kw * 8.5) * 0.25;
      } else if (p.power_kw >= thresholdHigh) {
        // Assume 15% savings by optimizing high load
        potentialSavings += (p.power_kw * 8.5) * 0.15;
      }
    });

    if (potentialSavings > 0) {
      savingsReason = "Based on reducing Peak usage by 25% & High usage by 15% through load shifting.";
    } else {
      // If no peaks, offer a baseline 5% standby optimization
      potentialSavings = totalCost * 0.05;
      savingsReason = "Based on a baseline 5% optimization of standby devices (no peak usage detected).";
    }

    let insightsHtml = `
      <style>@keyframes spin { 100% { transform: rotate(360deg); } }</style>
      <div style="display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 200px; background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 8px; padding: 16px; display: flex; align-items: center; gap: 12px;">
          <div style="font-size: 28px;">💰</div>
          <div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Est. Cost (Next 12h)</div>
            <div style="font-size: 28px; font-weight: bold; color: #f8fafc; margin-top: 4px;">₹${totalCost.toFixed(2)}</div>
          </div>
        </div>
        <div style="flex: 1; min-width: 200px; background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; padding: 16px; display: flex; align-items: center; gap: 12px;">
          <div style="font-size: 28px;">📉</div>
          <div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Potential Savings</div>
            <div style="font-size: 28px; font-weight: bold; color: #10b981; margin-top: 4px;">~₹${potentialSavings.toFixed(2)}</div>
            <div style="font-size: 10px; color: #94a3b8; margin-top: 6px; line-height: 1.3; max-width: 250px;">${savingsReason}</div>
          </div>
        </div>
      </div>
      
      <div id="ai-insights-container">
        <div style="color:#64748b; font-size: 13px; display: flex; align-items: center; gap: 10px; padding: 16px;">
           <span style="display:inline-block; width:16px; height:16px; border:2px solid #8b5cf6; border-top-color:transparent; border-radius:50%; animation: spin 1s linear infinite;"></span>
           Generating AI Insights via Gemini...
        </div>
      </div>
    `;

    document.getElementById("pred-insights").innerHTML = insightsHtml;

    // Call backend API for Gemini insights
    try {
      const aiRes = await fetch(`${API}/api/ai-insights`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ predictions: data.predictions.map(p => p.power_kw) })
      });
      const aiData = await aiRes.json();
      if (aiData.html) {
        document.getElementById("ai-insights-container").innerHTML = aiData.html;
      }
    } catch (e) {
      console.log("Failed to load AI insights", e);
      document.getElementById("ai-insights-container").innerHTML = `
        <div class="suggest-item" style="border-left: 4px solid #ef4444; background: rgba(239, 68, 68, 0.05);">
          <span class="suggest-icon">⚠️</span>
          <div><strong>Connection Error:</strong> Could not connect to the backend AI service.</div>
        </div>
       `;
    }

  } catch (err) {
    console.log("Prediction error:", err.message);
  }
}

// ══════════════════════════════════════
// ALERTS TAB
// ══════════════════════════════════════
async function loadAlerts() {
  try {
    const res = await fetch(`${API}/api/alerts`);
    const data = await res.json();
    const div = document.getElementById("alerts-list");

    if (!data.alerts || data.count === 0) {
      div.innerHTML = `
        <p style="color:#64748b;font-size:13px">
          No active alerts. System running normally. ✓
        </p>`;
      return;
    }

    div.innerHTML = data.alerts.map(a => `
      <div class="alert-box" style="margin-bottom:10px">
        <span>🚨</span>
        <div>
          <div class="alert-title">${a.severity} — ${a.device}</div>
          <div class="alert-msg">${a.message}</div>
          <div style="font-size:10px;color:#475569;margin-top:4px">
            ${new Date(a.timestamp + "Z").toLocaleString()}
          </div>
        </div>
      </div>
    `).join("");

  } catch (err) {
    document.getElementById("alerts-list").innerHTML =
      `<p style="color:#64748b">Server offline.</p>`;
  }
}

// ══════════════════════════════════════
// START
// ══════════════════════════════════════
fetchStatus();
setInterval(fetchStatus, 5000);   // live data every 5 seconds
fetchAlerts();
setInterval(fetchAlerts, 10000);   // alerts every 10 seconds