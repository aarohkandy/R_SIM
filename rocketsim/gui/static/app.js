const state = {
  runs: [],
  selectedRun: null,
  detail: null,
  activeView: "overview",
};

const els = {
  runList: document.getElementById("runList"),
  statusText: document.getElementById("statusText"),
  metricGrid: document.getElementById("metricGrid"),
  animationMount: document.getElementById("animationMount"),
  manifestPreview: document.getElementById("manifestPreview"),
  flightPlots: document.getElementById("flightPlots"),
  allPlots: document.getElementById("allPlots"),
  thermalPlots: document.getElementById("thermalPlots"),
  thermalSummary: document.getElementById("thermalSummary"),
  structuralPlots: document.getElementById("structuralPlots"),
  structuralSummary: document.getElementById("structuralSummary"),
  telemetryTable: document.getElementById("telemetryTable"),
  inspectorContent: document.getElementById("inspectorContent"),
  structuralPhase: document.getElementById("structuralPhase"),
  refreshButton: document.getElementById("refreshButton"),
  openBundleButton: document.getElementById("openBundleButton"),
};

async function loadRuns() {
  setStatus("Loading runs...");
  const response = await fetch("/api/runs");
  const payload = await response.json();
  state.runs = payload.runs || [];
  renderRunList();
  if (state.runs.length === 0) {
    setStatus("No run bundles found.");
    renderEmpty();
    return;
  }
  const current = state.selectedRun || state.runs[0].run_id;
  await selectRun(current);
}

async function selectRun(runId) {
  state.selectedRun = runId;
  setStatus(`Loading ${runId}...`);
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
  state.detail = await response.json();
  renderRunList();
  renderAll();
  setStatus(`Loaded ${runId}`);
}

function renderRunList() {
  els.runList.innerHTML = "";
  for (const run of state.runs) {
    const button = document.createElement("button");
    button.className = `run-item ${run.run_id === state.selectedRun ? "active" : ""}`;
    button.innerHTML = `
      <div class="run-name">${escapeHtml(run.run_id)}</div>
      <div class="run-meta">${formatMeters(run.max_altitude_m)} apogee · ${formatSpeed(run.touchdown_speed_m_s)} touchdown</div>
      <div class="run-meta">${run.telemetry_rows ?? "?"} telemetry rows</div>
    `;
    button.addEventListener("click", () => selectRun(run.run_id));
    els.runList.appendChild(button);
  }
}

function renderAll() {
  if (!state.detail) return;
  renderMetrics();
  renderAnimation();
  renderPlots();
  renderThermal();
  renderStructural();
  renderTelemetry();
  renderInspector();
  renderManifest();
}

function renderMetrics() {
  const summary = state.detail.summary || {};
  const metrics = [
    ["Touchdown", summary.touchdown === true ? "yes" : "no"],
    ["Apogee", formatMeters(summary.max_altitude_m)],
    ["Touchdown speed", formatSpeed(summary.touchdown_speed_m_s)],
    ["CO2 remaining", formatKg(summary.co2_remaining_kg)],
    ["Thermal margin", formatTemp(summary.minimum_thermal_margin_deg_c)],
    ["Peak stress", formatStress(summary.peak_structural_stress_pa)],
    ["Rows", summary.telemetry_rows ?? "n/a"],
    ["Backend", summary.controller_backend || "n/a"],
    ["Rail exit", formatSpeed(summary.rail_exit_speed_m_s)],
    ["Max q", formatPressure(summary.max_dynamic_pressure_pa)],
  ];
  els.metricGrid.innerHTML = metrics.map(([label, value]) => `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(String(value))}</div>
    </div>
  `).join("");
}

function renderAnimation() {
  const gif = state.detail.artifacts?.animation_gif;
  if (!gif) {
    els.animationMount.innerHTML = `<div class="empty-state">No animation artifact found.</div>`;
    return;
  }
  els.animationMount.innerHTML = `<img src="${gif}" alt="Flight animation with nozzle plumes">`;
}

function renderManifest() {
  const manifest = state.detail.manifest || {};
  els.manifestPreview.textContent = JSON.stringify({
    run_id: state.detail.run_id,
    seed: manifest.seed,
    backend: manifest.backend,
    telemetry_hash: manifest.telemetry_hash,
    state_hash: manifest.state_hash,
    deferred_artifacts: manifest.deferred_artifacts,
  }, null, 2);
}

function renderPlots() {
  const plots = state.detail.artifacts?.plots || [];
  const flightNames = new Set([
    "altitude_velocity_accel.png",
    "attitude_rates.png",
    "thrust_co2.png",
    "valve_activity.png",
  ]);
  els.flightPlots.innerHTML = plots
    .filter((plot) => flightNames.has(plot.name))
    .map(plotFrame)
    .join("") || `<div class="empty-state">No flight plots found.</div>`;
  els.allPlots.innerHTML = plots.map(plotFrame).join("")
    || `<div class="empty-state">No plot artifacts found.</div>`;
}

function renderThermal() {
  const plots = (state.detail.artifacts?.plots || [])
    .filter((plot) => plot.name.startsWith("thermal_"));
  els.thermalPlots.innerHTML = plots.map(plotFrame).join("")
    || `<div class="empty-state">Thermal artifacts are not present.</div>`;
  const thermal = state.detail.summary?.thermal || {};
  els.thermalSummary.innerHTML = keyValueTable([
    ["Peak temperature", formatTemp(thermal.peak_temperature_deg_c)],
    ["Minimum margin", formatTemp(thermal.minimum_margin_deg_c)],
    ["Crossed nodes", (thermal.crossed_limit_nodes || []).join(", ") || "none"],
    ["Duration", formatSeconds(thermal.duration_s)],
  ]);
}

function renderStructural() {
  const structuralGroup = state.detail.artifacts?.structural || {};
  const structuralPlots = structuralGroup.plots || [];
  els.structuralPlots.innerHTML = structuralPlots.map((url) => {
    const name = url.split("/").at(-1);
    return plotFrame({ name, url });
  }).join("") || `<div class="empty-state">Structural artifacts are not present yet.</div>`;
  const structural = state.detail.summary?.structural || {};
  els.structuralSummary.innerHTML = Object.keys(structural).length === 0
    ? `<div class="empty-state">Phase 11 structural results will appear here.</div>`
    : keyValueTable([
      ["Solver used", structural.solver_used],
      ["Solver status", structural.solver_status],
      ["Load cases", structural.load_case_count],
      ["Peak stress", formatStress(structural.peak_stress_pa)],
      ["Peak stress case", structural.peak_stress_case_id],
      ["Peak displacement", formatMillimeters(structural.peak_displacement_m)],
    ]);
  els.structuralPhase.className = Object.keys(structural).length === 0 ? "" : "done";
}

function renderTelemetry() {
  const preview = state.detail.telemetry_preview || { columns: [], rows: [] };
  const preferred = [
    "time_s",
    "position_z_m",
    "velocity_z_m_s",
    "mass_kg",
    "mach",
    "dynamic_pressure_pa",
    "static_margin_calibers",
    "coldgas_thrust_n",
    "co2_mass_kg",
    "tank_pressure_pa",
    "valve_0_open",
    "valve_1_open",
    "valve_2_open",
  ];
  const columns = preferred.filter((column) => preview.columns.includes(column));
  els.telemetryTable.innerHTML = `
    <thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead>
    <tbody>
      ${(preview.rows || []).map((row) => `
        <tr>${columns.map((column) => `<td>${formatCell(row[column])}</td>`).join("")}</tr>
      `).join("")}
    </tbody>
  `;
}

function renderInspector() {
  const summary = state.detail.summary || {};
  const manifest = state.detail.manifest || {};
  els.inspectorContent.innerHTML = `
    <div class="inspector-block">
      <div class="pane-title">Selected Run</div>
      ${keyValueTable([
        ["Run ID", state.detail.run_id],
        ["Seed", manifest.seed],
        ["Backend", manifest.backend],
        ["Touchdown", summary.touchdown],
        ["Telemetry rows", summary.telemetry_rows],
      ])}
    </div>
    <div class="inspector-block">
      <div class="pane-title">Artifacts</div>
      ${keyValueTable([
        ["Plots", (state.detail.artifacts?.plots || []).length],
        ["Thermal", Object.keys(state.detail.artifacts?.thermal || {}).length ? "present" : "missing"],
        ["Structural", Object.keys(state.detail.artifacts?.structural || {}).length ? "present" : "pending"],
        ["Animation", state.detail.artifacts?.animation_gif ? "present" : "missing"],
      ])}
    </div>
  `;
}

function renderEmpty() {
  els.metricGrid.innerHTML = "";
  els.animationMount.innerHTML = `<div class="empty-state">Run an e2e flight to populate the workbench.</div>`;
  els.manifestPreview.textContent = "";
  els.flightPlots.innerHTML = "";
  els.allPlots.innerHTML = "";
  els.telemetryTable.innerHTML = "";
  els.inspectorContent.innerHTML = "";
}

function keyValueTable(rows) {
  return `<div class="kv-table">${rows.map(([key, value]) => `
    <div class="kv-row">
      <div class="kv-key">${escapeHtml(String(key))}</div>
      <div class="kv-value">${escapeHtml(String(value ?? "n/a"))}</div>
    </div>
  `).join("")}</div>`;
}

function plotFrame(plot) {
  return `
    <figure class="plot-frame">
      <div class="plot-title">${escapeHtml(plot.name)}</div>
      <img src="${plot.url}" alt="${escapeHtml(plot.name)}">
    </figure>
  `;
}

function setStatus(text) {
  els.statusText.textContent = text;
}

function formatCell(value) {
  const number = Number(value);
  if (value === "True" || value === "true") return "1";
  if (value === "False" || value === "false") return "0";
  if (Number.isFinite(number)) return Math.abs(number) > 1000 ? number.toExponential(3) : number.toFixed(4);
  return escapeHtml(String(value ?? ""));
}

function formatMeters(value) {
  return numeric(value, "m", 2);
}

function formatSpeed(value) {
  return numeric(value, "m/s", 2);
}

function formatKg(value) {
  return numeric(value, "kg", 4);
}

function formatTemp(value) {
  return numeric(value, "C", 2);
}

function formatPressure(value) {
  return numeric(value, "Pa", 1);
}

function formatStress(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number / 1e6).toFixed(2)} MPa` : "n/a";
}

function formatMillimeters(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 1000).toFixed(3)} mm` : "n/a";
}

function formatSeconds(value) {
  return numeric(value, "s", 3);
}

function numeric(value, unit, digits) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)} ${unit}` : "n/a";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    state.activeView = tab.dataset.view;
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active-view"));
    tab.classList.add("active");
    document.getElementById(state.activeView).classList.add("active-view");
  });
}

els.refreshButton.addEventListener("click", loadRuns);
els.openBundleButton.addEventListener("click", () => {
  if (!state.selectedRun) return;
  window.open(`/api/runs/${encodeURIComponent(state.selectedRun)}`, "_blank");
});

loadRuns().catch((error) => {
  console.error(error);
  setStatus("GUI failed to load run data.");
});
