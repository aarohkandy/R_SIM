const state = {
  runs: [],
  configs: [],
  selectedRun: null,
  selectedConfig: "bom",
  detail: null,
  configDetail: null,
  rocketSummary: null,
  hilStatus: null,
  activeView: "design",
  dirty: false,
};

const els = {
  runList: document.getElementById("runList"),
  configList: document.getElementById("configList"),
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
  renodePhase: document.getElementById("renodePhase"),
  refreshButton: document.getElementById("refreshButton"),
  validateButton: document.getElementById("validateButton"),
  saveButton: document.getElementById("saveButton"),
  runE2EButton: document.getElementById("runE2EButton"),
  openBundleButton: document.getElementById("openBundleButton"),
  configTitle: document.getElementById("configTitle"),
  configPath: document.getElementById("configPath"),
  configSelect: document.getElementById("configSelect"),
  configEditor: document.getElementById("configEditor"),
  configDescription: document.getElementById("configDescription"),
  configSummary: document.getElementById("configSummary"),
  validationBadge: document.getElementById("validationBadge"),
  rocketSummary: document.getElementById("rocketSummary"),
  rocketSummaryTable: document.getElementById("rocketSummaryTable"),
  emulatorGrid: document.getElementById("emulatorGrid"),
};

async function loadWorkbench() {
  setStatus("Loading workbench...");
  const [runsPayload, configsPayload, summaryPayload, hilPayload] = await Promise.all([
    fetchJson("/api/runs"),
    fetchJson("/api/configs"),
    fetchJson("/api/rocket-summary"),
    fetchJson("/api/hil-status"),
  ]);
  state.runs = runsPayload.runs || [];
  state.configs = configsPayload.configs || [];
  state.rocketSummary = summaryPayload.summary || null;
  state.hilStatus = hilPayload.hil || null;
  renderRunList();
  renderConfigList();
  renderRocketSummary();
  if (state.runs.length > 0) {
    const current = state.selectedRun || state.runs[0].run_id;
    await selectRun(current);
  } else {
    renderEmptyRun();
  }
  await selectConfig(state.selectedConfig);
  setStatus("Workbench ready");
}

async function selectRun(runId) {
  state.selectedRun = runId;
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
  state.detail = payload;
  renderRunList();
  renderRunData();
}

async function selectConfig(name) {
  if (state.dirty && !window.confirm("Discard unsaved editor changes?")) return;
  state.selectedConfig = name;
  setStatus(`Loading ${name}...`);
  const payload = await fetchJson(`/api/configs/${encodeURIComponent(name)}`);
  state.configDetail = payload;
  state.dirty = false;
  els.configEditor.value = payload.text || "";
  renderConfigList();
  renderConfigDetail(payload);
  renderInspector();
  setStatus(`Editing ${payload.label}`);
}

async function validateSelectedConfig() {
  if (!state.configDetail) return;
  const payload = await postJson(
    `/api/configs/${encodeURIComponent(state.selectedConfig)}/validate`,
    { text: els.configEditor.value },
  );
  state.configDetail = { ...state.configDetail, ...payload, text: els.configEditor.value };
  renderConfigDetail(state.configDetail);
  setStatus(payload.valid ? "Definition is valid" : `Validation failed: ${payload.message}`);
}

async function saveSelectedConfig() {
  if (!state.configDetail) return;
  setStatus(`Saving ${state.configDetail.label}...`);
  const payload = await postJson(`/api/configs/${encodeURIComponent(state.selectedConfig)}`, {
    text: els.configEditor.value,
  });
  if (!payload.valid) {
    state.configDetail = { ...state.configDetail, ...payload, text: els.configEditor.value };
    renderConfigDetail(state.configDetail);
    setStatus(`Save blocked: ${payload.message}`);
    return;
  }
  state.configDetail = payload;
  state.dirty = false;
  els.configEditor.value = payload.text || els.configEditor.value;
  await refreshConfigsAndSummary();
  renderConfigDetail(payload);
  setStatus(`Saved ${payload.path}`);
}

async function runSilFromGui() {
  setBusy(true);
  setStatus("Running native SIL...");
  try {
    const payload = await postJson("/api/run/e2e", {});
    if (!payload.ok) {
      setStatus(`SIL run failed: ${payload.message}`);
      return;
    }
    await refreshRuns();
    await selectRun(payload.run_id);
    switchView("overview");
    setStatus(`SIL run complete: ${payload.run_id}`);
  } finally {
    setBusy(false);
  }
}

async function refreshRuns() {
  const payload = await fetchJson("/api/runs");
  state.runs = payload.runs || [];
  renderRunList();
}

async function refreshConfigsAndSummary() {
  const [configsPayload, summaryPayload, hilPayload] = await Promise.all([
    fetchJson("/api/configs"),
    fetchJson("/api/rocket-summary"),
    fetchJson("/api/hil-status"),
  ]);
  state.configs = configsPayload.configs || [];
  state.rocketSummary = summaryPayload.summary || null;
  state.hilStatus = hilPayload.hil || null;
  renderConfigList();
  renderRocketSummary();
}

function renderRunData() {
  renderMetrics();
  renderAnimation();
  renderPlots();
  renderThermal();
  renderStructural();
  renderEmulators();
  renderTelemetry();
  renderManifest();
  renderInspector();
}

function renderConfigList() {
  els.configList.innerHTML = "";
  const groups = groupBy(state.configs, (item) => item.group || "Other");
  for (const [group, items] of Object.entries(groups)) {
    const header = document.createElement("div");
    header.className = "file-group";
    header.textContent = group;
    els.configList.appendChild(header);
    for (const item of items) {
      const button = document.createElement("button");
      button.className = `file-item ${item.name === state.selectedConfig ? "active" : ""}`;
      const validClass = item.valid ? "good" : "bad";
      button.innerHTML = `
        <span class="file-main">
          <span class="file-label">${escapeHtml(item.label)}</span>
          <span class="file-path">${escapeHtml(item.path)}</span>
        </span>
        <span class="dot ${validClass}"></span>
      `;
      button.addEventListener("click", () => selectConfig(item.name));
      els.configList.appendChild(button);
    }
  }
  renderConfigSelect();
}

function renderConfigSelect() {
  els.configSelect.innerHTML = state.configs.map((item) => `
    <option value="${escapeHtml(item.name)}">${escapeHtml(`${item.group} - ${item.label}`)}</option>
  `).join("");
  els.configSelect.value = state.selectedConfig;
}

function renderRunList() {
  els.runList.innerHTML = "";
  for (const run of state.runs) {
    const button = document.createElement("button");
    button.className = `run-item ${run.run_id === state.selectedRun ? "active" : ""}`;
    button.innerHTML = `
      <div class="run-name">${escapeHtml(run.run_id)}</div>
      <div class="run-meta">${formatMeters(run.max_altitude_m)} apogee</div>
      <div class="run-meta">${formatSpeed(run.touchdown_speed_m_s)} touchdown</div>
    `;
    button.addEventListener("click", () => selectRun(run.run_id));
    els.runList.appendChild(button);
  }
  if (state.runs.length === 0) {
    els.runList.innerHTML = `<div class="empty-state small">No run bundles yet.</div>`;
  }
}

function renderConfigDetail(payload) {
  els.configTitle.textContent = payload.label || "Rocket Definition";
  els.configPath.textContent = payload.path || "";
  els.configDescription.textContent = payload.description || "";
  renderValidation(payload);
  els.configSummary.innerHTML = keyValueTable(summaryRows(payload.summary || {}));
}

function renderValidation(payload) {
  const valid = payload.valid === true;
  const dirty = state.dirty ? " unsaved" : "";
  els.validationBadge.className = `state-badge ${valid ? "good" : "bad"}`;
  els.validationBadge.textContent = valid ? `Valid${dirty}` : "Invalid";
  if (!valid) {
    els.configSummary.innerHTML = keyValueTable([["Problem", payload.message || "Unknown"]]);
  }
}

function renderRocketSummary() {
  const summary = state.rocketSummary || {};
  const metrics = [
    ["Wet mass", formatKg(summary.wet_mass_kg)],
    ["CG", formatVector(summary.cg_m, "m")],
    ["Parts", summary.part_count ?? "n/a"],
    ["Legs", summary.deployable_leg_count ?? "n/a"],
    ["Motor", summary.motor_designation || "n/a"],
    ["Impulse", numeric(summary.motor_total_impulse_ns, "N*s", 2)],
    ["CO2", formatKg(summary.co2_initial_mass_kg)],
    ["Nozzles", summary.nozzle_count ?? "n/a"],
  ];
  els.rocketSummary.innerHTML = metrics.map(([label, value]) => `
    <div class="summary-cell">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </div>
  `).join("");
  els.rocketSummaryTable.innerHTML = keyValueTable([
    ["Wet mass", formatKg(summary.wet_mass_kg)],
    ["CG", formatVector(summary.cg_m, "m")],
    ["Body diameter", formatMeters(summary.body_diameter_m)],
    ["Body length", formatMeters(summary.body_length_m)],
    ["Burn time", formatSeconds(summary.motor_burn_time_s)],
    ["Reg setpoint", formatPressure(summary.regulator_setpoint_pa)],
    ["Fixed dt", formatSeconds(summary.integrator_dt_s)],
    ["Seed", summary.master_seed],
  ]);
}

function renderMetrics() {
  const summary = state.detail?.summary || {};
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
  const gif = state.detail?.artifacts?.animation_gif;
  els.animationMount.innerHTML = gif
    ? `<img src="${gif}" alt="Flight animation with nozzle plumes">`
    : `<div class="empty-state">No animation artifact found.</div>`;
}

function renderManifest() {
  const manifest = state.detail?.manifest || {};
  els.manifestPreview.textContent = JSON.stringify({
    run_id: state.detail?.run_id,
    seed: manifest.seed,
    backend: manifest.backend,
    telemetry_hash: manifest.telemetry_hash,
    state_hash: manifest.state_hash,
    deferred_artifacts: manifest.deferred_artifacts,
  }, null, 2);
}

function renderPlots() {
  const plots = state.detail?.artifacts?.plots || [];
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
  const plots = (state.detail?.artifacts?.plots || [])
    .filter((plot) => plot.name.startsWith("thermal_"));
  els.thermalPlots.innerHTML = plots.map(plotFrame).join("")
    || `<div class="empty-state">Thermal artifacts are not present.</div>`;
  const thermal = state.detail?.summary?.thermal || {};
  els.thermalSummary.innerHTML = keyValueTable([
    ["Peak temperature", formatTemp(thermal.peak_temperature_deg_c)],
    ["Minimum margin", formatTemp(thermal.minimum_margin_deg_c)],
    ["Crossed nodes", (thermal.crossed_limit_nodes || []).join(", ") || "none"],
    ["Duration", formatSeconds(thermal.duration_s)],
  ]);
}

function renderStructural() {
  const structuralGroup = state.detail?.artifacts?.structural || {};
  const structuralPlots = structuralGroup.plots || [];
  els.structuralPlots.innerHTML = structuralPlots.map((url) => {
    const name = url.split("/").at(-1);
    return plotFrame({ name, url });
  }).join("") || `<div class="empty-state">Structural artifacts are not present yet.</div>`;
  const structural = state.detail?.summary?.structural || {};
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

function renderEmulators() {
  const manifest = state.detail?.manifest || {};
  const backend = manifest.backend || "sil";
  const hil = state.hilStatus || {};
  const blockers = hil.blockers || [];
  const components = hil.components || [];
  const ready = hil.ready === true;
  els.renodePhase.className = ready || backend === "renode" ? "done" : "";
  els.emulatorGrid.innerHTML = `
    <div class="emulator-panel">
      <div class="pane-title">Backend A</div>
      <div class="large-state good">Native SIL online</div>
      ${keyValueTable([
        ["Active run backend", backend],
        ["Loop source", "configured SIL"],
        ["Run hash", manifest.telemetry_hash ? manifest.telemetry_hash.slice(0, 12) : "n/a"],
      ])}
    </div>
    <div class="emulator-panel">
      <div class="pane-title">Backend B</div>
      <div class="large-state ${ready ? "good" : "waiting"}">${ready ? "Renode ready" : "Renode blocked"}</div>
      ${keyValueTable([
        ["Status", hil.status || "not checked"],
        ["Blockers", blockers.length],
        ["Sync quantum", formatSeconds(hil.time_sync?.renode_sync_quantum_s)],
        ["Loop period", formatSeconds(hil.time_sync?.controller_loop_period_s)],
      ])}
      <div class="pane-title stacked">Blockers</div>
      ${blockerList(blockers)}
      <div class="pane-title stacked">Components</div>
      ${componentList(components)}
      <div class="pane-title stacked">Next Steps</div>
      ${simpleList(hil.next_steps || [])}
    </div>
  `;
}

function blockerList(blockers) {
  if (!blockers.length) return `<div class="empty-state small">No HIL blockers reported.</div>`;
  return `<div class="status-list">${blockers.map((blocker) => `
    <div class="status-row bad">
      <strong>${escapeHtml(blocker.code)}</strong>
      <span>${escapeHtml(blocker.message)}</span>
    </div>
  `).join("")}</div>`;
}

function componentList(components) {
  if (!components.length) return `<div class="empty-state small">No component status available.</div>`;
  return `<div class="status-list">${components.map((component) => `
    <div class="status-row ${component.verified ? "good" : "bad"}">
      <strong>${escapeHtml(component.id)}</strong>
      <span>${escapeHtml(`${component.present ? "present" : "missing"} / ${component.verified ? "verified" : "unverified"}`)}</span>
    </div>
  `).join("")}</div>`;
}

function simpleList(items) {
  if (!items.length) return `<div class="empty-state small">No next steps reported.</div>`;
  return `<ul class="plain-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderTelemetry() {
  const preview = state.detail?.telemetry_preview || { columns: [], rows: [] };
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
  const summary = state.detail?.summary || {};
  const manifest = state.detail?.manifest || {};
  els.inspectorContent.innerHTML = `
    <div class="inspector-block">
      <div class="pane-title">Editor</div>
      ${keyValueTable([
        ["File", state.configDetail?.label || "n/a"],
        ["Path", state.configDetail?.path || "n/a"],
        ["Valid", state.configDetail?.valid],
        ["Unsaved", state.dirty],
      ])}
    </div>
    <div class="inspector-block">
      <div class="pane-title">Selected Run</div>
      ${keyValueTable([
        ["Run ID", state.detail?.run_id || "n/a"],
        ["Seed", manifest.seed],
        ["Backend", manifest.backend],
        ["Touchdown", summary.touchdown],
        ["Telemetry rows", summary.telemetry_rows],
      ])}
    </div>
    <div class="inspector-block">
      <div class="pane-title">Artifacts</div>
      ${keyValueTable([
        ["Plots", (state.detail?.artifacts?.plots || []).length],
        ["Thermal", Object.keys(state.detail?.artifacts?.thermal || {}).length ? "present" : "missing"],
        ["Structural", Object.keys(state.detail?.artifacts?.structural || {}).length ? "present" : "pending"],
        ["Animation", state.detail?.artifacts?.animation_gif ? "present" : "missing"],
      ])}
    </div>
  `;
}

function renderEmptyRun() {
  els.metricGrid.innerHTML = "";
  els.animationMount.innerHTML = `<div class="empty-state">Run native SIL to populate flight artifacts.</div>`;
  els.manifestPreview.textContent = "";
  els.flightPlots.innerHTML = "";
  els.allPlots.innerHTML = "";
  els.telemetryTable.innerHTML = "";
  renderEmulators();
}

function switchView(viewName) {
  state.activeView = viewName;
  document.querySelectorAll(".tab").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewName);
  });
  document.querySelectorAll(".view").forEach((item) => {
    item.classList.toggle("active-view", item.id === viewName);
  });
}

function setBusy(isBusy) {
  els.runE2EButton.disabled = isBusy;
  els.saveButton.disabled = isBusy;
  els.validateButton.disabled = isBusy;
}

function keyValueTable(rows) {
  return `<div class="kv-table">${rows.map(([key, value]) => `
    <div class="kv-row">
      <div class="kv-key">${escapeHtml(String(key))}</div>
      <div class="kv-value">${escapeHtml(String(value ?? "n/a"))}</div>
    </div>
  `).join("")}</div>`;
}

function summaryRows(summary) {
  const rows = Object.entries(summary || {}).map(([key, value]) => [labelize(key), value]);
  return rows.length ? rows : [["Summary", "n/a"]];
}

function plotFrame(plot) {
  return `
    <figure class="plot-frame">
      <div class="plot-title">${escapeHtml(plot.name)}</div>
      <img src="${plot.url}" alt="${escapeHtml(plot.name)}">
    </figure>
  `;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || response.statusText);
  return payload;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok && payload.valid !== false) throw new Error(payload.error || response.statusText);
  return payload;
}

function setStatus(text) {
  els.statusText.textContent = text;
}

function groupBy(items, keyFn) {
  return items.reduce((groups, item) => {
    const key = keyFn(item);
    groups[key] = groups[key] || [];
    groups[key].push(item);
    return groups;
  }, {});
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

function formatVector(value, unit) {
  if (!Array.isArray(value)) return "n/a";
  return `[${value.map((item) => Number(item).toFixed(3)).join(", ")}] ${unit}`;
}

function numeric(value, unit, digits) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)} ${unit}` : "n/a";
}

function labelize(value) {
  return value.replaceAll("_", " ");
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
  tab.addEventListener("click", () => switchView(tab.dataset.view));
}

els.refreshButton.addEventListener("click", loadWorkbench);
els.validateButton.addEventListener("click", validateSelectedConfig);
els.saveButton.addEventListener("click", saveSelectedConfig);
els.runE2EButton.addEventListener("click", runSilFromGui);
els.openBundleButton.addEventListener("click", () => {
  if (!state.selectedRun) return;
  window.open(`/api/runs/${encodeURIComponent(state.selectedRun)}`, "_blank");
});
els.configEditor.addEventListener("input", () => {
  state.dirty = true;
  renderValidation({ ...state.configDetail, valid: state.configDetail?.valid !== false });
  renderInspector();
});
els.configSelect.addEventListener("change", () => {
  selectConfig(els.configSelect.value);
});

loadWorkbench().catch((error) => {
  console.error(error);
  setStatus(`GUI failed: ${error.message}`);
});
