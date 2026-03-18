// --- CSRF helper for Django ---
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}
const csrftoken = getCookie("csrftoken");

// --- Predict Final Average ---
async function predictFinalAverage() {
  const avg = parseFloat(document.querySelector("#avg_so_far").value);
  const credits = parseFloat(document.querySelector("#credits_done").value);
  const res = await fetch("/predict_final_average/", {
    method: "POST",
    headers: { "X-CSRFToken": csrftoken },
    body: new URLSearchParams({ avg_so_far: avg, credits_done: credits }),
  });
  const data = await res.json();

  if (data.error) {
    Toastify({ text: data.error, backgroundColor: "#ef4444", duration: 3000 }).showToast();
    return;
  }

  document.querySelector("#predicted_output").innerHTML = `
    <div class="p-3 rounded" style="background: var(--card);">
      <strong>${data.predicted_classification}</strong><br>
      Predicted Average: ${data.predicted_average}%<br>
      Mode: ${data.mode}<br>
      Confidence: ${data.confidence !== undefined ? data.confidence : "n/a"}%
    </div>
  `;
  Toastify({ text: "Prediction successful ✅", duration: 2000 }).showToast();
}

// --- Predict What-If Multi Scenarios ---
async function predictWhatIf() {
  const rows = Array.from(document.querySelectorAll(".sim-row"));
  const sims = rows.map(row => ({
    mark: parseFloat(row.querySelector(".sim-mark").value),
    credits: parseFloat(row.querySelector(".sim-credits").value),
  }));

  const res = await fetch("/predict_what_if/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
    body: JSON.stringify({ sims }),
  });
  const data = await res.json();

  if (data.error) {
    Toastify({ text: data.error, backgroundColor: "#ef4444", duration: 3500 }).showToast();
    return;
  }

  // Update chart
  if (window.whatIfChart) {
    whatIfChart.destroy();
  }

  const ctx = document.getElementById("whatIfChart").getContext("2d");
  window.whatIfChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.classifications,
      datasets: [{
        label: "Predicted Averages",
        data: data.predicted_points,
        borderWidth: 2,
        fill: false
      }]
    },
    options: { scales: { y: { beginAtZero: true, max: 100 } } }
  });

  Toastify({ text: "What-If simulation complete 🎯", duration: 2500 }).showToast();
}

// --- Save Prediction to History ---
async function savePrediction(predicted_average, classification) {
  const res = await fetch("/save_simulation/", {
    method: "POST",
    headers: { "X-CSRFToken": csrftoken },
    body: new URLSearchParams({
      predicted_average,
      classification,
      notes: "Saved automatically",
    }),
  });
  const data = await res.json();
  if (data.success) {
    Toastify({ text: "Simulation saved ✅", duration: 2000 }).showToast();
  }
}
