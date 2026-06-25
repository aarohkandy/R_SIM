import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import './App.css';

const API_URL = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_SIMULATION_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:5011' : '')
).replace(/\/$/, '');

const makeId = (prefix) => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const numberValue = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const formatNumber = (value, digits = 1) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '--';
  if (Math.abs(parsed) >= 1000) return Math.round(parsed).toLocaleString();
  return parsed.toFixed(digits);
};

const componentColor = {
  'Nose Cone': '#d9514e',
  'Body Tube': '#d8dee6',
  Transition: '#bdc8d7',
  'Electronics Bay': '#4d908e',
  'Recovery Bay': '#577590',
  'Active Airbrake': '#f2a541',
  Fins: '#2a9d8f',
  Motor: '#343a40',
  'Landing System': '#7b61ff',
  'Rail Button': '#6c757d'
};

const componentDefaults = {
  'Nose Cone': {
    type: 'Nose Cone',
    name: 'Ogive nose cone',
    length: 145,
    diameter: 54,
    weight: 110,
    material: 'plastic',
    shape: 'ogive'
  },
  'Body Tube': {
    type: 'Body Tube',
    name: 'Airframe tube',
    length: 520,
    diameter: 54,
    weight: 155,
    material: 'cardboard'
  },
  Transition: {
    type: 'Transition',
    name: 'Diameter transition',
    length: 80,
    diameter: 54,
    topDiameter: 54,
    bottomDiameter: 38,
    weight: 42,
    material: 'fiberglass'
  },
  'Electronics Bay': {
    type: 'Electronics Bay',
    name: 'Avionics bay',
    length: 90,
    diameter: 54,
    weight: 95,
    material: 'fiberglass'
  },
  'Recovery Bay': {
    type: 'Recovery Bay',
    name: 'Recovery bay',
    length: 130,
    diameter: 54,
    weight: 72,
    material: 'cardboard'
  },
  'Active Airbrake': {
    type: 'Active Airbrake',
    name: 'Pneumatic airbrake module',
    length: 38,
    diameter: 54,
    weight: 70,
    surfaceCount: 3,
    surfaceArea: 0.0024,
    surfaceMaxAngle: 65
  },
  Fins: {
    type: 'Fins',
    name: 'Through-wall fin set',
    length: 0,
    diameter: 54,
    weight: 44,
    finCount: 3,
    finHeight: 72,
    finWidth: 118,
    finSweep: 36,
    finThickness: 3,
    material: 'plywood'
  },
  Motor: {
    type: 'Motor',
    name: 'AeroTech G40-7W',
    length: 124,
    diameter: 29,
    weight: 145,
    motorType: 'AeroTech',
    motorModel: 'G40-7W',
    motorImpulse: 'G',
    motorThrust: 40,
    motorBurnTime: 2.2,
    motorTotalImpulse: 90,
    motorDelay: 7
  },
  'Landing System': {
    type: 'Landing System',
    name: 'Main chute and landing cradle',
    length: 40,
    diameter: 54,
    weight: 85,
    mainDeployEvent: 'altitude',
    drogueDeployEvent: 'apogee',
    drogueDeployAltitude: 120,
    deployAltitude: 120,
    dragArea: 0.24,
    dragCoefficient: 1.55,
    drogueDragArea: 0.04,
    drogueDragCoefficient: 1.25,
    maxSafeVelocity: 7.5
  },
  'Rail Button': {
    type: 'Rail Button',
    name: 'Rail button pair',
    length: 12,
    diameter: 8,
    weight: 8,
    railOffset: 4
  }
};

const defaultComponents = [
  { ...componentDefaults['Nose Cone'], id: 'nose-1' },
  { ...componentDefaults['Recovery Bay'], id: 'recovery-1' },
  { ...componentDefaults['Landing System'], id: 'landing-1' },
  { ...componentDefaults['Body Tube'], id: 'tube-1', name: 'Forward airframe', length: 360, weight: 110 },
  { ...componentDefaults['Electronics Bay'], id: 'avbay-1' },
  { ...componentDefaults['Active Airbrake'], id: 'airbrake-1' },
  { ...componentDefaults['Body Tube'], id: 'tube-2', name: 'Aft airframe', length: 320, weight: 125 },
  { ...componentDefaults.Fins, id: 'fins-1', attachedToComponent: 'tube-2' },
  { ...componentDefaults.Motor, id: 'motor-1', attachedToComponent: 'tube-2' }
];

const defaultConfig = {
  launchSite: 'custom',
  launchAltitude: 0,
  temperature: 15,
  pressure: 101325,
  humidity: 45,
  windSpeed: 2.5,
  windDirection: 20,
  launchGuideLength: 2.0,
  launchGuideAngle: 0,
  launchGuideDirection: 0,
  minRailExitVelocity: 12,
  timeStep: 0.02,
  maxTime: 55,
  solverType: 'pimpleFoam',
  turbulenceModel: 'LES',
  activePneumaticEnabled: true,
  controllerLanguage: 'builtin',
  activeSystem: {
    enabled: true,
    tankPressure: 690000,
    tankVolume: 0.22,
    regulatorPressure: 455000,
    minOperatingPressure: 180000,
    valveFlowRate: 14,
    ventRate: 2.5,
    lineVolume: 0.035,
    cylinderBore: 0.012,
    cylinderStroke: 0.035,
    cylinderFriction: 5,
    returnSpring: 18,
    linkageRatio: 1,
    surfaceMaxAngle: 65,
    surfaceArea: 0.0024,
    surfaceCount: 3,
    surfaceCd: 1.35,
    locationFromNose: 0.52,
    maxDynamicPressure: 85000
  },
  controller: {
    mode: 'target_apogee',
    targetApogee: 180,
    deployAltitude: 45,
    descentDeployAltitude: 150,
    kp: 0.018,
    kd: 0.008,
    minimumCommand: 0.03
  },
  landingSystem: {
    enabled: true,
    type: 'main_parachute',
    mainDeployEvent: 'altitude',
    drogueDeployEvent: 'apogee',
    drogueDeployAltitude: 120,
    deployAltitude: 120,
    dragArea: 0.24,
    dragCoefficient: 1.55,
    drogueDragArea: 0.04,
    drogueDragCoefficient: 1.25,
    maxSafeVelocity: 7.5
  },
  aerodynamics: {
    baseDragCoefficient: 0.56,
    activeDragCoefficientTable: [
      { deployment: 0, cdIncrement: 0 },
      { deployment: 0.5, cdIncrement: 1.4 },
      { deployment: 1, cdIncrement: 3.2 }
    ]
  },
  noise: {
    seed: 20260625,
    altitudeStd: 0.12,
    velocityStd: 0.04,
    accelStd: 0.1,
    ambientPressureStd: 8,
    pneumaticPressureStd: 120,
    temperatureStd: 0.05,
    initialAttitudeStd: 0.35
  }
};

const structuralTypes = new Set([
  'Nose Cone',
  'Body Tube',
  'Transition',
  'Electronics Bay',
  'Recovery Bay',
  'Active Airbrake',
  'Landing System',
  'Rail Button'
]);

const normalizeMotor = (motor) => {
  const manufacturer = motor.manufacturer || 'Unknown';
  const designation = motor.designation || motor.model || 'Motor';
  const model = designation.startsWith(`${manufacturer} `)
    ? designation.slice(manufacturer.length + 1)
    : designation;
  const thrustCurve = (motor.thrust_curve || motor.thrustCurve || []).map((point) => (
    Array.isArray(point)
      ? { time: numberValue(point[0]), thrust: numberValue(point[1]) }
      : { time: numberValue(point.time), thrust: numberValue(point.thrust) }
  )).filter((point) => Number.isFinite(point.time) && Number.isFinite(point.thrust));

  return {
    id: `${manufacturer}-${designation}`.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
    manufacturer,
    designation,
    model,
    displayName: `${manufacturer} ${model}`.trim(),
    impulse: motor.impulse_class || motor.impulse || '',
    thrust: numberValue(motor.average_thrust ?? motor.thrust),
    maxThrust: numberValue(motor.max_thrust ?? motor.maxThrust),
    burnTime: numberValue(motor.burn_time ?? motor.burnTime),
    totalImpulse: numberValue(motor.total_impulse ?? motor.totalImpulse),
    delay: numberValue(motor.delay_time ?? motor.delay),
    weight: numberValue(motor.total_mass ?? motor.weight),
    propellantMass: numberValue(motor.propellant_mass),
    diameter: numberValue(motor.diameter),
    length: numberValue(motor.length),
    approvedForTarc: Boolean(motor.approved_for_tarc),
    thrustCurve
  };
};

const normalizeSite = ([id, site]) => {
  const elevation = numberValue(site.elevation);
  const tempK = 288.15 - 0.0065 * Math.min(Math.max(elevation, 0), 11000);
  const pressure = Math.round(101325 * (tempK / 288.15) ** 5.2561);
  return {
    id,
    label: id.replace(/_/g, ' '),
    elevation,
    pressure,
    temperature: numberValue(site.ground_temperature, 15),
    latitude: numberValue(site.latitude),
    longitude: numberValue(site.longitude)
  };
};

const cloneComponent = (type) => ({
  ...componentDefaults[type],
  id: makeId(type.toLowerCase().replace(/[^a-z0-9]+/g, '-')),
  name: componentDefaults[type].name
});

const componentMass = (component) => {
  if (component.type === 'Motor') return numberValue(component.motorWeight ?? component.weight, 0);
  return numberValue(component.weight, 0);
};

const getDiameter = (component) => numberValue(component.diameter ?? component.bottomDiameter ?? component.topDiameter, 0);

const getStructuralLength = (components) => components
  .filter((component) => structuralTypes.has(component.type) && component.type !== 'Rail Button')
  .reduce((sum, component) => sum + Math.max(0, numberValue(component.length)), 0);

const getMaxDiameter = (components) => Math.max(
  1,
  ...components.map((component) => getDiameter(component)).filter((value) => value > 0)
);

const layoutComponents = (components) => {
  let cursor = 0;
  const structural = [];
  components.forEach((component) => {
    if (structuralTypes.has(component.type) && component.type !== 'Rail Button') {
      const length = Math.max(0, numberValue(component.length));
      structural.push({
        ...component,
        start: cursor,
        end: cursor + length,
        length
      });
      cursor += length;
    }
  });
  return structural;
};

const noseCpFraction = (shape = 'ogive') => ({
  conical: 0.667,
  elliptical: 0.5,
  'von-karman': 0.5,
  ogive: 0.466
})[shape] || 0.466;

const getCpAnalysis = (components) => {
  const totalLength = getStructuralLength(components);
  const maxDiameter = getMaxDiameter(components);
  const structural = layoutComponents(components);
  const referenceDiameter = Math.max(maxDiameter, 1);
  const contributions = [];

  structural.forEach((component) => {
    if (component.type === 'Nose Cone') {
      const diameterRatio = getDiameter(component) / referenceDiameter;
      contributions.push({
        id: component.id,
        name: component.name,
        type: component.type,
        color: componentColor[component.type],
        normalForce: 2 * diameterRatio * diameterRatio,
        cp: component.start + component.length * noseCpFraction(component.shape)
      });
    }

    if (component.type === 'Transition' && component.length > 0) {
      const frontDiameter = numberValue(component.topDiameter, component.diameter);
      const rearDiameter = numberValue(component.bottomDiameter, component.diameter);
      const normalForce = 2 * (((rearDiameter / referenceDiameter) ** 2) - ((frontDiameter / referenceDiameter) ** 2));
      if (Math.abs(normalForce) > 0.01) {
        contributions.push({
          id: component.id,
          name: component.name,
          type: component.type,
          color: componentColor[component.type],
          normalForce,
          cp: component.start + component.length * 0.55
        });
      }
    }
  });

  components
    .filter((component) => component.type === 'Fins')
    .forEach((component) => {
      const finCount = Math.max(numberValue(component.finCount, 3), 1);
      const span = Math.max(numberValue(component.finHeight, 0), 1);
      const rootChord = Math.max(numberValue(component.finWidth, 0), 1);
      const sweep = Math.max(numberValue(component.finSweep, 0), 0);
      const tipChord = Math.max(rootChord * 0.45, rootChord - sweep, rootChord * 0.2);
      const midChord = Math.sqrt(span ** 2 + (sweep + (rootChord - tipChord) / 2) ** 2);
      const denominator = 1 + Math.sqrt(1 + ((2 * midChord) / (rootChord + tipChord)) ** 2);
      const normalForce = 1.8 * finCount * ((span / referenceDiameter) ** 2) / denominator;
      const leadingEdge = Math.max(0, totalLength - rootChord);
      const cp = leadingEdge
        + (sweep * (rootChord + 2 * tipChord)) / (3 * (rootChord + tipChord))
        + (rootChord + tipChord - (rootChord * tipChord) / (rootChord + tipChord)) / 6;
      contributions.push({
        id: component.id,
        name: component.name,
        type: component.type,
        color: componentColor.Fins,
        normalForce,
        cp: clamp(cp, 0, totalLength)
      });
    });

  const totalNormalForce = contributions.reduce((sum, item) => sum + item.normalForce, 0);
  const weightedCp = contributions.reduce((sum, item) => sum + item.normalForce * item.cp, 0);
  const cp = Math.abs(totalNormalForce) > 0.001
    ? weightedCp / totalNormalForce
    : totalLength * 0.65;
  return {
    cp: clamp(cp, 0, totalLength),
    totalNormalForce,
    contributions: contributions.map((item) => ({
      ...item,
      share: totalNormalForce ? (item.normalForce / totalNormalForce) * 100 : 0
    }))
  };
};

const getMetrics = (components) => {
  const totalLength = getStructuralLength(components);
  const maxDiameter = getMaxDiameter(components);
  const mass = components.reduce((sum, component) => sum + componentMass(component), 0);
  const structural = layoutComponents(components);
  const cpAnalysis = getCpAnalysis(components);
  let moment = 0;
  let weightedMass = 0;

  components.forEach((component) => {
    const weight = componentMass(component);
    if (!weight) return;
    let position = totalLength / 2;
    if (component.type === 'Fins') {
      position = Math.max(0, totalLength - numberValue(component.finWidth, 100) / 2);
    } else if (component.type === 'Motor') {
      position = Math.max(0, totalLength - numberValue(component.length, 80) / 2);
    } else {
      const segment = structural.find((item) => item.id === component.id);
      if (segment) position = segment.start + segment.length / 2;
    }
    moment += weight * position;
    weightedMass += weight;
  });

  const cg = weightedMass > 0 ? moment / weightedMass : totalLength * 0.45;
  const cp = cpAnalysis.cp;
  const stability = maxDiameter > 0 ? (cp - cg) / maxDiameter : 0;
  const motor = components.find((component) => component.type === 'Motor');
  const thrust = numberValue(motor?.motorThrust, 0);
  const thrustToWeight = mass > 0 ? thrust / ((mass / 1000) * 9.80665) : 0;

  return {
    totalLength,
    maxDiameter,
    mass,
    cg,
    cp,
    stability,
    cpAnalysis,
    motor,
    thrustToWeight
  };
};

const massGroups = [
  {
    key: 'airframe',
    label: 'Airframe',
    color: '#d8dee6',
    types: ['Nose Cone', 'Body Tube', 'Transition', 'Electronics Bay', 'Recovery Bay', 'Rail Button']
  },
  { key: 'fins', label: 'Fins', color: '#2a9d8f', types: ['Fins'] },
  { key: 'motor', label: 'Motor', color: '#343a40', types: ['Motor'] },
  { key: 'active', label: 'Active control', color: '#f2a541', types: ['Active Airbrake'] },
  { key: 'landing', label: 'Landing', color: '#7b61ff', types: ['Landing System'] }
];

const getMassBreakdown = (components) => {
  const rows = massGroups.map((group) => ({
    ...group,
    mass: components
      .filter((component) => group.types.includes(component.type))
      .reduce((sum, component) => sum + componentMass(component), 0)
  }));
  const groupedTypes = new Set(massGroups.flatMap((group) => group.types));
  const otherMass = components
    .filter((component) => !groupedTypes.has(component.type))
    .reduce((sum, component) => sum + componentMass(component), 0);
  const allRows = otherMass > 0
    ? [...rows, { key: 'other', label: 'Other', color: '#8793a1', mass: otherMass }]
    : rows;
  const total = allRows.reduce((sum, row) => sum + row.mass, 0);
  return allRows
    .filter((row) => row.mass > 0)
    .map((row) => ({
      ...row,
      percent: total > 0 ? (row.mass / total) * 100 : 0
    }));
};

const getAirDensity = (config) => {
  const pressure = numberValue(config.pressure, 101325);
  const temperatureK = numberValue(config.temperature, 15) + 273.15;
  return pressure / (287.05 * Math.max(temperatureK, 1));
};

const getLandingSizing = (metrics, config, overrides = {}) => {
  const landing = { ...config.landingSystem, ...overrides };
  const massKg = Math.max(metrics.mass / 1000, 0.001);
  const density = Math.max(getAirDensity(config), 0.2);
  const dragCoefficient = Math.max(numberValue(landing.dragCoefficient, 1.55), 0.1);
  const dragArea = Math.max(numberValue(landing.dragArea, 0), 0);
  const safeVelocity = Math.max(numberValue(landing.maxSafeVelocity, 7.5), 0.1);
  const requiredArea = (2 * massKg * 9.80665) / (density * dragCoefficient * safeVelocity * safeVelocity);
  const estimatedTerminalVelocity = dragArea > 0
    ? Math.sqrt((2 * massKg * 9.80665) / (density * dragCoefficient * dragArea))
    : Infinity;
  return {
    density,
    requiredArea,
    estimatedTerminalVelocity,
    areaMargin: dragArea - requiredArea,
    safeVelocity,
    dragArea,
    dragCoefficient
  };
};

const getActiveEnvelope = (metrics, config) => {
  const diameterM = Math.max(metrics.maxDiameter / 1000, 0.001);
  const frontalArea = Math.PI * (diameterM / 2) ** 2;
  const active = config.activeSystem;
  const surfaceArea = Math.max(numberValue(active.surfaceArea, 0), 0);
  const surfaceCount = Math.max(numberValue(active.surfaceCount, 0), 0);
  const deployedArea = surfaceArea * surfaceCount;
  const cdIncrement = frontalArea > 0
    ? (numberValue(active.surfaceCd, 1.35) * deployedArea) / frontalArea
    : 0;
  return {
    frontalArea,
    deployedArea,
    cdIncrement,
    maxDynamicPressure: numberValue(active.maxDynamicPressure, 0)
  };
};

const impulseClasses = [
  { label: '1/4A', max: 0.625 },
  { label: '1/2A', max: 1.25 },
  { label: 'A', max: 2.5 },
  { label: 'B', max: 5 },
  { label: 'C', max: 10 },
  { label: 'D', max: 20 },
  { label: 'E', max: 40 },
  { label: 'F', max: 80 },
  { label: 'G', max: 160 },
  { label: 'H', max: 320 },
  { label: 'I', max: 640 },
  { label: 'J', max: 1280 },
  { label: 'K', max: 2560 },
  { label: 'L', max: 5120 },
  { label: 'M', max: 10240 }
];

const recoveryDeployEvents = [
  { value: 'apogee', label: 'Apogee' },
  { value: 'motor_ejection', label: 'Motor ejection' },
  { value: 'altitude', label: 'Altitude on descent' }
];

const recoveryEventLabel = (value) => (
  recoveryDeployEvents.find((event) => event.value === value)?.label || 'Altitude on descent'
);

const recoveryEventDetail = (event, altitude) => (
  event === 'altitude'
    ? `${formatNumber(altitude, 0)} m on descent`
    : recoveryEventLabel(event)
);

const getImpulseClass = (impulse) => {
  const totalImpulse = numberValue(impulse, 0);
  const found = impulseClasses.find((item) => totalImpulse <= item.max);
  return found?.label || 'N+';
};

const getLaunchGuideAnalysis = (metrics, config) => {
  const motor = metrics.motor || {};
  const massKg = Math.max(metrics.mass / 1000, 0.001);
  const burnTime = Math.max(numberValue(motor.motorBurnTime, 0), 0.001);
  const averageThrust = Math.max(
    numberValue(motor.motorThrust, 0),
    numberValue(motor.motorTotalImpulse, 0) / burnTime
  );
  const guideLength = Math.max(numberValue(config.launchGuideLength, 1.5), 0);
  const guideAngle = clamp(numberValue(config.launchGuideAngle, 0), 0, 30);
  const acceleration = Math.max((averageThrust / massKg) - (9.80665 * Math.cos((guideAngle * Math.PI) / 180)), 0);
  const exitVelocity = acceleration > 0 ? Math.sqrt(2 * acceleration * guideLength) : 0;
  const exitTime = acceleration > 0 ? exitVelocity / acceleration : null;
  const safeVelocity = numberValue(config.minRailExitVelocity, 12);
  return {
    averageThrust,
    totalImpulse: numberValue(motor.motorTotalImpulse, 0),
    impulseClass: getImpulseClass(motor.motorTotalImpulse),
    guideLength,
    guideAngle,
    exitVelocity,
    exitTime,
    safeVelocity,
    windRatio: exitVelocity > 0 ? numberValue(config.windSpeed, 0) / exitVelocity : Infinity,
    burnFraction: exitTime && burnTime > 0 ? exitTime / burnTime : null,
    ok: exitVelocity >= safeVelocity
  };
};

const summarizeRun = ({ label, active, passive = null }) => {
  const activeData = active?.results || {};
  const passiveData = passive?.results || null;
  return {
    id: makeId('case'),
    label,
    createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    active,
    passive,
    apogee: activeData.max_altitude,
    targetApogee: activeData.controller?.target_apogee || null,
    flightTime: activeData.total_flight_time || null,
    touchdown: activeData.landing_velocity,
    landingDeploy: activeData.landing_system?.deploy_actual_altitude_m ?? activeData.landing_system?.deploy_altitude_m ?? null,
    maxDeployment: activeData.active_system?.max_surface_deployment || 0,
    trim: passiveData ? passiveData.max_altitude - activeData.max_altitude : null,
    landingStatus: activeData.landing_system?.touchdown_status || 'n/a'
  };
};

const csvCell = (value) => {
  if (value === null || value === undefined) return '';
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const rowsToCsv = (rows, headers) => [
  headers.join(','),
  ...rows.map((row) => headers.map((key) => csvCell(row[key])).join(','))
].join('\n');

const mergeRowsByTime = (...collections) => {
  const merged = new Map();
  collections.flat().forEach((row) => {
    if (!row || row.time === undefined || row.time === null) return;
    const key = String(row.time);
    merged.set(key, { ...(merged.get(key) || {}), ...row });
  });
  return [...merged.values()].sort((a, b) => numberValue(a.time) - numberValue(b.time));
};

function Field({ label, value, unit, type = 'number', step = 'any', min, max, onChange, options }) {
  const id = `${label.replace(/[^a-z0-9]+/gi, '-')}-${Math.random().toString(36).slice(2)}`;
  return (
    <label className="field" htmlFor={id}>
      <span>{label}</span>
      <div className="field-control">
        {options ? (
          <select
            id={id}
            value={value}
            onChange={(event) => onChange(event.target.value)}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        ) : (
          <input
            id={id}
            type={type}
            step={step}
            min={min}
            max={max}
            value={value ?? ''}
            onChange={(event) => onChange(type === 'number' ? numberValue(event.target.value) : event.target.value)}
          />
        )}
        {unit && <span className="unit">{unit}</span>}
      </div>
    </label>
  );
}

function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button"
      className={`switch ${checked ? 'is-on' : ''}`}
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
    >
      <span className="switch-track"><span className="switch-thumb" /></span>
      <span>{label}</span>
    </button>
  );
}

function LineChart({ title, series, yUnit = '', compact = false }) {
  const cleanSeries = series
    .map((item) => ({
      ...item,
      points: (item.points || []).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    }))
    .filter((item) => item.points.length > 1);
  const all = cleanSeries.flatMap((item) => item.points);

  if (!all.length) {
    return (
      <div className={`chart ${compact ? 'compact' : ''}`}>
        <div className="chart-title">{title}</div>
        <div className="chart-empty">No simulation data yet</div>
      </div>
    );
  }

  const width = 720;
  const height = compact ? 190 : 245;
  const pad = { top: 22, right: 20, bottom: 30, left: 50 };
  const xs = all.map((point) => point.x);
  const ys = all.map((point) => point.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMinRaw = Math.min(...ys);
  const yMaxRaw = Math.max(...ys);
  const yPad = Math.max((yMaxRaw - yMinRaw) * 0.1, Math.abs(yMaxRaw || 1) * 0.04, 0.01);
  const yMin = yMinRaw >= 0 ? 0 : yMinRaw - yPad;
  const yMax = yMaxRaw + yPad;
  const sx = (x) => pad.left + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - pad.left - pad.right);
  const sy = (y) => pad.top + (1 - ((y - yMin) / Math.max(yMax - yMin, 1e-9))) * (height - pad.top - pad.bottom);
  const yTicks = [yMin, (yMin + yMax) / 2, yMax];

  return (
    <div className={`chart ${compact ? 'compact' : ''}`}>
      <div className="chart-row">
        <div className="chart-title">{title}</div>
        <div className="chart-legend">
          {cleanSeries.map((item) => (
            <span key={item.label}><i style={{ backgroundColor: item.color }} />{item.label}</span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label={title}>
        {yTicks.map((tick) => (
          <g key={tick}>
            <line x1={pad.left} x2={width - pad.right} y1={sy(tick)} y2={sy(tick)} className="gridline" />
            <text x={pad.left - 8} y={sy(tick) + 4} textAnchor="end">{formatNumber(tick, 1)}</text>
          </g>
        ))}
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={height - pad.bottom} className="axis" />
        <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} className="axis" />
        <text x={pad.left} y={height - 8}>0s</text>
        <text x={width - pad.right} y={height - 8} textAnchor="end">{formatNumber(xMax, 1)}s</text>
        {yUnit && <text x="10" y="16">{yUnit}</text>}
        {cleanSeries.map((item) => (
          <polyline
            key={item.label}
            className="chart-line"
            style={{ stroke: item.color }}
            points={item.points.map((point) => `${sx(point.x).toFixed(2)},${sy(point.y).toFixed(2)}`).join(' ')}
          />
        ))}
      </svg>
    </div>
  );
}

function RocketDrawing({ components, selectedId, setSelectedId, metrics, results }) {
  const structural = layoutComponents(components);
  const length = Math.max(metrics.totalLength, 1);
  const maxDiameter = Math.max(metrics.maxDiameter, 1);
  const viewWidth = 980;
  const viewHeight = 320;
  const left = 70;
  const right = 880;
  const centerY = 142;
  const pxPerMm = (right - left) / length;
  const diameterScale = Math.min(1.35, 92 / maxDiameter);
  const xFor = (mm) => left + mm * pxPerMm;
  const heightFor = (diameter) => Math.max(12, numberValue(diameter, maxDiameter) * diameterScale);
  const finSet = components.find((component) => component.type === 'Fins');
  const motor = components.find((component) => component.type === 'Motor');
  const landingPoint = results?.landing_system?.deployed ? results.landing_system.deploy_altitude_m : null;
  const cgX = xFor(metrics.cg);
  const cpX = xFor(metrics.cp);

  return (
    <section className="drawing-panel" aria-label="Rocket design view">
      <div className="drawing-toolbar">
        <div>
          <strong>Side view</strong>
          <span>{formatNumber(length, 0)} mm length, {formatNumber(maxDiameter, 0)} mm max diameter</span>
        </div>
        <div className="stability-pill">
          Stability {formatNumber(metrics.stability, 2)} cal
        </div>
      </div>
      <svg className="rocket-svg" viewBox={`0 0 ${viewWidth} ${viewHeight}`} role="img" aria-label="Rocket side profile">
        <rect x="0" y="0" width={viewWidth} height={viewHeight} className="drawing-bg" />
        <line x1={left} x2={right} y1="258" y2="258" className="ruler" />
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const x = left + (right - left) * ratio;
          const value = Math.round(length * ratio);
          return (
            <g key={ratio}>
              <line x1={x} x2={x} y1="250" y2="266" className="ruler-tick" />
              <text x={x} y="285" textAnchor="middle">{value}</text>
            </g>
          );
        })}
        <line x1={left} x2={right} y1={centerY} y2={centerY} className="centerline" />
        {structural.map((component) => {
          const x = xFor(component.start);
          const w = Math.max(3, component.length * pxPerMm);
          const diameter = component.type === 'Transition'
            ? numberValue(component.bottomDiameter, component.diameter)
            : numberValue(component.diameter, maxDiameter);
          const h = heightFor(diameter);
          const topDiameter = heightFor(numberValue(component.topDiameter, diameter));
          const bottomDiameter = heightFor(numberValue(component.bottomDiameter, diameter));
          const selected = selectedId === component.id;
          if (component.type === 'Nose Cone') {
            return (
              <path
                key={component.id}
                className={`rocket-part ${selected ? 'selected' : ''}`}
                fill={componentColor[component.type]}
                d={`M ${x} ${centerY} C ${x + w * 0.18} ${centerY - h / 2}, ${x + w * 0.78} ${centerY - h / 2}, ${x + w} ${centerY - h / 2} L ${x + w} ${centerY + h / 2} C ${x + w * 0.78} ${centerY + h / 2}, ${x + w * 0.18} ${centerY + h / 2}, ${x} ${centerY} Z`}
                onClick={() => setSelectedId(component.id)}
              >
                <title>{component.name}</title>
              </path>
            );
          }
          if (component.type === 'Transition') {
            return (
              <polygon
                key={component.id}
                className={`rocket-part ${selected ? 'selected' : ''}`}
                fill={componentColor[component.type]}
                points={`${x},${centerY - topDiameter / 2} ${x + w},${centerY - bottomDiameter / 2} ${x + w},${centerY + bottomDiameter / 2} ${x},${centerY + topDiameter / 2}`}
                onClick={() => setSelectedId(component.id)}
              >
                <title>{component.name}</title>
              </polygon>
            );
          }
          return (
            <g key={component.id} onClick={() => setSelectedId(component.id)}>
              <rect
                x={x}
                y={centerY - h / 2}
                width={w}
                height={h}
                rx="2"
                className={`rocket-part ${selected ? 'selected' : ''}`}
                fill={componentColor[component.type] || '#ccd3dd'}
              />
              {component.type === 'Active Airbrake' && (
                <>
                  <rect x={x + w * 0.26} y={centerY - h / 2 - 16} width={w * 0.18} height="18" className="airbrake-tab" />
                  <rect x={x + w * 0.56} y={centerY + h / 2 - 2} width={w * 0.18} height="18" className="airbrake-tab" />
                </>
              )}
              <title>{component.name}</title>
            </g>
          );
        })}
        {finSet && (
          <g onClick={() => setSelectedId(finSet.id)}>
            {[-1, 1].map((side) => {
              const baseX = xFor(length - numberValue(finSet.finWidth, 100));
              const tailX = xFor(length - 6);
              const rootY = centerY + side * heightFor(maxDiameter) / 2;
              const tipY = rootY + side * clamp(numberValue(finSet.finHeight, 60), 22, 90);
              return (
                <polygon
                  key={side}
                  className={`rocket-part fin ${selectedId === finSet.id ? 'selected' : ''}`}
                  fill={componentColor.Fins}
                  points={`${baseX},${rootY} ${tailX},${rootY} ${tailX - numberValue(finSet.finSweep, 25) * pxPerMm},${tipY}`}
                />
              );
            })}
            <title>{finSet.name}</title>
          </g>
        )}
        {motor && (
          <g onClick={() => setSelectedId(motor.id)}>
            <rect
              x={xFor(length - numberValue(motor.length, 85))}
              y={centerY - heightFor(numberValue(motor.diameter, 29)) / 2}
              width={numberValue(motor.length, 85) * pxPerMm}
              height={heightFor(numberValue(motor.diameter, 29))}
              rx="4"
              className={`motor-core ${selectedId === motor.id ? 'selected' : ''}`}
            />
            <path
              d={`M ${xFor(length)} ${centerY - 14} L ${xFor(length) + 30} ${centerY} L ${xFor(length)} ${centerY + 14} Z`}
              className="motor-nozzle"
            />
            <title>{motor.name}</title>
          </g>
        )}
        <line x1={cgX} x2={cgX} y1="58" y2="226" className="cg-line" />
        <text x={cgX + 6} y="72" className="marker-label">CG</text>
        <line x1={cpX} x2={cpX} y1="58" y2="226" className="cp-line" />
        <text x={cpX + 6} y="92" className="marker-label">CP</text>
        {landingPoint !== null && (
          <g>
            <line x1="910" x2="910" y1="48" y2="238" className="landing-line" />
            <text x="900" y="64" textAnchor="end" className="marker-label">Landing deploy {formatNumber(landingPoint, 0)} m</text>
          </g>
        )}
      </svg>
    </section>
  );
}

function DesignTree({ components, selectedId, setSelectedId, moveComponent, duplicateComponent, removeComponent }) {
  const groups = [
    ['Airframe', components.filter((component) => structuralTypes.has(component.type) && component.type !== 'Landing System')],
    ['Motor and fins', components.filter((component) => ['Motor', 'Fins'].includes(component.type))],
    ['Recovery and landing', components.filter((component) => component.type === 'Landing System')]
  ];

  return (
    <section className="left-section">
      <div className="section-title">Design tree</div>
      <div className="tree-root">
        <div className="tree-vehicle">ActiveRocket</div>
        {groups.map(([label, items]) => (
          <div className="tree-group" key={label}>
            <div className="tree-group-label">{label}</div>
            {items.map((component) => (
              <div
                key={component.id}
                className={`tree-item ${selectedId === component.id ? 'active' : ''}`}
                onClick={() => setSelectedId(component.id)}
              >
                <span className="part-swatch" style={{ backgroundColor: componentColor[component.type] || '#999' }} />
                <span className="tree-name">{component.name}</span>
                <button type="button" onClick={(event) => { event.stopPropagation(); moveComponent(component.id, -1); }}>Up</button>
                <button type="button" onClick={(event) => { event.stopPropagation(); moveComponent(component.id, 1); }}>Down</button>
                <button type="button" onClick={(event) => { event.stopPropagation(); duplicateComponent(component.id); }}>Copy</button>
                <button type="button" onClick={(event) => { event.stopPropagation(); removeComponent(component.id); }}>Remove</button>
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function ComponentPalette({ addComponent }) {
  const categories = [
    ['Airframe', ['Nose Cone', 'Body Tube', 'Transition', 'Electronics Bay', 'Recovery Bay']],
    ['Control', ['Active Airbrake', 'Fins', 'Rail Button']],
    ['Propulsion and landing', ['Motor', 'Landing System']]
  ];

  return (
    <section className="left-section">
      <div className="section-title">Add component</div>
      {categories.map(([label, types]) => (
        <div className="palette-group" key={label}>
          <div className="palette-label">{label}</div>
          <div className="palette-grid">
            {types.map((type) => (
              <button key={type} type="button" onClick={() => addComponent(type)}>
                <span className="part-swatch" style={{ backgroundColor: componentColor[type] || '#999' }} />
                {type}
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function ComponentTable({ components, selectedId, setSelectedId }) {
  return (
    <section className="table-panel">
      <div className="table-title">Component table</div>
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Length</th>
              <th>Diameter</th>
              <th>Mass</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {components.map((component) => (
              <tr
                key={component.id}
                className={selectedId === component.id ? 'selected-row' : ''}
                onClick={() => setSelectedId(component.id)}
              >
                <td>{component.name}</td>
                <td>{component.type}</td>
                <td>{formatNumber(component.length, 0)} mm</td>
                <td>{formatNumber(getDiameter(component), 0)} mm</td>
                <td>{formatNumber(componentMass(component), 0)} g</td>
                <td>{component.type === 'Motor'
                  ? `${formatNumber(component.motorThrust, 1)} N, ${formatNumber(component.motorTotalImpulse, 1)} Ns`
                  : component.type === 'Fins'
                    ? `${component.finCount} fins, ${formatNumber(component.finHeight, 0)} mm span`
                    : component.material || 'configured'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DesignAnalysis({ metrics, massBreakdown, config }) {
  const cgCpSeparation = metrics.cp - metrics.cg;
  const landingSizing = getLandingSizing(metrics, config);
  const activeEnvelope = getActiveEnvelope(metrics, config);
  const guideAnalysis = getLaunchGuideAnalysis(metrics, config);
  const stabilityState = metrics.stability < 1
    ? { label: 'Low', tone: 'bad' }
    : metrics.stability > 3.5
      ? { label: 'High', tone: 'warn' }
      : { label: 'Nominal', tone: 'good' };
  const thrustState = metrics.thrustToWeight >= 5
    ? { label: 'Strong', tone: 'good' }
    : metrics.thrustToWeight >= 3
      ? { label: 'Usable', tone: 'warn' }
      : { label: 'Low', tone: 'bad' };
  const landingAreaLoading = config.landingSystem.enabled && landingSizing.dragArea > 0
    ? (metrics.mass / 1000) / landingSizing.dragArea
    : null;
  const landingTone = landingSizing.estimatedTerminalVelocity <= landingSizing.safeVelocity
    ? 'good'
    : landingSizing.estimatedTerminalVelocity <= landingSizing.safeVelocity * 1.15
      ? 'warn'
      : 'bad';

  return (
    <div className="analysis-panel">
      <div className="analysis-header">
        <strong>Design analysis</strong>
        <span>{formatNumber(cgCpSeparation, 0)} mm CG to CP</span>
      </div>
      <div className="analysis-grid">
        <div className={`analysis-stat ${stabilityState.tone}`}>
          <span>Static margin</span>
          <strong>{stabilityState.label}</strong>
          <em>{formatNumber(metrics.stability, 2)} cal</em>
        </div>
        <div className={`analysis-stat ${thrustState.tone}`}>
          <span>Lift-off</span>
          <strong>{thrustState.label}</strong>
          <em>{formatNumber(metrics.thrustToWeight, 2)} T/W</em>
        </div>
        <div className={`analysis-stat ${landingTone}`}>
          <span>Landing load</span>
          <strong>{landingAreaLoading === null ? 'Off' : `${formatNumber(landingAreaLoading, 1)} kg/m2`}</strong>
          <em>{formatNumber(landingSizing.estimatedTerminalVelocity, 2)} m/s terminal</em>
        </div>
      </div>
      <div className="envelope-list">
        <div>
          <span>Recovery area margin</span>
          <strong>{landingSizing.areaMargin >= 0 ? '+' : ''}{formatNumber(landingSizing.areaMargin, 3)} m2</strong>
        </div>
        <div>
          <span>Required landing drag</span>
          <strong>{formatNumber(landingSizing.requiredArea, 3)} m2</strong>
        </div>
        <div>
          <span>Airbrake Cd authority</span>
          <strong>+{formatNumber(activeEnvelope.cdIncrement, 2)}</strong>
        </div>
        <div>
          <span>Active deployed area</span>
          <strong>{formatNumber(activeEnvelope.deployedArea, 4)} m2</strong>
        </div>
        <div>
          <span>Guide exit velocity</span>
          <strong>{formatNumber(guideAnalysis.exitVelocity, 2)} m/s</strong>
        </div>
        <div>
          <span>Motor impulse class</span>
          <strong>{guideAnalysis.impulseClass} / {formatNumber(guideAnalysis.totalImpulse, 1)} Ns</strong>
        </div>
      </div>
      <div className="cp-breakdown">
        <div className="cp-breakdown-title">
          <strong>CP contributors</strong>
          <span>CNa {formatNumber(metrics.cpAnalysis.totalNormalForce, 2)}</span>
        </div>
        {metrics.cpAnalysis.contributions.map((item) => (
          <div className="cp-row" key={item.id}>
            <span className="mass-swatch" style={{ backgroundColor: item.color }} />
            <strong>{item.name}</strong>
            <em>{formatNumber(item.cp, 0)} mm</em>
            <b>{formatNumber(item.share, 0)}%</b>
          </div>
        ))}
      </div>
      <div className="mass-breakdown" aria-label="Mass breakdown">
        {massBreakdown.map((row) => (
          <div className="mass-row" key={row.key}>
            <div className="mass-label">
              <span className="mass-swatch" style={{ backgroundColor: row.color }} />
              <strong>{row.label}</strong>
              <em>{formatNumber(row.mass, 0)} g</em>
            </div>
            <div className="mass-track">
              <span style={{ width: `${clamp(row.percent, 3, 100)}%`, backgroundColor: row.color }} />
            </div>
            <b>{formatNumber(row.percent, 0)}%</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function ComponentInspector({ component, updateComponent }) {
  if (!component) {
    return (
      <div className="empty-state">
        Select a component in the tree or drawing.
      </div>
    );
  }

  const set = (key, value) => updateComponent(component.id, { [key]: value });
  const commonFields = (
    <>
      <Field label="Name" type="text" value={component.name} onChange={(value) => set('name', value)} />
      <Field label="Length" value={component.length} unit="mm" onChange={(value) => set('length', value)} />
      <Field label="Diameter" value={component.diameter} unit="mm" onChange={(value) => set('diameter', value)} />
      <Field label="Mass" value={componentMass(component)} unit="g" onChange={(value) => set(component.type === 'Motor' ? 'motorWeight' : 'weight', value)} />
    </>
  );

  return (
    <div className="inspector-scroll">
      <div className="inspector-heading">
        <span className="part-swatch" style={{ backgroundColor: componentColor[component.type] || '#999' }} />
        <div>
          <h2>{component.name}</h2>
          <p>{component.type}</p>
        </div>
      </div>
      <div className="field-grid single">
        {commonFields}
        {component.type === 'Transition' && (
          <>
            <Field label="Top diameter" value={component.topDiameter} unit="mm" onChange={(value) => set('topDiameter', value)} />
            <Field label="Bottom diameter" value={component.bottomDiameter} unit="mm" onChange={(value) => set('bottomDiameter', value)} />
          </>
        )}
        {component.type === 'Nose Cone' && (
          <Field
            label="Shape"
            value={component.shape || 'ogive'}
            onChange={(value) => set('shape', value)}
            options={[
              { value: 'ogive', label: 'Ogive' },
              { value: 'conical', label: 'Conical' },
              { value: 'elliptical', label: 'Elliptical' },
              { value: 'von-karman', label: 'Von Karman' }
            ]}
          />
        )}
        {component.type === 'Fins' && (
          <>
            <Field label="Fin count" value={component.finCount} onChange={(value) => set('finCount', value)} />
            <Field label="Root chord" value={component.finWidth} unit="mm" onChange={(value) => set('finWidth', value)} />
            <Field label="Span" value={component.finHeight} unit="mm" onChange={(value) => set('finHeight', value)} />
            <Field label="Sweep" value={component.finSweep} unit="mm" onChange={(value) => set('finSweep', value)} />
            <Field label="Thickness" value={component.finThickness} unit="mm" onChange={(value) => set('finThickness', value)} />
          </>
        )}
        {component.type === 'Active Airbrake' && (
          <>
            <Field label="Surface count" value={component.surfaceCount} onChange={(value) => set('surfaceCount', value)} />
            <Field label="Surface area" value={component.surfaceArea} unit="m2" step="0.0001" onChange={(value) => set('surfaceArea', value)} />
            <Field label="Max angle" value={component.surfaceMaxAngle} unit="deg" onChange={(value) => set('surfaceMaxAngle', value)} />
          </>
        )}
        {component.type === 'Motor' && (
          <>
            <Field label="Manufacturer" type="text" value={component.motorType || ''} onChange={(value) => set('motorType', value)} />
            <Field label="Designation" type="text" value={component.motorModel || ''} onChange={(value) => set('motorModel', value)} />
            <Field label="Avg thrust" value={component.motorThrust} unit="N" onChange={(value) => set('motorThrust', value)} />
            <Field label="Burn time" value={component.motorBurnTime} unit="s" onChange={(value) => set('motorBurnTime', value)} />
            <Field label="Total impulse" value={component.motorTotalImpulse} unit="Ns" onChange={(value) => set('motorTotalImpulse', value)} />
            <Field label="Delay" value={component.motorDelay} unit="s" onChange={(value) => set('motorDelay', value)} />
          </>
        )}
        {component.type === 'Landing System' && (
          <>
            <Field label="Deploy altitude" value={component.deployAltitude} unit="m" onChange={(value) => set('deployAltitude', value)} />
            <Field label="Drag area" value={component.dragArea} unit="m2" step="0.01" onChange={(value) => set('dragArea', value)} />
            <Field label="Drag coefficient" value={component.dragCoefficient} step="0.01" onChange={(value) => set('dragCoefficient', value)} />
            <Field label="Drogue area" value={component.drogueDragArea ?? 0.04} unit="m2" step="0.005" onChange={(value) => set('drogueDragArea', value)} />
            <Field label="Drogue Cd" value={component.drogueDragCoefficient ?? 1.25} step="0.01" onChange={(value) => set('drogueDragCoefficient', value)} />
            <Field label="Safe touchdown" value={component.maxSafeVelocity} unit="m/s" step="0.1" onChange={(value) => set('maxSafeVelocity', value)} />
          </>
        )}
      </div>
    </div>
  );
}

function MotorBrowser({ motors, loading, error, query, setQuery, addMotor }) {
  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    const base = text
      ? motors.filter((motor) => (
        motor.displayName.toLowerCase().includes(text) ||
        motor.impulse.toLowerCase().includes(text) ||
        motor.manufacturer.toLowerCase().includes(text)
      ))
      : motors;
    return base.slice(0, 36);
  }, [motors, query]);

  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Motor database</h2>
        <p>Search installed motor curves and add one to the aft mount.</p>
      </div>
      <Field label="Search" type="text" value={query} onChange={setQuery} />
      {loading && <div className="inline-status">Loading motors...</div>}
      {error && <div className="inline-status error">{error}</div>}
      <div className="motor-list">
        {filtered.map((motor) => (
          <button key={motor.id} type="button" className="motor-row" onClick={() => addMotor(motor)}>
            <strong>{motor.displayName}</strong>
            <span>{motor.impulse} class</span>
            <span>{formatNumber(motor.totalImpulse, 1)} Ns</span>
            <span>{formatNumber(motor.thrust, 1)} N avg</span>
            <span>{formatNumber(motor.length, 0)} x {formatNumber(motor.diameter, 0)} mm</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function FlightSetup({ config, setConfig, launchSites, applyLaunchSite, metrics }) {
  const set = (key, value) => setConfig((current) => ({ ...current, [key]: value }));
  const guide = getLaunchGuideAnalysis(metrics, config);
  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Flight setup</h2>
        <p>Launch conditions, solver timing, and target apogee.</p>
      </div>
      <div className="field-grid single">
        <label className="field" htmlFor="launch-site">
          <span>Launch site</span>
          <div className="field-control">
            <select id="launch-site" value={config.launchSite} onChange={(event) => applyLaunchSite(event.target.value)}>
              <option value="custom">Custom</option>
              {launchSites.map((site) => (
                <option key={site.id} value={site.id}>{site.label}</option>
              ))}
            </select>
          </div>
        </label>
        <Field label="Launch altitude" value={config.launchAltitude} unit="m" onChange={(value) => set('launchAltitude', value)} />
        <Field label="Temperature" value={config.temperature} unit="C" onChange={(value) => set('temperature', value)} />
        <Field label="Pressure" value={config.pressure} unit="Pa" onChange={(value) => set('pressure', value)} />
        <Field label="Wind speed" value={config.windSpeed} unit="m/s" step="0.1" onChange={(value) => set('windSpeed', value)} />
        <Field label="Wind direction" value={config.windDirection} unit="deg" onChange={(value) => set('windDirection', value)} />
        <Field label="Guide length" value={config.launchGuideLength} unit="m" step="0.1" onChange={(value) => set('launchGuideLength', value)} />
        <Field label="Guide angle" value={config.launchGuideAngle} unit="deg" step="0.5" onChange={(value) => set('launchGuideAngle', value)} />
        <Field label="Guide direction" value={config.launchGuideDirection} unit="deg" onChange={(value) => set('launchGuideDirection', value)} />
        <Field label="Min guide speed" value={config.minRailExitVelocity} unit="m/s" step="0.5" onChange={(value) => set('minRailExitVelocity', value)} />
        <Field label="Time step" value={config.timeStep} unit="s" step="0.005" onChange={(value) => set('timeStep', value)} />
        <Field label="Max time" value={config.maxTime} unit="s" onChange={(value) => set('maxTime', value)} />
        <Field
          label="Controller mode"
          value={config.controller.mode}
          onChange={(value) => setConfig((current) => ({ ...current, controller: { ...current.controller, mode: value } }))}
          options={[
            { value: 'target_apogee', label: 'Target apogee' },
            { value: 'descent_brake', label: 'Descent brake' },
            { value: 'disabled', label: 'Disabled' }
          ]}
        />
        <Field
          label="Target apogee"
          value={config.controller.targetApogee}
          unit="m"
          onChange={(value) => setConfig((current) => ({ ...current, controller: { ...current.controller, targetApogee: value } }))}
        />
      </div>
      <div className="sizing-card">
        <div className="comparison-title">Launch guide</div>
        <div className="sizing-grid">
          <div><span>Exit velocity</span><strong>{formatNumber(guide.exitVelocity, 2)} m/s</strong></div>
          <div><span>Status</span><strong>{guide.ok ? 'Safe' : 'Slow'}</strong></div>
          <div><span>Clear time</span><strong>{guide.exitTime === null ? '--' : `${formatNumber(guide.exitTime, 2)} s`}</strong></div>
          <div><span>Burn at clear</span><strong>{guide.burnFraction === null ? '--' : `${formatNumber(guide.burnFraction * 100, 0)}%`}</strong></div>
          <div><span>Wind / exit</span><strong>{formatNumber(guide.windRatio * 100, 0)}%</strong></div>
          <div><span>Impulse class</span><strong>{guide.impulseClass}</strong></div>
        </div>
      </div>
    </div>
  );
}

function ActiveSetup({ config, setConfig, syncAirbrake }) {
  const active = config.activeSystem;
  const controller = config.controller;
  const setActive = (key, value) => setConfig((current) => ({
    ...current,
    activePneumaticEnabled: key === 'enabled' ? value : current.activePneumaticEnabled,
    activeSystem: { ...current.activeSystem, [key]: value }
  }));
  const setController = (key, value) => setConfig((current) => ({
    ...current,
    controller: { ...current.controller, [key]: value }
  }));

  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Active airbrake</h2>
        <p>Pneumatic surfaces, pressure limits, and apogee control.</p>
      </div>
      <Toggle checked={active.enabled} onChange={(value) => setActive('enabled', value)} label="Active pneumatic system" />
      <div className="field-grid single">
        <Field label="Tank pressure" value={active.tankPressure} unit="Pa" onChange={(value) => setActive('tankPressure', value)} />
        <Field label="Tank volume" value={active.tankVolume} unit="L" step="0.01" onChange={(value) => setActive('tankVolume', value)} />
        <Field label="Regulator pressure" value={active.regulatorPressure} unit="Pa" onChange={(value) => setActive('regulatorPressure', value)} />
        <Field label="Valve flow" value={active.valveFlowRate} step="0.1" onChange={(value) => setActive('valveFlowRate', value)} />
        <Field label="Cylinder bore" value={active.cylinderBore} unit="m" step="0.001" onChange={(value) => setActive('cylinderBore', value)} />
        <Field label="Cylinder stroke" value={active.cylinderStroke} unit="m" step="0.001" onChange={(value) => setActive('cylinderStroke', value)} />
        <Field label="Surface count" value={active.surfaceCount} onChange={(value) => { setActive('surfaceCount', value); syncAirbrake('surfaceCount', value); }} />
        <Field label="Surface area" value={active.surfaceArea} unit="m2" step="0.0001" onChange={(value) => { setActive('surfaceArea', value); syncAirbrake('surfaceArea', value); }} />
        <Field label="Max angle" value={active.surfaceMaxAngle} unit="deg" onChange={(value) => { setActive('surfaceMaxAngle', value); syncAirbrake('surfaceMaxAngle', value); }} />
        <Field label="Deploy altitude" value={controller.deployAltitude} unit="m" onChange={(value) => setController('deployAltitude', value)} />
        <Field label="Kp" value={controller.kp} step="0.001" onChange={(value) => setController('kp', value)} />
        <Field label="Kd" value={controller.kd} step="0.001" onChange={(value) => setController('kd', value)} />
      </div>
    </div>
  );
}

function LandingSetup({ config, setConfig, syncLanding, metrics }) {
  const landing = config.landingSystem;
  const mainDeployEvent = landing.mainDeployEvent || landing.deployEvent || 'altitude';
  const drogueDeployEvent = landing.drogueDeployEvent || 'apogee';
  const sizing = getLandingSizing(metrics, config);
  const drogueSizing = getLandingSizing(metrics, config, {
    dragArea: landing.drogueDragArea,
    dragCoefficient: landing.drogueDragCoefficient,
    maxSafeVelocity: 25
  });
  const setLanding = (key, value) => {
    setConfig((current) => ({
      ...current,
      landingSystem: { ...current.landingSystem, [key]: value }
    }));
    syncLanding(key, value);
  };
  const applyLandingSizing = (targetVelocity = landing.maxSafeVelocity) => {
    const nextSizing = getLandingSizing(metrics, config, { maxSafeVelocity: targetVelocity });
    const nextArea = Math.ceil(nextSizing.requiredArea * 1000) / 1000;
    setLanding('maxSafeVelocity', targetVelocity);
    setLanding('dragArea', Number(nextArea.toFixed(3)));
  };

  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Landing system</h2>
        <p>Recovery deployment and touchdown constraints.</p>
      </div>
      <Toggle checked={landing.enabled} onChange={(value) => setLanding('enabled', value)} label="Landing recovery enabled" />
      <div className="field-grid single">
        <Field
          label="System type"
          value={landing.type}
          onChange={(value) => setLanding('type', value)}
          options={[
            { value: 'main_parachute', label: 'Main parachute' },
            { value: 'drogue_main', label: 'Drogue plus main' },
            { value: 'active_drag_landing', label: 'Active drag landing' }
          ]}
        />
        {landing.type === 'drogue_main' && (
          <>
            <Field
              label="Drogue event"
              value={drogueDeployEvent}
              onChange={(value) => setLanding('drogueDeployEvent', value)}
              options={recoveryDeployEvents}
            />
            {drogueDeployEvent === 'altitude' && (
              <Field
                label="Drogue altitude"
                value={landing.drogueDeployAltitude ?? landing.deployAltitude}
                unit="m"
                onChange={(value) => setLanding('drogueDeployAltitude', value)}
              />
            )}
          </>
        )}
        <Field
          label={landing.type === 'drogue_main' ? 'Main event' : 'Deploy event'}
          value={mainDeployEvent}
          onChange={(value) => setLanding('mainDeployEvent', value)}
          options={recoveryDeployEvents}
        />
        {mainDeployEvent === 'altitude' && (
          <Field label={landing.type === 'drogue_main' ? 'Main altitude' : 'Deploy altitude'} value={landing.deployAltitude} unit="m" onChange={(value) => setLanding('deployAltitude', value)} />
        )}
        <Field label={landing.type === 'drogue_main' ? 'Main area' : 'Drag area'} value={landing.dragArea} unit="m2" step="0.01" onChange={(value) => setLanding('dragArea', value)} />
        <Field label={landing.type === 'drogue_main' ? 'Main Cd' : 'Drag coefficient'} value={landing.dragCoefficient} step="0.01" onChange={(value) => setLanding('dragCoefficient', value)} />
        {landing.type === 'drogue_main' && (
          <>
            <Field label="Drogue area" value={landing.drogueDragArea} unit="m2" step="0.005" onChange={(value) => setLanding('drogueDragArea', value)} />
            <Field label="Drogue Cd" value={landing.drogueDragCoefficient} step="0.01" onChange={(value) => setLanding('drogueDragCoefficient', value)} />
          </>
        )}
        <Field label="Safe touchdown" value={landing.maxSafeVelocity} unit="m/s" step="0.1" onChange={(value) => setLanding('maxSafeVelocity', value)} />
      </div>
      <div className="sizing-card">
        <div className="comparison-title">Recovery sequence</div>
        <div className="sequence-list">
          {landing.type === 'drogue_main' && (
            <div className="sequence-row">
              <span>Drogue</span>
              <strong>{recoveryEventLabel(drogueDeployEvent)}</strong>
              <em>{recoveryEventDetail(drogueDeployEvent, landing.drogueDeployAltitude ?? landing.deployAltitude)}</em>
            </div>
          )}
          <div className="sequence-row">
            <span>{landing.type === 'drogue_main' ? 'Main' : 'Recovery'}</span>
            <strong>{recoveryEventLabel(mainDeployEvent)}</strong>
            <em>{recoveryEventDetail(mainDeployEvent, landing.deployAltitude)}</em>
          </div>
        </div>
      </div>
      <div className="sizing-card">
        <div className="comparison-title">Recovery sizing</div>
        <div className="sizing-grid">
          <div><span>Required area</span><strong>{formatNumber(sizing.requiredArea, 3)} m2</strong></div>
          <div><span>Current terminal</span><strong>{formatNumber(sizing.estimatedTerminalVelocity, 2)} m/s</strong></div>
          <div><span>Area margin</span><strong>{sizing.areaMargin >= 0 ? '+' : ''}{formatNumber(sizing.areaMargin, 3)} m2</strong></div>
          <div><span>Air density</span><strong>{formatNumber(sizing.density, 2)} kg/m3</strong></div>
          {landing.type === 'drogue_main' && (
            <>
              <div><span>Drogue descent</span><strong>{formatNumber(drogueSizing.estimatedTerminalVelocity, 2)} m/s</strong></div>
              <div><span>Drogue drag area</span><strong>{formatNumber(landing.drogueDragArea, 3)} m2</strong></div>
            </>
          )}
        </div>
        <div className="sizing-actions">
          <button type="button" onClick={() => applyLandingSizing(numberValue(landing.maxSafeVelocity, 7.5))}>
            Size to limit
          </button>
          <button type="button" onClick={() => applyLandingSizing(6)}>
            Target 6 m/s
          </button>
        </div>
      </div>
      <div className="landing-presets">
        <button type="button" onClick={() => {
          setLanding('dragArea', 0.16);
          setLanding('deployAltitude', 90);
          setLanding('maxSafeVelocity', 8.5);
        }}>Compact</button>
        <button type="button" onClick={() => {
          setLanding('dragArea', 0.24);
          setLanding('deployAltitude', 120);
          setLanding('drogueDragArea', 0.04);
          setLanding('maxSafeVelocity', 7.5);
        }}>Balanced</button>
        <button type="button" onClick={() => {
          setLanding('dragArea', 0.34);
          setLanding('deployAltitude', 150);
          setLanding('maxSafeVelocity', 6);
        }}>Gentle</button>
      </div>
    </div>
  );
}

function ResultsPanel({
  result,
  comparisonResult,
  simulationCases,
  selectedCaseId,
  onSelectCase,
  metrics,
  exportResults
}) {
  const data = result?.results;
  const comparisonData = comparisonResult?.results;
  const trajectory = data?.trajectory || [];
  const activeHistory = data?.active_system?.history || [];
  const landingHistory = data?.landing_system?.history || [];
  const controllerHistory = data?.controller?.history || [];
  const forceHistory = data?.force_history || [];
  const momentHistory = data?.moment_history || [];
  const touchdown = data?.landing_system;
  const launchGuide = data?.launch_guide;
  const recoveryTiming = data?.recovery_timing;
  const events = data?.flight_events || [];
  const apogeeTrim = comparisonData ? comparisonData.max_altitude - data.max_altitude : null;
  const touchdownDelta = comparisonData ? comparisonData.landing_velocity - data.landing_velocity : null;
  const targetError = data.controller?.target_apogee
    ? data.max_altitude - data.controller.target_apogee
    : null;
  const landingMargin = touchdown?.max_safe_velocity_mps
    ? touchdown.max_safe_velocity_mps - data.landing_velocity
    : null;
  const activeDeployment = data.active_system?.max_surface_deployment || 0;
  const tuningNotes = [
    targetError === null
      ? null
      : {
        label: 'Apogee target',
        status: Math.abs(targetError) <= 10 ? 'good' : targetError > 0 ? 'warn' : 'info',
        detail: `${targetError > 0 ? '+' : ''}${formatNumber(targetError, 1)} m from target`
      },
    {
      label: 'Airbrake authority',
      status: activeDeployment > 0.95 ? 'warn' : activeDeployment < 0.02 ? 'info' : 'good',
      detail: activeDeployment > 0.95
        ? 'Fully saturated during ascent'
        : activeDeployment < 0.02
          ? 'Barely deployed'
          : `${formatNumber(activeDeployment * 100, 0)}% max deployment`
    },
    landingMargin === null
      ? null
      : {
        label: 'Landing margin',
        status: landingMargin >= 1 ? 'good' : landingMargin >= 0 ? 'warn' : 'bad',
        detail: `${formatNumber(landingMargin, 2)} m/s below limit`
      },
    recoveryTiming
      ? {
        label: 'Motor delay',
        status: recoveryTiming.status === 'optimal'
          ? 'good'
          : Math.abs(recoveryTiming.timing_error_s) <= 2.5
            ? 'warn'
            : 'bad',
        detail: `${recoveryTiming.timing_error_s >= 0 ? '+' : ''}${formatNumber(recoveryTiming.timing_error_s, 2)} s from apogee; optimal ${formatNumber(recoveryTiming.optimal_delay_s, 1)} s`
      }
      : null
  ].filter(Boolean);

  if (!data) {
    return (
      <div className="empty-state">
        Run the local active simulation to populate flight results.
      </div>
    );
  }

  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Flight results</h2>
        <p>{data.model_version || data.source}</p>
      </div>
      <div className="metric-grid">
        <div className="metric-box"><span>Apogee</span><strong>{formatNumber(data.max_altitude, 1)} m</strong></div>
        <div className="metric-box"><span>Max speed</span><strong>{formatNumber(data.max_velocity, 1)} m/s</strong></div>
        <div className="metric-box"><span>Touchdown</span><strong>{formatNumber(data.landing_velocity, 2)} m/s</strong></div>
        <div className="metric-box"><span>Status</span><strong>{touchdown?.touchdown_status || 'n/a'}</strong></div>
        <div className="metric-box"><span>Downrange</span><strong>{formatNumber(data.downrange_distance, 1)} m</strong></div>
        <div className="metric-box"><span>Guide exit</span><strong>{formatNumber(launchGuide?.simulated_exit_velocity_mps ?? launchGuide?.estimated_exit_velocity_mps, 2)} m/s</strong></div>
        <div className="metric-box"><span>Motor delay</span><strong>{formatNumber(recoveryTiming?.motor_delay_s, 1)} s</strong></div>
        <div className="metric-box"><span>Stability</span><strong>{formatNumber(metrics.stability, 2)} cal</strong></div>
      </div>
      {comparisonData && (
        <div className="comparison-panel">
          <div className="comparison-title">Active vs passive comparison</div>
          <div className="comparison-grid">
            <div><span>Passive apogee</span><strong>{formatNumber(comparisonData.max_altitude, 1)} m</strong></div>
            <div><span>Apogee trimmed</span><strong>{formatNumber(apogeeTrim, 1)} m</strong></div>
            <div><span>Passive touchdown</span><strong>{formatNumber(comparisonData.landing_velocity, 2)} m/s</strong></div>
            <div><span>Touchdown delta</span><strong>{formatNumber(touchdownDelta, 2)} m/s</strong></div>
          </div>
        </div>
      )}
      <div className="tuning-panel">
        <div className="comparison-title">Tuning notes</div>
        <div className="tuning-list">
          {tuningNotes.map((note) => (
            <div className={`tuning-row ${note.status}`} key={note.label}>
              <span>{note.status}</span>
              <strong>{note.label}</strong>
              <em>{note.detail}</em>
            </div>
          ))}
        </div>
      </div>
      {simulationCases.length > 0 && (
        <div className="case-panel">
          <div className="comparison-title">Simulation cases</div>
          <div className="case-table-wrap">
            <table className="case-table">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Time</th>
                  <th>Apogee</th>
                  <th>Trim</th>
                  <th>Airbrake</th>
                  <th>Deploy</th>
                  <th>Touchdown</th>
                </tr>
              </thead>
              <tbody>
                {simulationCases.map((runCase) => (
                  <tr
                    key={runCase.id}
                    className={runCase.id === selectedCaseId ? 'active-case' : ''}
                    role="button"
                    tabIndex={0}
                    onClick={() => onSelectCase(runCase)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onSelectCase(runCase);
                      }
                    }}
                  >
                    <td>{runCase.label}</td>
                    <td>{runCase.createdAt}</td>
                    <td>{formatNumber(runCase.apogee, 1)} m</td>
                    <td>{runCase.trim === null ? '--' : `${formatNumber(runCase.trim, 1)} m`}</td>
                    <td>{formatNumber(runCase.maxDeployment * 100, 0)}%</td>
                    <td>{runCase.landingDeploy === null ? '--' : `${formatNumber(runCase.landingDeploy, 0)} m`}</td>
                    <td>{formatNumber(runCase.touchdown, 2)} m/s {runCase.landingStatus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <div className="event-panel">
        <div className="comparison-title">Flight events</div>
        <div className="event-list">
          {events.map((event) => (
            <div className={`event-row ${event.type}`} key={`${event.name}-${event.time}`}>
              <span>{formatNumber(event.time, 2)} s</span>
              <strong>{event.name}</strong>
              <em>{formatNumber(event.value, event.unit === '%' ? 1 : 2)} {event.unit}</em>
            </div>
          ))}
        </div>
      </div>
      <LineChart
        compact
        title="Altitude and velocity"
        yUnit="m / mps"
        series={[
          { label: 'Altitude', color: '#d9514e', points: trajectory.map((row) => ({ x: row.time, y: row.altitude })) },
          { label: 'Vertical speed', color: '#4d908e', points: trajectory.map((row) => ({ x: row.time, y: row.velocity_z })) },
          ...(comparisonData ? [{
            label: 'Passive altitude',
            color: '#8b97a6',
            points: (comparisonData.trajectory || []).map((row) => ({ x: row.time, y: row.altitude }))
          }] : [])
        ]}
      />
      <LineChart
        compact
        title="Force balance"
        yUnit="N"
        series={[
          { label: 'Thrust', color: '#343a40', points: forceHistory.map((row) => ({ x: row.time, y: row.thrust_force })) },
          { label: 'Drag', color: '#d9514e', points: forceHistory.map((row) => ({ x: row.time, y: row.drag_force })) },
          { label: 'Weight', color: '#8b97a6', points: forceHistory.map((row) => ({ x: row.time, y: row.weight_force })) },
          { label: 'Net Z', color: '#2a9d8f', points: forceHistory.map((row) => ({ x: row.time, y: row.net_force_z })) }
        ]}
      />
      <LineChart
        compact
        title="Active and landing deployment"
        yUnit="%"
        series={[
          { label: 'Airbrake', color: '#f2a541', points: activeHistory.map((row) => ({ x: row.time, y: row.surface_deployment * 100 })) },
          { label: 'Landing', color: '#7b61ff', points: landingHistory.map((row) => ({ x: row.time, y: row.deployment * 100 })) },
          { label: 'Drogue', color: '#4d908e', points: landingHistory.map((row) => ({ x: row.time, y: (row.drogue_deployment || 0) * 100 })) },
          { label: 'Main', color: '#d9514e', points: landingHistory.map((row) => ({ x: row.time, y: (row.main_deployment || 0) * 100 })) }
        ]}
      />
      <LineChart
        compact
        title="Pneumatic and aero pressure"
        yUnit="kPa"
        series={[
          { label: 'Tank', color: '#f2a541', points: activeHistory.map((row) => ({ x: row.time, y: row.tank_pressure / 1000 })) },
          { label: 'Actuator', color: '#7b61ff', points: activeHistory.map((row) => ({ x: row.time, y: row.actuator_pressure / 1000 })) },
          { label: 'Dynamic q', color: '#4d908e', points: forceHistory.map((row) => ({ x: row.time, y: row.dynamic_pressure / 1000 })) }
        ]}
      />
      <LineChart
        compact
        title="Controller and drag"
        yUnit="Cd / %"
        series={[
          { label: 'Drag Cd', color: '#d9514e', points: trajectory.map((row) => ({ x: row.time, y: row.drag_coefficient })) },
          { label: 'Command', color: '#343a40', points: controllerHistory.map((row) => ({ x: row.time, y: row.command * 100 })) },
          { label: 'Target', color: '#f2a541', points: controllerHistory.map((row) => ({ x: row.time, y: row.surface_target * 100 })) }
        ]}
      />
      <LineChart
        compact
        title="Attitude moments"
        yUnit="Nm"
        series={[
          { label: 'Pitch', color: '#d9514e', points: momentHistory.map((row) => ({ x: row.time, y: row.pitch_moment })) },
          { label: 'Yaw', color: '#4d908e', points: momentHistory.map((row) => ({ x: row.time, y: row.yaw_moment })) },
          { label: 'Roll', color: '#343a40', points: momentHistory.map((row) => ({ x: row.time, y: row.roll_moment })) }
        ]}
      />
      <div className="result-actions">
        <button type="button" onClick={() => exportResults('json')}>Export JSON</button>
        <button type="button" onClick={() => exportResults('trajectory')}>Trajectory CSV</button>
        <button type="button" onClick={() => exportResults('forces')}>Force/moment CSV</button>
        <button type="button" onClick={() => exportResults('active')}>Active CSV</button>
        <button type="button" onClick={() => exportResults('recovery')}>Recovery CSV</button>
      </div>
      {data.warnings?.length ? (
        <div className="warning-list">
          {data.warnings.map((warning) => <div key={warning}>{warning}</div>)}
        </div>
      ) : null}
    </div>
  );
}

function App() {
  const [components, setComponents] = useState(defaultComponents);
  const [selectedId, setSelectedId] = useState(defaultComponents[0].id);
  const [config, setConfig] = useState(defaultConfig);
  const [inspectorTab, setInspectorTab] = useState('component');
  const [motors, setMotors] = useState([]);
  const [motorQuery, setMotorQuery] = useState('');
  const [motorsLoading, setMotorsLoading] = useState(false);
  const [motorError, setMotorError] = useState('');
  const [launchSites, setLaunchSites] = useState([]);
  const [apiStatus, setApiStatus] = useState('checking');
  const [runState, setRunState] = useState('idle');
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [simulationCases, setSimulationCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const fileInputRef = useRef(null);
  const metrics = useMemo(() => getMetrics(components), [components]);
  const massBreakdown = useMemo(() => getMassBreakdown(components), [components]);
  const landingSizing = useMemo(() => getLandingSizing(metrics, config), [metrics, config]);
  const activeEnvelope = useMemo(() => getActiveEnvelope(metrics, config), [metrics, config]);
  const guideAnalysis = useMemo(() => getLaunchGuideAnalysis(metrics, config), [metrics, config]);
  const selectedComponent = components.find((component) => component.id === selectedId);

  const staleResults = () => {
    setResult(null);
    setComparisonResult(null);
    setSelectedCaseId(null);
  };

  const setConfigAndInvalidate = (updater) => {
    setConfig(updater);
    staleResults();
  };

  useEffect(() => {
    let cancelled = false;
    const loadEnvironment = async () => {
      if (!API_URL) {
        setApiStatus('offline');
        return;
      }
      try {
        const [healthResponse, motorsResponse, sitesResponse] = await Promise.all([
          fetch(`${API_URL}/api/health`),
          fetch(`${API_URL}/api/environment/motors`),
          fetch(`${API_URL}/api/environment/launch-sites`)
        ]);
        if (cancelled) return;
        setApiStatus(healthResponse.ok ? 'ready' : 'offline');
        if (motorsResponse.ok) {
          const motorsData = await motorsResponse.json();
          setMotors((motorsData.motors || []).map(normalizeMotor));
        }
        if (sitesResponse.ok) {
          const siteData = await sitesResponse.json();
          setLaunchSites(Object.entries(siteData.launch_sites || {}).map(normalizeSite));
        }
      } catch (error) {
        if (!cancelled) {
          setApiStatus('offline');
          setMotorError(error.message);
        }
      } finally {
        if (!cancelled) setMotorsLoading(false);
      }
    };
    setMotorsLoading(true);
    loadEnvironment();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const airbrake = components.find((component) => component.type === 'Active Airbrake');
    const landing = components.find((component) => component.type === 'Landing System');
    setConfig((current) => ({
      ...current,
      activeSystem: airbrake ? {
        ...current.activeSystem,
        surfaceCount: numberValue(airbrake.surfaceCount, current.activeSystem.surfaceCount),
        surfaceArea: numberValue(airbrake.surfaceArea, current.activeSystem.surfaceArea),
        surfaceMaxAngle: numberValue(airbrake.surfaceMaxAngle, current.activeSystem.surfaceMaxAngle)
      } : current.activeSystem,
      landingSystem: landing ? {
        ...current.landingSystem,
        deployAltitude: numberValue(landing.deployAltitude, current.landingSystem.deployAltitude),
        dragArea: numberValue(landing.dragArea, current.landingSystem.dragArea),
        dragCoefficient: numberValue(landing.dragCoefficient, current.landingSystem.dragCoefficient),
        drogueDragArea: numberValue(landing.drogueDragArea, current.landingSystem.drogueDragArea),
        drogueDragCoefficient: numberValue(landing.drogueDragCoefficient, current.landingSystem.drogueDragCoefficient),
        maxSafeVelocity: numberValue(landing.maxSafeVelocity, current.landingSystem.maxSafeVelocity)
      } : current.landingSystem
    }));
  }, [components]);

  const updateComponent = (id, patch) => {
    setComponents((current) => current.map((component) => (
      component.id === id ? { ...component, ...patch } : component
    )));
    staleResults();
  };

  const syncAirbrake = (key, value) => {
    setComponents((current) => current.map((component) => (
      component.type === 'Active Airbrake' ? { ...component, [key]: value } : component
    )));
  };

  const syncLanding = (key, value) => {
    setComponents((current) => current.map((component) => (
      component.type === 'Landing System' ? { ...component, [key]: value } : component
    )));
  };

  const addComponent = (type) => {
    const next = cloneComponent(type);
    if (type === 'Fins' || type === 'Motor') {
      const aftTube = [...components].reverse().find((component) => ['Body Tube', 'Transition'].includes(component.type));
      if (aftTube) next.attachedToComponent = aftTube.id;
    }
    setComponents((current) => [...current, next]);
    setSelectedId(next.id);
    setInspectorTab('component');
    staleResults();
  };

  const removeComponent = (id) => {
    setComponents((current) => {
      const next = current.filter((component) => component.id !== id);
      if (id === selectedId) setSelectedId(next[0]?.id || null);
      return next;
    });
    staleResults();
  };

  const moveComponent = (id, direction) => {
    setComponents((current) => {
      const index = current.findIndex((component) => component.id === id);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      return next;
    });
    staleResults();
  };

  const duplicateComponent = (id) => {
    const source = components.find((component) => component.id === id);
    if (!source) return;
    const copy = {
      ...source,
      id: makeId(source.type.toLowerCase().replace(/[^a-z0-9]+/g, '-')),
      name: `${source.name} copy`
    };
    const index = components.findIndex((component) => component.id === id);
    setComponents((current) => [
      ...current.slice(0, index + 1),
      copy,
      ...current.slice(index + 1)
    ]);
    setSelectedId(copy.id);
    setInspectorTab('component');
    staleResults();
  };

  const addMotor = (motor) => {
    const aftTube = [...components].reverse().find((component) => ['Body Tube', 'Transition'].includes(component.type));
    const motorComponent = {
      ...componentDefaults.Motor,
      id: makeId('motor'),
      name: motor.displayName,
      length: motor.length || componentDefaults.Motor.length,
      diameter: motor.diameter || componentDefaults.Motor.diameter,
      weight: motor.weight || componentDefaults.Motor.weight,
      motorWeight: motor.weight || componentDefaults.Motor.weight,
      motorType: motor.manufacturer,
      motorModel: motor.designation,
      motorImpulse: motor.impulse,
      motorThrust: motor.thrust,
      motorBurnTime: motor.burnTime,
      motorTotalImpulse: motor.totalImpulse,
      motorDelay: motor.delay,
      thrustCurve: motor.thrustCurve,
      attachedToComponent: aftTube?.id || null
    };
    setComponents((current) => [
      ...current.filter((component) => component.type !== 'Motor'),
      motorComponent
    ]);
    setSelectedId(motorComponent.id);
    setInspectorTab('component');
    staleResults();
  };

  const applyLaunchSite = (siteId) => {
    if (siteId === 'custom') {
      setConfig((current) => ({ ...current, launchSite: 'custom' }));
      staleResults();
      return;
    }
    const site = launchSites.find((item) => item.id === siteId);
    if (!site) return;
    setConfig((current) => ({
      ...current,
      launchSite: siteId,
      launchAltitude: Number(site.elevation.toFixed(1)),
      temperature: Number(site.temperature.toFixed(1)),
      pressure: site.pressure
    }));
    staleResults();
  };

  const buildSimulationPayload = (overrides = {}) => {
    const nextConfig = {
      ...config,
      ...overrides,
      activeSystem: {
        ...config.activeSystem,
        ...(overrides.activeSystem || {})
      },
      controller: {
        ...config.controller,
        ...(overrides.controller || {})
      },
      landingSystem: {
        ...config.landingSystem,
        ...(overrides.landingSystem || {})
      }
    };

    return {
      rocketComponents: components,
      rocketWeight: metrics.mass,
      rocketCG: metrics.cg,
      totalHeight: metrics.totalLength,
      simulationConfig: {
        ...nextConfig,
        activePneumaticEnabled: nextConfig.activeSystem.enabled,
        activeSystem: {
          ...nextConfig.activeSystem,
          enabled: nextConfig.activeSystem.enabled
        },
        landingSystem: {
          ...nextConfig.landingSystem,
          enabled: nextConfig.landingSystem.enabled
        }
      }
    };
  };

  const submitSimulation = async (payload) => {
    const response = await fetch(`${API_URL}/api/simulation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const body = await response.json();
    if (!response.ok || body.success === false) {
      throw new Error(body.message || body.error || 'Simulation failed.');
    }
    return {
      ...body,
      rocket_weight: metrics.mass,
      rocket_cg: metrics.cg,
      totalHeight: metrics.totalLength
    };
  };

  const runSimulation = async () => {
    if (!API_URL) {
      setMessage('No local API URL is configured.');
      return;
    }
    setRunState('running');
    setMessage('Running active flight and landing simulation...');
    try {
      const active = await submitSimulation(buildSimulationPayload());
      const runCase = summarizeRun({ label: `Active run ${simulationCases.length + 1}`, active });
      setResult(active);
      setComparisonResult(null);
      setSelectedCaseId(runCase.id);
      setSimulationCases((current) => [runCase, ...current].slice(0, 8));
      setInspectorTab('results');
      setRunState('complete');
      setMessage('Simulation complete.');
    } catch (error) {
      setRunState('error');
      setMessage(error.message);
    }
  };

  const runComparison = async () => {
    if (!API_URL) {
      setMessage('No local API URL is configured.');
      return;
    }
    setRunState('running');
    setMessage('Running active and passive comparison...');
    try {
      const active = await submitSimulation(buildSimulationPayload());
      const passive = await submitSimulation(buildSimulationPayload({
        activePneumaticEnabled: false,
        activeSystem: { enabled: false },
        controller: { mode: 'disabled' }
      }));
      const runCase = summarizeRun({ label: `Comparison ${simulationCases.length + 1}`, active, passive });
      setResult(active);
      setComparisonResult(passive);
      setSelectedCaseId(runCase.id);
      setSimulationCases((current) => [runCase, ...current].slice(0, 8));
      setInspectorTab('results');
      setRunState('complete');
      setMessage('Comparison complete.');
    } catch (error) {
      setRunState('error');
      setMessage(error.message);
    }
  };

  const saveDesign = () => {
    const data = { components, config, savedAt: new Date().toISOString() };
    localStorage.setItem('activeRocket.design', JSON.stringify(data));
    setMessage('Design saved in this browser.');
  };

  const loadDesign = () => {
    const raw = localStorage.getItem('activeRocket.design');
    if (!raw) {
      setMessage('No saved browser design found.');
      return;
    }
    try {
      const data = JSON.parse(raw);
      if (Array.isArray(data.components)) setComponents(data.components);
      if (data.config) setConfig({ ...defaultConfig, ...data.config });
      setSelectedId(data.components?.[0]?.id || null);
      staleResults();
      setSimulationCases([]);
      setMessage('Saved design loaded.');
    } catch (error) {
      setMessage(`Load failed: ${error.message}`);
    }
  };

  const exportDesign = () => {
    const blob = new Blob([JSON.stringify({ components, config }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'active-rocket-design.json';
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportResults = (format) => {
    if (!result?.results) return;
    let content = '';
    let type = 'application/json';
    let filename = 'active-rocket-results.json';
    if (format !== 'json') {
      type = 'text/csv';
      if (format === 'trajectory') {
        const headers = [
          'time',
          'altitude',
          'downrange_x',
          'crossrange_y',
          'velocity_z',
          'speed',
          'acceleration_z',
          'pitch_deg',
          'yaw_deg',
          'roll_deg',
          'dynamic_pressure',
          'drag_coefficient',
          'surface_deployment',
          'landing_deployment',
          'drogue_deployment',
          'main_deployment'
        ];
        content = rowsToCsv(result.results.trajectory || [], headers);
        filename = 'active-rocket-trajectory.csv';
      } else if (format === 'forces') {
        const rows = mergeRowsByTime(result.results.force_history || [], result.results.moment_history || []);
        const headers = [
          'time',
          'thrust_force',
          'drag_force',
          'weight_force',
          'net_force_x',
          'net_force_y',
          'net_force_z',
          'dynamic_pressure',
          'drag_coefficient',
          'pitch_moment',
          'yaw_moment',
          'roll_moment',
          'pitch_rate_deg_s',
          'yaw_rate_deg_s',
          'roll_rate_deg_s'
        ];
        content = rowsToCsv(rows, headers);
        filename = 'active-rocket-forces-moments.csv';
      } else if (format === 'active') {
        const rows = mergeRowsByTime(result.results.active_system?.history || [], result.results.controller?.history || []);
        const headers = [
          'time',
          'tank_pressure',
          'actuator_pressure',
          'stroke_m',
          'surface_deployment',
          'surface_angle_deg',
          'valve_command',
          'mode',
          'predicted_apogee',
          'command',
          'surface_target'
        ];
        content = rowsToCsv(rows, headers);
        filename = 'active-rocket-active-system.csv';
      } else if (format === 'recovery') {
        const headers = [
          'time',
          'phase',
          'altitude',
          'velocity_z',
          'deployed',
          'deployment',
          'drogue_deployed',
          'drogue_deployment',
          'main_deployed',
          'main_deployment'
        ];
        content = rowsToCsv(result.results.landing_system?.history || [], headers);
        filename = 'active-rocket-recovery.csv';
      }
    } else {
      content = JSON.stringify({ active: result, passive: comparisonResult }, null, 2);
    }
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      if (file.name.toLowerCase().endsWith('.json')) {
        const data = JSON.parse(await file.text());
        if (!Array.isArray(data.components)) throw new Error('JSON file does not include components.');
        setComponents(data.components);
        setConfig({ ...defaultConfig, ...(data.config || {}) });
        setSelectedId(data.components[0]?.id || null);
        staleResults();
        setSimulationCases([]);
        setMessage('Design JSON imported.');
      } else if (file.name.toLowerCase().endsWith('.ork') || file.name.toLowerCase().endsWith('.xml')) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_URL}/api/openrocket/import`, { method: 'POST', body: formData });
        const body = await response.json();
        if (!response.ok || !body.success) throw new Error(body.message || 'OpenRocket import failed.');
        const imported = (body.rocketData?.components || []).map((component) => ({
          ...component,
          id: String(component.id || makeId(component.type || 'component'))
        }));
        setComponents(imported.length ? imported : defaultComponents);
        setSelectedId(imported[0]?.id || null);
        staleResults();
        setSimulationCases([]);
        setMessage(`${body.design_name || file.name} imported.`);
      } else {
        throw new Error('Use .ork, .xml, or exported .json files.');
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      event.target.value = '';
    }
  };

  const newDesign = () => {
    setComponents(defaultComponents.map((component) => ({ ...component, id: makeId(component.type.toLowerCase().replace(/[^a-z0-9]+/g, '-')) })));
    setConfig(defaultConfig);
    staleResults();
    setSimulationCases([]);
    setInspectorTab('component');
    setMessage('Fresh active rocket design loaded.');
  };

  const selectSimulationCase = (runCase) => {
    setResult(runCase.active);
    setComparisonResult(runCase.passive);
    setSelectedCaseId(runCase.id);
    setInspectorTab('results');
    setMessage(`${runCase.label} restored.`);
  };

  const validationItems = [
    {
      label: 'Motor installed',
      ok: Boolean(metrics.motor),
      detail: metrics.motor ? metrics.motor.name : 'Add a motor'
    },
    {
      label: 'Static margin',
      ok: metrics.stability >= 1.0 && metrics.stability <= 3.5,
      detail: `${formatNumber(metrics.stability, 2)} cal`
    },
    {
      label: 'Lift off thrust',
      ok: metrics.thrustToWeight >= 3,
      detail: `${formatNumber(metrics.thrustToWeight, 2)} T/W`
    },
    {
      label: 'Guide exit',
      ok: guideAnalysis.ok,
      detail: `${formatNumber(guideAnalysis.exitVelocity, 2)} / ${formatNumber(guideAnalysis.safeVelocity, 1)} m/s`
    },
    {
      label: 'Landing enabled',
      ok: config.landingSystem.enabled,
      detail: `${formatNumber(config.landingSystem.deployAltitude, 0)} m deploy`
    },
    {
      label: 'Recovery sized',
      ok: !config.landingSystem.enabled || landingSizing.estimatedTerminalVelocity <= landingSizing.safeVelocity,
      detail: `${formatNumber(landingSizing.estimatedTerminalVelocity, 2)} / ${formatNumber(landingSizing.safeVelocity, 1)} m/s`
    },
    {
      label: 'Active control',
      ok: config.activeSystem.enabled && activeEnvelope.cdIncrement > 0.5,
      detail: `+${formatNumber(activeEnvelope.cdIncrement, 2)} Cd authority`
    }
  ];

  const inspector = {
    component: <ComponentInspector component={selectedComponent} updateComponent={updateComponent} />,
    motors: (
      <MotorBrowser
        motors={motors}
        loading={motorsLoading}
        error={motorError}
        query={motorQuery}
        setQuery={setMotorQuery}
        addMotor={addMotor}
      />
    ),
    flight: <FlightSetup config={config} setConfig={setConfigAndInvalidate} launchSites={launchSites} applyLaunchSite={applyLaunchSite} metrics={metrics} />,
    active: <ActiveSetup config={config} setConfig={setConfigAndInvalidate} syncAirbrake={syncAirbrake} />,
    landing: <LandingSetup config={config} setConfig={setConfigAndInvalidate} syncLanding={syncLanding} metrics={metrics} />,
    results: (
      <ResultsPanel
        result={result}
        comparisonResult={comparisonResult}
        simulationCases={simulationCases}
        selectedCaseId={selectedCaseId}
        onSelectCase={selectSimulationCase}
        metrics={metrics}
        exportResults={exportResults}
      />
    )
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">AR</div>
          <div>
            <h1>ActiveRocket Workbench</h1>
            <p>OpenRocket-style design, active apogee control, and landing simulation</p>
          </div>
        </div>
        <div className="top-actions">
          <span className={`api-pill ${apiStatus}`}>API {apiStatus}</span>
          <button type="button" onClick={newDesign}>New</button>
          <button type="button" onClick={() => fileInputRef.current?.click()}>Import</button>
          <button type="button" onClick={saveDesign}>Save</button>
          <button type="button" onClick={loadDesign}>Load</button>
          <button type="button" onClick={exportDesign}>Export</button>
          <button type="button" className="secondary-action" disabled={runState === 'running'} onClick={runComparison}>
            Compare active/passive
          </button>
          <button type="button" className="primary-action" disabled={runState === 'running'} onClick={runSimulation}>
            {runState === 'running' ? 'Running...' : 'Run simulation'}
          </button>
          <input ref={fileInputRef} className="hidden-input" type="file" accept=".ork,.xml,.json" onChange={handleImport} />
        </div>
      </header>

      <main className="workspace">
        <aside className="left-rail">
          <DesignTree
            components={components}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            moveComponent={moveComponent}
            duplicateComponent={duplicateComponent}
            removeComponent={removeComponent}
          />
          <ComponentPalette addComponent={addComponent} />
        </aside>

        <section className="main-workarea">
          <div className="metrics-strip">
            <div><span>Length</span><strong>{formatNumber(metrics.totalLength, 0)} mm</strong></div>
            <div><span>Mass</span><strong>{formatNumber(metrics.mass, 0)} g</strong></div>
            <div><span>CG</span><strong>{formatNumber(metrics.cg, 0)} mm</strong></div>
            <div><span>CP</span><strong>{formatNumber(metrics.cp, 0)} mm</strong></div>
            <div><span>Stability</span><strong>{formatNumber(metrics.stability, 2)} cal</strong></div>
            <div><span>T/W</span><strong>{formatNumber(metrics.thrustToWeight, 2)}</strong></div>
          </div>

          <RocketDrawing
            components={components}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            metrics={metrics}
            results={result?.results}
          />

          <div className="lower-grid">
            <ComponentTable components={components} selectedId={selectedId} setSelectedId={setSelectedId} />
            <section className="checks-panel">
              <div className="table-title">Readiness</div>
              <div className="check-list">
                {validationItems.map((item) => (
                  <div className={`check-row ${item.ok ? 'ok' : 'warn'}`} key={item.label}>
                    <span>{item.ok ? 'Pass' : 'Check'}</span>
                    <strong>{item.label}</strong>
                    <em>{item.detail}</em>
                  </div>
                ))}
              </div>
              <DesignAnalysis metrics={metrics} massBreakdown={massBreakdown} config={config} />
              <LineChart
                compact
                title="Trajectory preview"
                yUnit="m"
                series={[
                  {
                    label: 'Altitude',
                    color: '#d9514e',
                    points: (result?.results?.trajectory || []).map((row) => ({ x: row.time, y: row.altitude }))
                  }
                ]}
              />
            </section>
          </div>
        </section>

        <aside className="inspector">
          <nav className="inspector-tabs">
            {[
              ['component', 'Component'],
              ['motors', 'Motors'],
              ['flight', 'Flight'],
              ['active', 'Active'],
              ['landing', 'Landing'],
              ['results', 'Results']
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={inspectorTab === id ? 'active' : ''}
                onClick={() => setInspectorTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>
          {inspector[inspectorTab]}
        </aside>
      </main>

      <footer className="statusbar">
        <span>{message || 'Ready'}</span>
        <span>{components.length} components</span>
        <span>{metrics.motor ? `${metrics.motor.name} motor` : 'No motor selected'}</span>
      </footer>
    </div>
  );
}

const rootElement = document.getElementById('root');
const root = ReactDOM.createRoot(rootElement);
root.render(<App />);
