import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import './App.css';

const API_URL = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_SIMULATION_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:5011' : '')
).replace(/\/$/, '');

let fallbackIdCounter = 0;

const makeId = (prefix) => {
  const cryptoUuid = globalThis.crypto?.randomUUID?.();
  const cryptoId = cryptoUuid ? cryptoUuid.slice(0, 8) : null;
  const fallbackId = `${Date.now().toString(36)}-${fallbackIdCounter += 1}`;
  return `${prefix}-${cryptoId || fallbackId}`;
};

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
  'Rail Button': '#6c757d',
  'Mass Component': '#b56576',
  Parachute: '#ef476f'
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
    maxSafeVelocity: 7.5,
    maxOpeningLoadG: 15
  },
  'Rail Button': {
    type: 'Rail Button',
    name: 'Rail button pair',
    length: 12,
    diameter: 8,
    weight: 8,
    railOffset: 4
  },
  'Mass Component': {
    type: 'Mass Component',
    name: 'Payload mass',
    length: 0,
    diameter: 0,
    weight: 75,
    massRole: 'payload',
    material: 'internal'
  },
  Parachute: {
    type: 'Parachute',
    name: 'Main parachute',
    length: 0,
    diameter: 0,
    weight: 38,
    recoveryRole: 'main',
    deployEvent: 'altitude',
    deployAltitude: 120,
    dragArea: 0.24,
    dragCoefficient: 1.55,
    maxOpeningLoadG: 15,
    material: 'ripstop nylon'
  }
};

const defaultControllerCode = `ControlOutput control_function(SensorData sensor_data) {
    ControlOutput out{};
    double error = sensor_data.predicted_apogee - 180.0;
    double command = error > 0.0 ? error * 0.012 + sensor_data.velocity_z * 0.004 : 0.0;
    if (sensor_data.altitude < 35.0 && sensor_data.velocity_z > 0.0) {
        command = 0.0;
    }
    if (command > 1.0) command = 1.0;
    if (command < 0.0) command = 0.0;
    out.valve_command = command;
    out.surface_target = command;
    out.recovery_trigger = false;
    return out;
}`;

const defaultComponents = [
  { ...componentDefaults['Nose Cone'], id: 'nose-1' },
  { ...componentDefaults['Recovery Bay'], id: 'recovery-1' },
  { ...componentDefaults.Parachute, id: 'parachute-1', attachedToComponent: 'recovery-1', axialPosition: 210 },
  { ...componentDefaults['Landing System'], id: 'landing-1' },
  { ...componentDefaults['Body Tube'], id: 'tube-1', name: 'Forward airframe', length: 360, weight: 110 },
  { ...componentDefaults['Electronics Bay'], id: 'avbay-1' },
  { ...componentDefaults['Mass Component'], id: 'mass-1', name: 'Avionics battery pack', weight: 65, massRole: 'battery', axialPosition: 720, attachedToComponent: 'avbay-1' },
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
  controlCode: defaultControllerCode,
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
    locationFromNose: 0.78,
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
    maxSafeVelocity: 7.5,
    maxOpeningLoadG: 15
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

const internalMassTypes = new Set(['Mass Component', 'Parachute']);

const getStructuralLength = (components) => components
  .filter((component) => structuralTypes.has(component.type) && component.type !== 'Rail Button')
  .reduce((sum, component) => sum + Math.max(0, numberValue(component.length)), 0);

const positionalTypes = new Set(['Fins', 'Motor', 'Rail Button', 'Mass Component', 'Parachute']);
const attachmentChildTypes = new Set(['Fins', 'Motor', 'Rail Button', 'Mass Component', 'Parachute']);
const attachmentHostTypes = new Set(['Body Tube', 'Transition', 'Electronics Bay', 'Recovery Bay', 'Active Airbrake']);

const normalizeAttachmentId = (value) => (value === null || value === undefined ? '' : String(value));

const getAttachmentHosts = (components) => components.filter((component) => attachmentHostTypes.has(component.type));

const getAttachmentHost = (component, components) => {
  const attachedId = normalizeAttachmentId(component?.attachedToComponent ?? component?.attached_to_component);
  if (!attachedId) return null;
  return getAttachmentHosts(components).find((host) => String(host.id) === attachedId) || null;
};

const getDefaultAttachmentHost = (components) => [...getAttachmentHosts(components)].reverse()[0] || null;

const getAttachmentHostCenter = (host, components, fallback) => {
  const segment = layoutComponents(components).find((component) => String(component.id) === String(host?.id));
  return segment ? segment.start + segment.length / 2 : fallback;
};

const getComponentAxialPosition = (component, totalLength) => {
  const rawPosition = numberValue(
    component.axialPosition ?? component.positionFromNose ?? component.position,
    NaN
  );
  if (Number.isFinite(rawPosition)) {
    return clamp(rawPosition, 0, totalLength);
  }
  if (component.type === 'Fins') {
    return clamp(totalLength - numberValue(component.finWidth, 100), 0, totalLength);
  }
  if (component.type === 'Motor') {
    return clamp(totalLength - numberValue(component.length, 80), 0, totalLength);
  }
  if (component.type === 'Rail Button') {
    return clamp(totalLength * 0.38 + numberValue(component.railOffset, 0), 0, totalLength);
  }
  if (component.type === 'Mass Component') {
    return clamp(totalLength * 0.45, 0, totalLength);
  }
  if (component.type === 'Parachute') {
    return clamp(totalLength * 0.2, 0, totalLength);
  }
  return 0;
};

const getMaxDiameter = (components) => Math.max(
  1,
  ...components
    .filter((component) => !internalMassTypes.has(component.type))
    .map((component) => getDiameter(component))
    .filter((value) => value > 0)
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

const getSplitBoundaries = (components) => {
  const structural = layoutComponents(components);
  return structural.slice(0, -1).map((component, index) => {
    const next = structural[index + 1];
    return {
      id: `${component.id}->${next.id}`,
      afterComponentId: String(component.id),
      beforeComponentId: String(next.id),
      afterName: component.name,
      beforeName: next.name,
      positionMm: component.end
    };
  });
};

const normalizeSplitPoints = (rawSplitPoints = [], components = []) => {
  const boundaries = getSplitBoundaries(components);
  const seen = new Set();
  return (Array.isArray(rawSplitPoints) ? rawSplitPoints : []).reduce((items, point, index) => {
    const afterComponentId = String(point.afterComponentId ?? point.after_component_id ?? point.componentId ?? '');
    const boundary = boundaries.find((item) => item.afterComponentId === afterComponentId);
    if (!boundary || seen.has(boundary.afterComponentId)) return items;
    seen.add(boundary.afterComponentId);
    items.push({
      id: String(point.id || makeId('split')),
      afterComponentId: boundary.afterComponentId,
      label: point.label || point.name || `Split ${items.length + 1}`,
      color: point.color || '#d9514e',
      order: numberValue(point.order, index)
    });
    return items;
  }, []);
};

const getSplitPointViews = (splitPoints = [], components = []) => {
  const boundaries = getSplitBoundaries(components);
  return normalizeSplitPoints(splitPoints, components)
    .map((point, index) => {
      const boundary = boundaries.find((item) => item.afterComponentId === String(point.afterComponentId));
      if (!boundary) return null;
      return {
        ...point,
        ...boundary,
        label: point.label || `Split ${index + 1}`,
        position_m: boundary.positionMm / 1000,
        position_mm: boundary.positionMm
      };
    })
    .filter(Boolean);
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
      const leadingEdge = getComponentAxialPosition(component, totalLength);
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
      position = getComponentAxialPosition(component, totalLength) + numberValue(component.finWidth, 100) / 2;
    } else if (component.type === 'Motor') {
      position = getComponentAxialPosition(component, totalLength) + numberValue(component.length, 80) / 2;
    } else if (component.type === 'Rail Button') {
      position = getComponentAxialPosition(component, totalLength);
    } else if (component.type === 'Mass Component') {
      position = getComponentAxialPosition(component, totalLength);
    } else if (component.type === 'Parachute') {
      position = getComponentAxialPosition(component, totalLength);
    } else {
      const segment = structural.find((item) => item.id === component.id);
      if (segment) position = segment.start + segment.length / 2;
    }
    position = clamp(position, 0, totalLength);
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
  { key: 'payload', label: 'Payload and ballast', color: '#b56576', types: ['Mass Component'] },
  { key: 'active', label: 'Active control', color: '#f2a541', types: ['Active Airbrake'] },
  { key: 'landing', label: 'Landing', color: '#7b61ff', types: ['Landing System', 'Parachute'] }
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
  const locationFromNoseM = numberValue(active.locationFromNose, 0);
  const locationFromNoseMm = locationFromNoseM * 1000;
  const momentArmMm = locationFromNoseMm - metrics.cg;
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
    locationFromNoseM,
    locationFromNoseMm,
    momentArmMm,
    momentArmM: momentArmMm / 1000,
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

const getParachuteRole = (component) => (
  String(component.recoveryRole || component.role || 'main').toLowerCase() === 'drogue' ? 'drogue' : 'main'
);

const getRecoveryDevices = (components) => components.filter((component) => component.type === 'Parachute');

const buildLandingSystemFromRecoveryDevices = (components, currentLanding) => {
  const devices = getRecoveryDevices(components);
  if (!devices.length) return currentLanding;
  const main = devices.find((component) => getParachuteRole(component) === 'main') || devices[0];
  const drogue = devices.find((component) => getParachuteRole(component) === 'drogue');
  const next = {
    ...currentLanding,
    enabled: true,
    type: drogue ? 'drogue_main' : 'main_parachute',
    mainDeployEvent: main.deployEvent || currentLanding.mainDeployEvent || 'altitude',
    deployAltitude: numberValue(main.deployAltitude, currentLanding.deployAltitude),
    dragArea: numberValue(main.dragArea, currentLanding.dragArea),
    dragCoefficient: numberValue(main.dragCoefficient, currentLanding.dragCoefficient),
    maxOpeningLoadG: numberValue(main.maxOpeningLoadG, currentLanding.maxOpeningLoadG)
  };
  if (drogue) {
    next.drogueDeployEvent = drogue.deployEvent || currentLanding.drogueDeployEvent || 'apogee';
    next.drogueDeployAltitude = numberValue(drogue.deployAltitude, currentLanding.drogueDeployAltitude ?? next.deployAltitude);
    next.drogueDragArea = numberValue(drogue.dragArea, currentLanding.drogueDragArea);
    next.drogueDragCoefficient = numberValue(drogue.dragCoefficient, currentLanding.drogueDragCoefficient);
  }
  return next;
};

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

const severityRank = {
  error: 0,
  warn: 1,
  info: 2,
  ok: 3
};

const componentTarget = (component, field) => (component ? `component.${component.id}.${field}` : null);

const getDesignChecks = ({ components, splitPoints = [], metrics, config, landingSizing, activeEnvelope, guideAnalysis }) => {
  const checks = [];
  const add = (severity, label, detail, targets) => {
    const targetList = (Array.isArray(targets) ? targets : [targets]).filter(Boolean);
    checks.push({
      id: `${severity}-${label}-${detail}`.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      severity,
      label,
      detail,
      targets: targetList
    });
  };

  const motor = metrics.motor || components.find((component) => component.type === 'Motor');
  const landingComponent = components.find((component) => component.type === 'Landing System');
  const activeComponent = components.find((component) => component.type === 'Active Airbrake');
  const active = config.activeSystem || {};
  const controller = config.controller || {};
  const landing = config.landingSystem || {};
  const ambientPressure = numberValue(config.pressure, 101325);
  const targetApogee = numberValue(controller.targetApogee, 0);
  const motorDelay = numberValue(motor?.motorDelay, 0);
  const attachmentHosts = getAttachmentHosts(components);

  if (!motor) {
    add('error', 'Motor missing', 'Add a motor before simulation.', 'component.motor');
  }
  if (splitPoints.length !== getSplitPointViews(splitPoints, components).length) {
    add('warn', 'Split marker', 'A split marker no longer sits between structural parts.', 'structure.splitPoints');
  }

  components.forEach((component) => {
    const mass = componentMass(component);
    if (mass <= 0) {
      add('error', 'Mass missing', `${component.name} needs a positive mass.`, componentTarget(component, 'mass'));
    }

    if (structuralTypes.has(component.type) && component.type !== 'Rail Button' && numberValue(component.length, 0) <= 0) {
      add('error', 'Length missing', `${component.name} needs a positive length.`, componentTarget(component, 'length'));
    }

    if (['Nose Cone', 'Body Tube', 'Transition', 'Electronics Bay', 'Recovery Bay', 'Active Airbrake', 'Landing System', 'Motor'].includes(component.type)) {
      const diameter = getDiameter(component);
      if (diameter <= 0) {
        add('error', 'Diameter missing', `${component.name} needs a positive diameter.`, componentTarget(component, 'diameter'));
      } else if (diameter < 10) {
        add('warn', 'Diameter looks small', `${component.name} may be using meters instead of millimeters.`, componentTarget(component, 'diameter'));
      }
    }

    if (positionalTypes.has(component.type)) {
      const explicitPosition = numberValue(
        component.axialPosition ?? component.positionFromNose ?? component.position,
        NaN
      );
      const axialPosition = getComponentAxialPosition(component, metrics.totalLength);
      const positionTarget = componentTarget(component, 'axialPosition');
      if (Number.isFinite(explicitPosition) && (explicitPosition < 0 || explicitPosition > metrics.totalLength)) {
        add('error', 'Component position', `${component.name} position must stay inside the rocket length.`, positionTarget);
      }
      if (component.type === 'Motor' && axialPosition + numberValue(component.length, 0) > metrics.totalLength + 0.1) {
        add('warn', 'Motor overhang', 'Motor extends past the aft end; move it forward or check length.', positionTarget);
      }
      if (component.type === 'Fins' && axialPosition + numberValue(component.finWidth, 0) > metrics.totalLength + 0.1) {
        add('warn', 'Fin position', 'Fin root chord extends past the aft end.', positionTarget);
      }
    }

    if (attachmentChildTypes.has(component.type)) {
      const attachedId = normalizeAttachmentId(component.attachedToComponent ?? component.attached_to_component);
      const host = getAttachmentHost(component, components);
      const target = componentTarget(component, 'attachedToComponent');
      if (!attachmentHosts.length) {
        add('error', 'Attachment host missing', 'Add a body tube, transition, or bay before placing subparts.', target);
      } else if (!attachedId) {
        add('warn', 'Attachment missing', `${component.name} should be attached to an airframe host.`, target);
      } else if (!host) {
        add('error', 'Attachment invalid', `${component.name} must attach to a body tube, transition, electronics bay, recovery bay, or active airbrake.`, target);
      }
    }

    if (component.type === 'Transition') {
      if (numberValue(component.topDiameter, 0) <= 0) {
        add('error', 'Transition front diameter', 'Top diameter must be positive.', componentTarget(component, 'topDiameter'));
      }
      if (numberValue(component.bottomDiameter, 0) <= 0) {
        add('error', 'Transition rear diameter', 'Bottom diameter must be positive.', componentTarget(component, 'bottomDiameter'));
      }
    }

    if (component.type === 'Fins') {
      if (numberValue(component.finCount, 0) < 3) {
        add('warn', 'Fin count', 'Use at least three fins for a practical baseline.', componentTarget(component, 'finCount'));
      }
      if (numberValue(component.finWidth, 0) <= 0) {
        add('error', 'Fin root chord', 'Root chord must be positive.', componentTarget(component, 'finWidth'));
      }
      if (numberValue(component.finHeight, 0) <= 0) {
        add('error', 'Fin span', 'Fin span must be positive.', componentTarget(component, 'finHeight'));
      }
      if (numberValue(component.finThickness, 0) <= 0) {
        add('warn', 'Fin thickness', 'Add fin thickness for mass and drag realism.', componentTarget(component, 'finThickness'));
      }
    }

    if (component.type === 'Parachute') {
      const deployEvent = component.deployEvent || (getParachuteRole(component) === 'drogue' ? 'apogee' : 'altitude');
      if (!['apogee', 'altitude', 'motor_ejection'].includes(deployEvent)) {
        add('error', 'Recovery event', 'Deploy event must be apogee, altitude, or motor ejection.', componentTarget(component, 'deployEvent'));
      }
      if (deployEvent === 'altitude' && numberValue(component.deployAltitude, 0) <= 0) {
        add('error', 'Deploy altitude', 'Parachute deploy altitude must be positive.', componentTarget(component, 'deployAltitude'));
      }
      if (deployEvent === 'motor_ejection' && motorDelay <= 0) {
        add('warn', 'Parachute motor ejection', 'Set a positive motor delay for motor ejection.', [
          componentTarget(component, 'deployEvent'),
          componentTarget(motor, 'motorDelay')
        ]);
      }
      if (numberValue(component.dragArea, 0) <= 0) {
        add('error', 'Parachute area', 'Parachute drag area must be positive.', componentTarget(component, 'dragArea'));
      }
      if (numberValue(component.dragCoefficient, 0) <= 0) {
        add('error', 'Parachute Cd', 'Parachute drag coefficient must be positive.', componentTarget(component, 'dragCoefficient'));
      }
      if (numberValue(component.maxOpeningLoadG, 0) <= 0) {
        add('error', 'Opening load', 'Parachute opening-load limit must be positive.', componentTarget(component, 'maxOpeningLoadG'));
      }
    }

    if (component.type === 'Motor') {
      const thrust = numberValue(component.motorThrust, 0);
      const impulse = numberValue(component.motorTotalImpulse, 0);
      const rawCurve = component.thrustCurve;
      const normalizedCurve = normalizeThrustCurvePoints(rawCurve || []);
      if (numberValue(component.motorBurnTime, 0) <= 0) {
        add('error', 'Motor burn time', 'Burn time must be positive.', componentTarget(component, 'motorBurnTime'));
      }
      if (thrust <= 0 && impulse <= 0) {
        add('error', 'Motor power', 'Average thrust or total impulse must be positive.', [
          componentTarget(component, 'motorThrust'),
          componentTarget(component, 'motorTotalImpulse')
        ]);
      }
      if (numberValue(component.motorDelay, 0) < 0) {
        add('error', 'Motor delay', 'Delay must not be negative.', componentTarget(component, 'motorDelay'));
      }
      if (Array.isArray(rawCurve) && rawCurve.length > 0) {
        if (normalizedCurve.length < 2) {
          add('error', 'Thrust curve', 'Curve needs at least two valid time/thrust points.', componentTarget(component, 'thrustCurve'));
        } else {
          const curveImpulse = integrateThrustCurve(normalizedCurve);
          if (curveImpulse <= 0) {
            add('error', 'Thrust curve impulse', 'Curve area must be positive.', componentTarget(component, 'thrustCurve'));
          } else if (impulse > 0 && Math.abs(curveImpulse - impulse) / Math.max(impulse, 1) > 0.15) {
            add('info', 'Curve changed impulse', `Curve integrates to ${formatNumber(curveImpulse, 1)} Ns.`, componentTarget(component, 'thrustCurve'));
          }
        }
      }
    }
  });

  if (metrics.mass <= 0) {
    add('error', 'Flight mass', 'Flight mass must be positive.', 'flight.mass');
  }
  if (metrics.cg <= 0 || metrics.cg > metrics.totalLength) {
    add('warn', 'Flight CG', 'CG should sit inside the rocket length.', 'flight.cg');
  }
  if (metrics.totalLength <= 0) {
    add('error', 'Flight length', 'Flight length must be positive.', 'flight.totalLength');
  }
  if (metrics.stability < 1) {
    add('warn', 'Static margin low', `${formatNumber(metrics.stability, 2)} cal; move CG forward or CP aft.`, 'flight.cg');
  } else if (metrics.stability > 3.5) {
    add('info', 'Static margin high', `${formatNumber(metrics.stability, 2)} cal; expect weathercocking sensitivity.`, 'flight.cg');
  }
  if (metrics.thrustToWeight < 3) {
    add('error', 'Lift-off thrust low', `${formatNumber(metrics.thrustToWeight, 2)} T/W; choose a stronger motor.`, componentTarget(motor, 'motorThrust'));
  } else if (metrics.thrustToWeight < 5) {
    add('warn', 'Lift-off thrust modest', `${formatNumber(metrics.thrustToWeight, 2)} T/W leaves little wind margin.`, componentTarget(motor, 'motorThrust'));
  }

  if (numberValue(config.pressure, 0) <= 0) {
    add('error', 'Ambient pressure', 'Pressure must be positive.', 'flight.pressure');
  }
  if (numberValue(config.launchGuideLength, 0) <= 0) {
    add('error', 'Guide length', 'Launch guide length must be positive.', 'flight.launchGuideLength');
  }
  if (numberValue(config.launchGuideAngle, 0) < 0 || numberValue(config.launchGuideAngle, 0) > 30) {
    add('error', 'Guide angle', 'Keep guide angle between 0 and 30 degrees.', 'flight.launchGuideAngle');
  }
  if (numberValue(config.minRailExitVelocity, 0) <= 0) {
    add('error', 'Minimum guide speed', 'Minimum guide speed must be positive.', 'flight.minRailExitVelocity');
  } else if (!guideAnalysis.ok) {
    add('warn', 'Guide exit slow', `${formatNumber(guideAnalysis.exitVelocity, 2)} m/s is below the configured limit.`, 'flight.launchGuideLength');
  }
  if (numberValue(config.timeStep, 0) <= 0) {
    add('error', 'Time step', 'Time step must be positive.', 'flight.timeStep');
  } else if (numberValue(config.timeStep, 0) > 0.1) {
    add('warn', 'Time step large', 'The solver clamps time steps above 0.1 s.', 'flight.timeStep');
  }
  if (numberValue(config.maxTime, 0) <= 0) {
    add('error', 'Max time', 'Max time must be positive.', 'flight.maxTime');
  }
  if (controller.mode === 'target_apogee' && targetApogee <= 0) {
    add('error', 'Target apogee', 'Target apogee must be positive.', 'controller.targetApogee');
  }

  if (!active.enabled) {
    add('warn', 'Active control off', 'Enable active control for this active rocket workflow.', 'active.enabled');
  } else {
    if (numberValue(active.tankPressure, 0) <= ambientPressure) {
      add('error', 'Tank pressure', 'Tank pressure must be above ambient pressure.', 'active.tankPressure');
    } else if (numberValue(active.tankPressure, 0) < numberValue(active.minOperatingPressure, 0)) {
      add('warn', 'Tank pressure low', 'Tank starts below minimum operating pressure.', 'active.tankPressure');
    }
    if (numberValue(active.tankVolume, 0) <= 0) {
      add('error', 'Tank volume', 'Tank volume must be positive.', 'active.tankVolume');
    }
    if (numberValue(active.regulatorPressure, 0) <= ambientPressure) {
      add('error', 'Regulator pressure', 'Regulator pressure must be above ambient pressure.', 'active.regulatorPressure');
    }
    if (numberValue(active.valveFlowRate, 0) <= 0) {
      add('error', 'Valve flow', 'Valve flow must be positive.', 'active.valveFlowRate');
    }
    if (numberValue(active.cylinderBore, 0) <= 0) {
      add('error', 'Cylinder bore', 'Cylinder bore must be positive.', 'active.cylinderBore');
    }
    if (numberValue(active.cylinderStroke, 0) <= 0) {
      add('error', 'Cylinder stroke', 'Cylinder stroke must be positive.', 'active.cylinderStroke');
    }
    if (numberValue(active.surfaceCount, 0) < 1) {
      add('error', 'Surface count', 'At least one active surface is required.', [
        'active.surfaceCount',
        componentTarget(activeComponent, 'surfaceCount')
      ]);
    }
    if (numberValue(active.surfaceArea, 0) <= 0) {
      add('error', 'Surface area', 'Active surface area must be positive.', [
        'active.surfaceArea',
        componentTarget(activeComponent, 'surfaceArea')
      ]);
    } else if (activeEnvelope.cdIncrement < 0.5) {
      add('warn', 'Airbrake authority', `Only +${formatNumber(activeEnvelope.cdIncrement, 2)} Cd; increase area or count.`, [
        'active.surfaceArea',
        componentTarget(activeComponent, 'surfaceArea')
      ]);
    }
    if (numberValue(active.surfaceMaxAngle, 0) <= 0) {
      add('error', 'Surface angle', 'Max angle must be positive.', [
        'active.surfaceMaxAngle',
        componentTarget(activeComponent, 'surfaceMaxAngle')
      ]);
    }
    if (activeEnvelope.locationFromNoseM < 0 || activeEnvelope.locationFromNoseMm > metrics.totalLength) {
      add('error', 'Airbrake station', 'Airbrake force station must stay inside the rocket length.', 'active.locationFromNose');
    } else if (Math.abs(activeEnvelope.momentArmMm) < metrics.maxDiameter * 0.5) {
      add('info', 'Airbrake moment arm', 'Airbrake station is close to CG; pitch/yaw authority will be limited.', 'active.locationFromNose');
    }
  }

  if (!landing.enabled) {
    add('warn', 'Landing disabled', 'Enable recovery to model touchdown.', 'landing.enabled');
  } else {
    const mainDeployEvent = landing.mainDeployEvent || landing.deployEvent || 'altitude';
    const drogueDeployEvent = landing.drogueDeployEvent || 'apogee';
    const deployAltitude = numberValue(landing.deployAltitude, 0);
    const drogueDeployAltitude = numberValue(landing.drogueDeployAltitude ?? landing.deployAltitude, 0);

    if (mainDeployEvent === 'altitude') {
      if (deployAltitude <= 0) {
        add('error', 'Deploy altitude', 'Deploy altitude must be positive.', [
          'landing.deployAltitude',
          componentTarget(landingComponent, 'deployAltitude')
        ]);
      } else if (targetApogee > 0 && deployAltitude >= targetApogee) {
        add('warn', 'Deploy altitude high', 'Main deployment is at or above target apogee.', [
          'landing.deployAltitude',
          componentTarget(landingComponent, 'deployAltitude')
        ]);
      }
    }
    if (mainDeployEvent === 'motor_ejection' && motorDelay <= 0) {
      add('warn', 'Main motor ejection', 'Set a positive motor delay for motor ejection.', [
        'landing.mainDeployEvent',
        componentTarget(motor, 'motorDelay')
      ]);
    }
    if (numberValue(landing.dragArea, 0) <= 0) {
      add('error', 'Landing drag area', 'Landing drag area must be positive.', [
        'landing.dragArea',
        componentTarget(landingComponent, 'dragArea')
      ]);
    } else if (landingSizing.estimatedTerminalVelocity > landingSizing.safeVelocity) {
      add('warn', 'Recovery undersized', `${formatNumber(landingSizing.estimatedTerminalVelocity, 2)} m/s exceeds safe touchdown.`, [
        'landing.dragArea',
        componentTarget(landingComponent, 'dragArea')
      ]);
    }
    if (numberValue(landing.dragCoefficient, 0) <= 0) {
      add('error', 'Landing drag coefficient', 'Drag coefficient must be positive.', [
        'landing.dragCoefficient',
        componentTarget(landingComponent, 'dragCoefficient')
      ]);
    }
    if (numberValue(landing.maxSafeVelocity, 0) <= 0) {
      add('error', 'Safe touchdown', 'Safe touchdown speed must be positive.', [
        'landing.maxSafeVelocity',
        componentTarget(landingComponent, 'maxSafeVelocity')
      ]);
    }
    if (numberValue(landing.maxOpeningLoadG, 0) <= 0) {
      add('error', 'Opening load', 'Maximum opening load must be positive.', [
        'landing.maxOpeningLoadG',
        componentTarget(landingComponent, 'maxOpeningLoadG')
      ]);
    }
    if (landing.type === 'drogue_main') {
      if (drogueDeployEvent === 'altitude' && drogueDeployAltitude <= 0) {
        add('error', 'Drogue altitude', 'Drogue altitude must be positive.', 'landing.drogueDeployAltitude');
      }
      if (drogueDeployEvent === 'motor_ejection' && motorDelay <= 0) {
        add('warn', 'Drogue motor ejection', 'Set a positive motor delay for drogue ejection.', [
          'landing.drogueDeployEvent',
          componentTarget(motor, 'motorDelay')
        ]);
      }
      if (numberValue(landing.drogueDragArea, 0) <= 0) {
        add('error', 'Drogue area', 'Drogue drag area must be positive.', [
          'landing.drogueDragArea',
          componentTarget(landingComponent, 'drogueDragArea')
        ]);
      }
      if (numberValue(landing.drogueDragCoefficient, 0) <= 0) {
        add('error', 'Drogue Cd', 'Drogue drag coefficient must be positive.', [
          'landing.drogueDragCoefficient',
          componentTarget(landingComponent, 'drogueDragCoefficient')
        ]);
      }
    }
  }

  return checks.sort((left, right) => (
    severityRank[left.severity] - severityRank[right.severity] ||
    left.label.localeCompare(right.label)
  ));
};

const getFieldCheckMap = (checks) => checks.reduce((map, check) => {
  check.targets.forEach((target) => {
    map[target] = [...(map[target] || []), check];
  });
  return map;
}, {});

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

const normalizeThrustCurvePoints = (rawCurve = []) => {
  if (!Array.isArray(rawCurve)) return [];
  const points = rawCurve.map((point) => (
    Array.isArray(point)
      ? { time: numberValue(point[0], NaN), thrust: numberValue(point[1], NaN) }
      : { time: numberValue(point.time ?? point.time_s ?? point.t, NaN), thrust: numberValue(point.thrust ?? point.thrust_n ?? point.force, NaN) }
  )).filter((point) => (
    Number.isFinite(point.time) &&
    Number.isFinite(point.thrust) &&
    point.time >= 0 &&
    point.thrust >= 0
  )).sort((left, right) => left.time - right.time);

  return points.reduce((deduped, point) => {
    const cleanPoint = {
      time: Number(point.time.toFixed(4)),
      thrust: Number(point.thrust.toFixed(4))
    };
    if (deduped.length && Math.abs(deduped[deduped.length - 1].time - cleanPoint.time) < 1e-9) {
      deduped[deduped.length - 1] = cleanPoint;
    } else {
      deduped.push(cleanPoint);
    }
    return deduped;
  }, []);
};

const integrateThrustCurve = (points) => points.slice(1).reduce((sum, point, index) => {
  const previous = points[index];
  return sum + Math.max(point.time - previous.time, 0) * (point.thrust + previous.thrust) * 0.5;
}, 0);

const interpolateThrustCurve = (points, time) => {
  if (!points.length || time < points[0].time || time > points[points.length - 1].time) return 0;
  for (let index = 0; index < points.length - 1; index += 1) {
    const left = points[index];
    const right = points[index + 1];
    if (left.time <= time && time <= right.time) {
      const span = right.time - left.time;
      if (span <= 1e-9) return right.thrust;
      const fraction = (time - left.time) / span;
      return left.thrust + (right.thrust - left.thrust) * fraction;
    }
  }
  return 0;
};

const sampleThrustCurve = (points, count = 12) => {
  const curve = normalizeThrustCurvePoints(points);
  if (curve.length <= count) return curve;
  const burnTime = curve[curve.length - 1].time;
  if (burnTime <= 0) return curve.slice(0, count);
  return Array.from({ length: count }, (_, index) => {
    const time = (burnTime * index) / (count - 1);
    return {
      time: Number(time.toFixed(3)),
      thrust: Number(interpolateThrustCurve(curve, time).toFixed(2))
    };
  });
};

const buildAverageThrustCurve = (motor) => {
  const burnTime = Math.max(numberValue(motor.motorBurnTime, 0), 0.1);
  const totalImpulse = Math.max(
    numberValue(motor.motorTotalImpulse, 0),
    numberValue(motor.motorThrust, 0) * burnTime
  );
  const plateau = totalImpulse > 0 ? totalImpulse / (burnTime * 0.9) : numberValue(motor.motorThrust, 0);
  return normalizeThrustCurvePoints([
    { time: 0, thrust: 0 },
    { time: burnTime * 0.1, thrust: plateau },
    { time: burnTime * 0.9, thrust: plateau },
    { time: burnTime, thrust: 0 }
  ]);
};

const getMotorCurveSummary = (motor) => {
  const curve = normalizeThrustCurvePoints(motor.thrustCurve || []);
  const hasCurve = curve.length >= 2 && curve[curve.length - 1].time > curve[0].time;
  const burnTime = hasCurve ? curve[curve.length - 1].time : numberValue(motor.motorBurnTime, 0);
  const totalImpulse = hasCurve ? integrateThrustCurve(curve) : numberValue(motor.motorTotalImpulse, 0);
  const averageThrust = burnTime > 0 ? totalImpulse / burnTime : numberValue(motor.motorThrust, 0);
  const peakThrust = hasCurve
    ? Math.max(...curve.map((point) => point.thrust))
    : Math.max(numberValue(motor.motorThrust, 0), averageThrust);
  return {
    curve,
    hasCurve,
    burnTime,
    totalImpulse,
    averageThrust,
    peakThrust
  };
};

const motorPatchFromCurve = (curve) => {
  const summary = getMotorCurveSummary({ thrustCurve: curve });
  if (!summary.hasCurve) return { thrustCurve: [] };
  return {
    thrustCurve: summary.curve,
    motorBurnTime: Number(summary.burnTime.toFixed(3)),
    motorTotalImpulse: Number(summary.totalImpulse.toFixed(3)),
    motorThrust: Number(summary.averageThrust.toFixed(3))
  };
};

const mergeConfig = (base, incoming = {}) => ({
  ...base,
  ...incoming,
  activeSystem: {
    ...base.activeSystem,
    ...(incoming.activeSystem || {})
  },
  controller: {
    ...base.controller,
    ...(incoming.controller || {})
  },
  landingSystem: {
    ...base.landingSystem,
    ...(incoming.landingSystem || incoming.recoverySystem || {})
  },
  aerodynamics: {
    ...base.aerodynamics,
    ...(incoming.aerodynamics || {})
  },
  noise: {
    ...base.noise,
    ...(incoming.noise || {})
  }
});

const normalizeRocketOverrides = (rocketData = {}, data = {}) => {
  const weight = numberValue(rocketData.weight ?? data.rocketWeight, 0);
  const cg = numberValue(rocketData.cg ?? data.rocketCG, 0);
  const totalHeight = numberValue(rocketData.totalHeight ?? data.totalHeight, 0);
  return {
    ...(weight > 0 ? { weight } : {}),
    ...(cg > 0 ? { cg } : {}),
    ...(totalHeight > 0 ? { totalHeight } : {})
  };
};

const clonePlain = (value, fallback = {}) => {
  try {
    return JSON.parse(JSON.stringify(value ?? fallback));
  } catch {
    return fallback;
  }
};

const createSimulationSetup = (label, config, rocketOverrides = {}) => ({
  id: makeId('setup'),
  label,
  createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  updatedAt: new Date().toISOString(),
  config: mergeConfig(defaultConfig, clonePlain(config, defaultConfig)),
  rocketOverrides: clonePlain(rocketOverrides, {})
});

const createInitialSimulationSetups = (baseConfig = defaultConfig, rocketOverrides = {}) => {
  const passiveConfig = mergeConfig(baseConfig, {
    activePneumaticEnabled: false,
    activeSystem: { enabled: false },
    controller: { mode: 'disabled' }
  });
  const descentConfig = mergeConfig(baseConfig, {
    controller: {
      mode: 'descent_brake',
      targetApogee: 300,
      descentDeployAltitude: 70
    },
    landingSystem: {
      type: 'drogue_main',
      drogueDeployEvent: 'apogee',
      mainDeployEvent: 'altitude'
    }
  });

  return [
    createSimulationSetup('Active target apogee', baseConfig, rocketOverrides),
    createSimulationSetup('Passive baseline', passiveConfig, rocketOverrides),
    createSimulationSetup('Descent brake and landing', descentConfig, rocketOverrides)
  ];
};

const normalizeSimulationSetups = (rawSetups, fallbackConfig, fallbackOverrides = {}) => {
  if (!Array.isArray(rawSetups) || rawSetups.length === 0) {
    return createInitialSimulationSetups(fallbackConfig, fallbackOverrides);
  }

  return rawSetups.map((setup, index) => ({
    id: String(setup.id || makeId('setup')),
    label: setup.label || setup.name || `Simulation setup ${index + 1}`,
    createdAt: setup.createdAt || 'Imported',
    updatedAt: setup.updatedAt || new Date().toISOString(),
    config: mergeConfig(defaultConfig, setup.config || setup.simulationConfig || fallbackConfig),
    rocketOverrides: clonePlain(setup.rocketOverrides || fallbackOverrides, {})
  }));
};

const normalizeImportedComponents = (rawComponents) => rawComponents.map((component) => ({
  ...component,
  id: String(component.id || makeId(component.type || 'component'))
}));

const normalizeImportedDesign = (data) => {
  const rocketData = data.rocketData || data.rocket || {};
  const rawComponents = data.components || rocketData.components || data.rocketComponents;
  if (!Array.isArray(rawComponents) || !rawComponents.length) {
    throw new Error('JSON file does not include rocket components.');
  }

  const incomingConfig = data.config || data.simulationConfig || {};
  const config = mergeConfig(defaultConfig, incomingConfig);
  const rocketOverrides = data.rocketOverrides || normalizeRocketOverrides(rocketData, data);
  const components = normalizeImportedComponents(rawComponents);
  const splitPoints = normalizeSplitPoints(
    data.splitPoints || rocketData.splitPoints || data.stageSplits || rocketData.stageSplits,
    components
  );
  return {
    id: data.id || data.name || 'imported-design',
    description: data.description || '',
    components,
    splitPoints,
    config,
    rocketOverrides,
    simulationSetups: normalizeSimulationSetups(data.simulationSetups || data.simulations, config, rocketOverrides)
  };
};

const applyRocketOverrides = (metrics, overrides = {}) => {
  const mass = numberValue(overrides.weight, metrics.mass) > 0
    ? numberValue(overrides.weight, metrics.mass)
    : metrics.mass;
  const cg = numberValue(overrides.cg, metrics.cg) > 0
    ? numberValue(overrides.cg, metrics.cg)
    : metrics.cg;
  const totalLength = numberValue(overrides.totalHeight, metrics.totalLength) > 0
    ? numberValue(overrides.totalHeight, metrics.totalLength)
    : metrics.totalLength;
  const thrust = numberValue(metrics.motor?.motorThrust, 0);
  return {
    ...metrics,
    mass,
    cg,
    totalLength,
    stability: metrics.maxDiameter > 0 ? (metrics.cp - cg) / metrics.maxDiameter : metrics.stability,
    thrustToWeight: mass > 0 ? thrust / ((mass / 1000) * 9.80665) : 0,
    overridesApplied: Boolean(overrides.weight || overrides.cg || overrides.totalHeight)
  };
};

function Field({ label, value, unit, type = 'number', step = 'any', min, max, onChange, options, checks = [] }) {
  const reactId = useId().replace(/:/g, '');
  const id = `${label.replace(/[^a-z0-9]+/gi, '-')}-${reactId}`;
  const messages = Array.isArray(checks) ? checks : [checks].filter(Boolean);
  const severity = messages.reduce((current, check) => (
    severityRank[check.severity] < severityRank[current] ? check.severity : current
  ), 'ok');
  return (
    <label className={`field ${messages.length ? `has-${severity}` : ''}`} htmlFor={id}>
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
            aria-invalid={severity === 'error'}
            onChange={(event) => onChange(type === 'number' ? numberValue(event.target.value) : event.target.value)}
          />
        )}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {messages.length > 0 && (
        <div className="field-messages">
          {messages.slice(0, 2).map((check) => (
            <span className={`field-message ${check.severity}`} key={check.id}>{check.detail}</span>
          ))}
        </div>
      )}
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

function LandingFootprintMap({ footprint = {} }) {
  const readPoint = (key) => {
    const x = footprint[`${key}_x_m`];
    const y = footprint[`${key}_y_m`];
    if (x === null || x === undefined || y === null || y === undefined) return null;
    const parsedX = Number(x);
    const parsedY = Number(y);
    if (!Number.isFinite(parsedX) || !Number.isFinite(parsedY)) return null;
    return { x: parsedX, y: parsedY };
  };
  const points = [
    { key: 'launch', label: 'Launch', color: '#343a40', ...readPoint('launch') },
    { key: 'apogee', label: 'Apogee', color: '#4d908e', ...readPoint('apogee') },
    { key: 'drogue', label: 'Drogue', color: '#f2a541', ...readPoint('drogue_deploy') },
    { key: 'main', label: 'Main', color: '#7b61ff', ...readPoint('main_deploy') },
    { key: 'touchdown', label: 'Touchdown', color: '#d9514e', ...readPoint('touchdown') }
  ].filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));

  if (points.length < 2) {
    return <div className="chart-empty">No landing footprint data yet</div>;
  }

  const width = 720;
  const height = 220;
  const pad = { top: 28, right: 28, bottom: 38, left: 54 };
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const xSpan = Math.max(Math.max(...xs) - Math.min(...xs), 1);
  const ySpan = Math.max(Math.max(...ys) - Math.min(...ys), 1);
  const xMin = Math.min(...xs) - xSpan * 0.1;
  const xMax = Math.max(...xs) + xSpan * 0.1;
  const yMin = Math.min(...ys) - ySpan * 0.2;
  const yMax = Math.max(...ys) + ySpan * 0.2;
  const sx = (x) => pad.left + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - pad.left - pad.right);
  const sy = (y) => pad.top + (1 - ((y - yMin) / Math.max(yMax - yMin, 1e-9))) * (height - pad.top - pad.bottom);
  const xTicks = [xMin, (xMin + xMax) / 2, xMax];
  const yTicks = [yMin, (yMin + yMax) / 2, yMax];
  const path = points.map((point) => `${sx(point.x).toFixed(2)},${sy(point.y).toFixed(2)}`).join(' ');

  return (
    <div className="footprint-map">
      <div className="footprint-legend">
        {points.map((point) => (
          <span key={point.key}><i style={{ backgroundColor: point.color }} />{point.label}</span>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="footprint-svg" role="img" aria-label="Landing footprint">
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line x1={sx(tick)} x2={sx(tick)} y1={pad.top} y2={height - pad.bottom} className="gridline" />
            <text x={sx(tick)} y={height - 13} textAnchor="middle">{formatNumber(tick, 1)} m</text>
          </g>
        ))}
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line x1={pad.left} x2={width - pad.right} y1={sy(tick)} y2={sy(tick)} className="gridline" />
            <text x={pad.left - 8} y={sy(tick) + 4} textAnchor="end">{formatNumber(tick, 1)}</text>
          </g>
        ))}
        <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} className="axis" />
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={height - pad.bottom} className="axis" />
        <text x="10" y="18">crossrange</text>
        <text x={width - pad.right} y={height - 6} textAnchor="end">downrange</text>
        <polyline className="footprint-path" points={path} />
        {points.map((point, index) => {
          const rightSide = sx(point.x) > width * 0.62;
          const yOffset = index % 2 === 0 ? -10 : 16;
          return (
            <g className={`footprint-point ${point.key}`} key={point.key}>
              <circle cx={sx(point.x)} cy={sy(point.y)} r={5} style={{ fill: point.color }} />
              <text
                x={sx(point.x) + (rightSide ? -8 : 8)}
                y={sy(point.y) + yOffset}
                textAnchor={rightSide ? 'end' : 'start'}
              >
                {point.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function RecoveryAnalysisPanel({ analysis = {} }) {
  const sequence = analysis.deployment_sequence || [];
  const phases = analysis.phases || [];
  if (!sequence.length && !phases.length) {
    return null;
  }

  return (
    <div className="recovery-panel">
      <div className="comparison-title">Recovery analysis</div>
      {sequence.length > 0 && (
        <div className="recovery-table recovery-sequence">
          <div className="recovery-row recovery-head">
            <span>Event</span>
            <span>Time</span>
            <span>Altitude</span>
            <span>V vertical</span>
            <span>Range</span>
          </div>
          {sequence.map((event) => (
            <div className="recovery-row" key={`${event.name}-${event.time_s}`}>
              <strong>{event.name}</strong>
              <span>{formatNumber(event.time_s, 2)} s</span>
              <span>{formatNumber(event.altitude_m, 1)} m</span>
              <span>{formatNumber(event.velocity_z_mps, 2)} m/s</span>
              <span>{formatNumber(event.range_m, 1)} m</span>
            </div>
          ))}
        </div>
      )}
      {phases.length > 0 && (
        <div className="recovery-table recovery-phases">
          <div className="recovery-row recovery-head">
            <span>Phase</span>
            <span>Duration</span>
            <span>Alt loss</span>
            <span>Avg descent</span>
            <span>Drift</span>
          </div>
          {phases.map((phase) => (
            <div className="recovery-row" key={phase.name}>
              <strong>{phase.name}</strong>
              <span>{formatNumber(phase.duration_s, 2)} s</span>
              <span>{formatNumber(phase.altitude_loss_m, 1)} m</span>
              <span>{formatNumber(phase.average_descent_rate_mps, 2)} m/s</span>
              <span>{formatNumber(phase.drift_m, 1)} m</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function statusLabel(status) {
  if (!status) return 'n/a';
  return String(status).replace(/_/g, ' ');
}

function RecoverySafetyPanel({ safety = {} }) {
  if (!safety.enabled) {
    return null;
  }
  const rows = [
    ['Overall', statusLabel(safety.overall_status)],
    ['Main terminal', `${formatNumber(safety.main_terminal_velocity_mps, 2)} m/s`],
    ['Required main area', `${formatNumber(safety.required_main_drag_area_m2, 3)} m2`],
    ['Main area margin', `${safety.main_area_margin_m2 >= 0 ? '+' : ''}${formatNumber(safety.main_area_margin_m2, 3)} m2`],
    ['Main opening', `${formatNumber(safety.main_opening_load_g, 2)} g`],
    ['Opening limit', `${formatNumber(safety.max_opening_load_g, 1)} g`],
    ['Drogue terminal', safety.drogue_terminal_velocity_mps === null || safety.drogue_terminal_velocity_mps === undefined ? '--' : `${formatNumber(safety.drogue_terminal_velocity_mps, 2)} m/s`],
    ['Drogue opening', safety.drogue_opening_load_g === null || safety.drogue_opening_load_g === undefined ? '--' : `${formatNumber(safety.drogue_opening_load_g, 2)} g`]
  ];

  return (
    <div className={`safety-panel ${safety.overall_status || ''}`}>
      <div className="comparison-title">Recovery safety</div>
      <div className="comparison-grid safety-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function RocketDrawing({ components, splitPoints, selectedId, setSelectedId, metrics, results }) {
  const structural = layoutComponents(components);
  const splitViews = getSplitPointViews(splitPoints, components);
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
              const finStart = getComponentAxialPosition(finSet, length);
              const rootChord = numberValue(finSet.finWidth, 100);
              const baseX = xFor(finStart);
              const tailX = xFor(clamp(finStart + rootChord, 0, length));
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
            {(() => {
              const motorStart = getComponentAxialPosition(motor, length);
              const motorLength = Math.max(6, Math.min(numberValue(motor.length, 85), length - motorStart));
              return (
                <>
                  <rect
                    x={xFor(motorStart)}
                    y={centerY - heightFor(numberValue(motor.diameter, 29)) / 2}
                    width={motorLength * pxPerMm}
                    height={heightFor(numberValue(motor.diameter, 29))}
                    rx="4"
                    className={`motor-core ${selectedId === motor.id ? 'selected' : ''}`}
                  />
                  <path
                    d={`M ${xFor(motorStart + motorLength)} ${centerY - 14} L ${xFor(motorStart + motorLength) + 30} ${centerY} L ${xFor(motorStart + motorLength)} ${centerY + 14} Z`}
                    className="motor-nozzle"
                  />
                </>
              );
            })()}
            <title>{motor.name}</title>
          </g>
        )}
        {components.filter((component) => component.type === 'Rail Button').map((button) => {
          const x = xFor(getComponentAxialPosition(button, length));
          const selected = selectedId === button.id;
          return (
            <g key={button.id} onClick={() => setSelectedId(button.id)}>
              <circle cx={x} cy={centerY - heightFor(maxDiameter) / 2 - 12} r="6" className={`rail-button-dot ${selected ? 'selected' : ''}`} />
              <circle cx={x + 22} cy={centerY - heightFor(maxDiameter) / 2 - 12} r="6" className={`rail-button-dot ${selected ? 'selected' : ''}`} />
              <title>{button.name}</title>
            </g>
          );
        })}
        {components.filter((component) => component.type === 'Mass Component').map((massComponent, index) => {
          const x = xFor(getComponentAxialPosition(massComponent, length));
          const selected = selectedId === massComponent.id;
          const yOffset = index % 2 === 0 ? -18 : 18;
          return (
            <g key={massComponent.id} onClick={() => setSelectedId(massComponent.id)}>
              <path
                className={`mass-marker ${selected ? 'selected' : ''}`}
                d={`M ${x} ${centerY + yOffset - 9} L ${x + 9} ${centerY + yOffset} L ${x} ${centerY + yOffset + 9} L ${x - 9} ${centerY + yOffset} Z`}
              />
              <line x1={x} x2={x} y1={centerY + yOffset} y2={centerY} className="mass-marker-line" />
              <title>{massComponent.name}</title>
            </g>
          );
        })}
        {components.filter((component) => component.type === 'Parachute').map((parachute, index) => {
          const x = xFor(getComponentAxialPosition(parachute, length));
          const selected = selectedId === parachute.id;
          const canopyY = centerY - heightFor(maxDiameter) / 2 - 44 - (index % 2) * 16;
          return (
            <g key={parachute.id} onClick={() => setSelectedId(parachute.id)}>
              <path
                className={`parachute-marker ${selected ? 'selected' : ''}`}
                d={`M ${x - 18} ${canopyY + 12} Q ${x} ${canopyY - 14} ${x + 18} ${canopyY + 12} Z`}
              />
              <line x1={x - 12} x2={x} y1={canopyY + 12} y2={centerY} className="parachute-shroud" />
              <line x1={x + 12} x2={x} y1={canopyY + 12} y2={centerY} className="parachute-shroud" />
              <title>{parachute.name}</title>
            </g>
          );
        })}
        {splitViews.map((split, index) => {
          const splitX = xFor(split.positionMm);
          const labelOffset = index % 2 === 0 ? 0 : 18;
          return (
            <g className="split-marker" key={split.id}>
              <line x1={splitX} x2={splitX} y1="42" y2="238" className="split-line" />
              <text x={splitX + 7} y={48 + labelOffset} className="marker-label">
                {split.label} {formatNumber(split.positionMm, 0)} mm
              </text>
            </g>
          );
        })}
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

const isTreeAirframeComponent = (component) => (
  structuralTypes.has(component.type) && !['Landing System', 'Rail Button'].includes(component.type)
);

const getTreeAttachmentGroups = (components) => {
  const childrenByHost = new Map();
  const unattached = [];
  components.forEach((component) => {
    if (!attachmentChildTypes.has(component.type)) return;
    const host = getAttachmentHost(component, components);
    if (!host) {
      unattached.push(component);
      return;
    }
    const key = String(host.id);
    if (!childrenByHost.has(key)) childrenByHost.set(key, []);
    childrenByHost.get(key).push(component);
  });
  return { childrenByHost, unattached };
};

function DesignTree({
  components,
  splitPoints,
  selectedId,
  setSelectedId,
  moveComponent,
  duplicateComponent,
  removeComponent,
  addSplitPoint,
  removeSplitPoint
}) {
  const airframeComponents = components.filter(isTreeAirframeComponent);
  const landingComponents = components.filter((component) => component.type === 'Landing System');
  const { childrenByHost, unattached } = getTreeAttachmentGroups(components);
  const splitViews = getSplitPointViews(splitPoints, components);
  const boundaries = getSplitBoundaries(components);
  const splitByAfter = new Map(splitViews.map((point) => [point.afterComponentId, point]));
  const boundaryByAfter = new Map(boundaries.map((boundary) => [boundary.afterComponentId, boundary]));
  const renderTreeItem = (component, { child = false, orphan = false, meta = component.type } = {}) => (
    <div
      key={component.id}
      className={`tree-item ${child ? 'child' : ''} ${orphan ? 'orphan' : ''} ${selectedId === component.id ? 'active' : ''}`}
      onClick={() => setSelectedId(component.id)}
    >
      <span className="part-swatch" style={{ backgroundColor: componentColor[component.type] || '#999' }} />
      <span className="tree-name">
        <strong>{component.name}</strong>
        <em>{meta}</em>
      </span>
      <button type="button" onClick={(event) => { event.stopPropagation(); moveComponent(component.id, -1); }}>Up</button>
      <button type="button" onClick={(event) => { event.stopPropagation(); moveComponent(component.id, 1); }}>Down</button>
      <button type="button" onClick={(event) => { event.stopPropagation(); duplicateComponent(component.id); }}>Copy</button>
      <button type="button" onClick={(event) => { event.stopPropagation(); removeComponent(component.id); }}>Remove</button>
    </div>
  );

  return (
    <section className="left-section">
      <div className="section-title">Design tree</div>
      <div className="tree-root">
        <div className="tree-vehicle">ActiveRocket</div>
        <div className="tree-group">
          <div className="tree-group-label">Airframe hierarchy</div>
          {airframeComponents.map((component) => {
            const children = childrenByHost.get(String(component.id)) || [];
            return (
              <React.Fragment key={component.id}>
                {renderTreeItem(component)}
                {children.length > 0 && (
                  <div className="tree-children">
                    {children.map((childComponent) => renderTreeItem(childComponent, { child: true }))}
                  </div>
                )}
                {boundaryByAfter.has(String(component.id)) && (
                  splitByAfter.has(String(component.id)) ? (
                    <div className="tree-split-marker">
                      <span className="split-swatch" />
                      <strong>{splitByAfter.get(String(component.id)).label}</strong>
                      <em>{formatNumber(splitByAfter.get(String(component.id)).positionMm, 0)} mm</em>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          removeSplitPoint(splitByAfter.get(String(component.id)).id);
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="tree-add-split"
                      onClick={(event) => {
                        event.stopPropagation();
                        addSplitPoint(component.id);
                      }}
                    >
                      Add split between {component.name} and {boundaryByAfter.get(String(component.id)).beforeName}
                    </button>
                  )
                )}
              </React.Fragment>
            );
          })}
        </div>
        {unattached.length > 0 && (
          <div className="tree-group">
            <div className="tree-group-label">Unattached subparts</div>
            {unattached.map((component) => renderTreeItem(component, { child: true, orphan: true, meta: `${component.type} - choose host` }))}
          </div>
        )}
        {landingComponents.length > 0 && (
          <div className="tree-group">
            <div className="tree-group-label">Recovery configuration</div>
            {landingComponents.map((component) => renderTreeItem(component, { meta: 'Landing system settings' }))}
          </div>
        )}
      </div>
    </section>
  );
}

function ComponentPalette({ addComponent }) {
  const categories = [
    ['Airframe', ['Nose Cone', 'Body Tube', 'Transition', 'Electronics Bay', 'Recovery Bay']],
    ['Payload', ['Mass Component']],
    ['Control', ['Active Airbrake', 'Fins', 'Rail Button']],
    ['Propulsion and landing', ['Motor', 'Parachute', 'Landing System']]
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

const getComponentDetailText = (component) => {
  if (component.type === 'Motor') {
    return `${formatNumber(component.motorThrust, 1)} N, ${formatNumber(component.motorTotalImpulse, 1)} Ns`;
  }
  if (component.type === 'Fins') {
    return `${component.finCount} fins, ${formatNumber(component.finHeight, 0)} mm span`;
  }
  if (component.type === 'Mass Component') {
    return component.massRole || 'payload';
  }
  if (component.type === 'Parachute') {
    return `${getParachuteRole(component)} ${formatNumber(component.dragArea, 3)} m2`;
  }
  return component.material || 'configured';
};

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
              <th>Position</th>
              <th>Host</th>
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
                <td>{internalMassTypes.has(component.type) ? '--' : `${formatNumber(component.length, 0)} mm`}</td>
                <td>{internalMassTypes.has(component.type) ? '--' : `${formatNumber(getDiameter(component), 0)} mm`}</td>
                <td>{positionalTypes.has(component.type) ? `${formatNumber(getComponentAxialPosition(component, getStructuralLength(components)), 0)} mm` : '--'}</td>
                <td>{attachmentChildTypes.has(component.type) ? getAttachmentHost(component, components)?.name || 'Unattached' : '--'}</td>
                <td>{formatNumber(componentMass(component), 0)} g</td>
                <td>{getComponentDetailText(component)}</td>
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
          <span>Airbrake station</span>
          <strong>{formatNumber(activeEnvelope.locationFromNoseMm, 0)} mm</strong>
        </div>
        <div>
          <span>Airbrake moment arm</span>
          <strong>{activeEnvelope.momentArmMm >= 0 ? '+' : ''}{formatNumber(activeEnvelope.momentArmMm, 0)} mm</strong>
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

function MotorCurvePanel({ component, updateComponent, fieldChecks = {} }) {
  const summary = getMotorCurveSummary(component);
  const displayCurve = summary.hasCurve ? summary.curve : buildAverageThrustCurve(component);
  const editableCurve = summary.curve.length <= 18;
  const checks = fieldChecks[componentTarget(component, 'thrustCurve')] || [];
  const setCurve = (nextCurve) => updateComponent(component.id, motorPatchFromCurve(nextCurve));
  const updatePoint = (index, key, value) => {
    const nextCurve = summary.curve.map((point, pointIndex) => (
      pointIndex === index ? { ...point, [key]: value } : point
    ));
    setCurve(nextCurve);
  };
  const addPoint = () => {
    const lastPoint = summary.curve[summary.curve.length - 1] || { time: 0, thrust: 0 };
    setCurve([...summary.curve, { time: Number((lastPoint.time + 0.1).toFixed(3)), thrust: 0 }]);
  };
  const removePoint = (index) => {
    setCurve(summary.curve.filter((_, pointIndex) => pointIndex !== index));
  };

  return (
    <div className="sizing-card motor-curve-panel">
      <div className="comparison-title">Motor thrust curve</div>
      <div className="sizing-grid">
        <div><span>Curve source</span><strong>{summary.hasCurve ? `${summary.curve.length} points` : 'Average fields'}</strong></div>
        <div><span>Peak thrust</span><strong>{formatNumber(summary.peakThrust, 1)} N</strong></div>
        <div><span>Burn time</span><strong>{formatNumber(summary.burnTime, 2)} s</strong></div>
        <div><span>Integrated impulse</span><strong>{formatNumber(summary.totalImpulse, 1)} Ns</strong></div>
      </div>
      <LineChart
        compact
        title="Motor thrust"
        yUnit="N"
        series={[
          {
            label: summary.hasCurve ? 'Curve' : 'Generated',
            color: '#343a40',
            points: displayCurve.map((point) => ({ x: point.time, y: point.thrust }))
          }
        ]}
      />
      {checks.length > 0 && (
        <div className="field-messages curve-messages">
          {checks.slice(0, 2).map((check) => (
            <span className={`field-message ${check.severity}`} key={check.id}>{check.detail}</span>
          ))}
        </div>
      )}
      {summary.hasCurve && !editableCurve && (
        <div className="curve-note">
          Loaded curve has {summary.curve.length} points. Simplify it to edit sampled points by hand.
        </div>
      )}
      {editableCurve && summary.hasCurve && (
        <div className="curve-point-table">
          <div className="curve-point-head">
            <span>Time</span>
            <span>Thrust</span>
            <span />
          </div>
          {summary.curve.map((point, index) => (
            <div className="curve-point-row" key={`${point.time}-${index}`}>
              <input
                aria-label={`Curve point ${index + 1} time`}
                type="number"
                step="0.01"
                min="0"
                value={point.time}
                onChange={(event) => updatePoint(index, 'time', numberValue(event.target.value))}
              />
              <input
                aria-label={`Curve point ${index + 1} thrust`}
                type="number"
                step="0.1"
                min="0"
                value={point.thrust}
                onChange={(event) => updatePoint(index, 'thrust', numberValue(event.target.value))}
              />
              <button type="button" onClick={() => removePoint(index)} disabled={summary.curve.length <= 2}>Remove</button>
            </div>
          ))}
        </div>
      )}
      <div className="sizing-actions curve-actions">
        <button type="button" onClick={() => setCurve(buildAverageThrustCurve(component))}>
          Build avg curve
        </button>
        <button type="button" onClick={() => setCurve(sampleThrustCurve(displayCurve, 12))}>
          Simplify to edit
        </button>
        <button type="button" onClick={addPoint}>
          Add point
        </button>
        <button type="button" onClick={() => updateComponent(component.id, { thrustCurve: [] })}>
          Clear curve
        </button>
      </div>
    </div>
  );
}

function ComponentInspector({ component, components = [], updateComponent, metrics, fieldChecks = {} }) {
  if (!component) {
    return (
      <div className="empty-state">
        Select a component in the tree or drawing.
      </div>
    );
  }

  const set = (key, value) => updateComponent(component.id, { [key]: value });
  const checks = (field) => fieldChecks[componentTarget(component, field)] || [];
  const axialPosition = component
    ? getComponentAxialPosition(component, metrics?.totalLength || numberValue(component.axialPosition, 0))
    : 0;
  const attachmentHosts = getAttachmentHosts(components);
  const parachuteDeployEvent = component.type === 'Parachute'
    ? component.deployEvent || (getParachuteRole(component) === 'drogue' ? 'apogee' : 'altitude')
    : 'altitude';
  const commonFields = (
    <>
      <Field label="Name" type="text" value={component.name} onChange={(value) => set('name', value)} />
      {!internalMassTypes.has(component.type) && (
        <>
          <Field label="Length" value={component.length} unit="mm" checks={checks('length')} onChange={(value) => set('length', value)} />
          <Field label="Diameter" value={component.diameter} unit="mm" checks={checks('diameter')} onChange={(value) => set('diameter', value)} />
        </>
      )}
      <Field label="Mass" value={componentMass(component)} unit="g" checks={checks('mass')} onChange={(value) => set(component.type === 'Motor' ? 'motorWeight' : 'weight', value)} />
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
        {positionalTypes.has(component.type) && (
          <Field
            label="Axial position"
            value={component.axialPosition ?? axialPosition}
            unit="mm"
            checks={checks('axialPosition')}
            onChange={(value) => set('axialPosition', value)}
          />
        )}
        {attachmentChildTypes.has(component.type) && (
          <Field
            label="Attached to"
            value={normalizeAttachmentId(component.attachedToComponent ?? component.attached_to_component)}
            checks={checks('attachedToComponent')}
            onChange={(value) => set('attachedToComponent', value || null)}
            options={[
              { value: '', label: 'Unattached' },
              ...attachmentHosts.map((host) => ({
                value: String(host.id),
                label: `${host.name} (${host.type})`
              }))
            ]}
          />
        )}
        {component.type === 'Transition' && (
          <>
            <Field label="Top diameter" value={component.topDiameter} unit="mm" checks={checks('topDiameter')} onChange={(value) => set('topDiameter', value)} />
            <Field label="Bottom diameter" value={component.bottomDiameter} unit="mm" checks={checks('bottomDiameter')} onChange={(value) => set('bottomDiameter', value)} />
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
            <Field label="Fin count" value={component.finCount} checks={checks('finCount')} onChange={(value) => set('finCount', value)} />
            <Field label="Root chord" value={component.finWidth} unit="mm" checks={checks('finWidth')} onChange={(value) => set('finWidth', value)} />
            <Field label="Span" value={component.finHeight} unit="mm" checks={checks('finHeight')} onChange={(value) => set('finHeight', value)} />
            <Field label="Sweep" value={component.finSweep} unit="mm" onChange={(value) => set('finSweep', value)} />
            <Field label="Thickness" value={component.finThickness} unit="mm" checks={checks('finThickness')} onChange={(value) => set('finThickness', value)} />
          </>
        )}
        {component.type === 'Mass Component' && (
          <Field
            label="Mass role"
            value={component.massRole || 'payload'}
            onChange={(value) => set('massRole', value)}
            options={[
              { value: 'payload', label: 'Payload' },
              { value: 'battery', label: 'Battery' },
              { value: 'avionics', label: 'Avionics' },
              { value: 'ballast', label: 'Ballast' },
              { value: 'recovery', label: 'Recovery hardware' }
            ]}
          />
        )}
        {component.type === 'Parachute' && (
          <>
            <Field
              label="Recovery role"
              value={component.recoveryRole || 'main'}
              onChange={(value) => set('recoveryRole', value)}
              options={[
                { value: 'main', label: 'Main' },
                { value: 'drogue', label: 'Drogue' }
              ]}
            />
            <Field
              label="Deploy event"
              value={parachuteDeployEvent}
              onChange={(value) => set('deployEvent', value)}
              options={recoveryDeployEvents}
            />
            {parachuteDeployEvent === 'altitude' && (
              <Field label="Deploy altitude" value={component.deployAltitude} unit="m" checks={checks('deployAltitude')} onChange={(value) => set('deployAltitude', value)} />
            )}
            <Field label="Drag area" value={component.dragArea} unit="m2" step="0.005" checks={checks('dragArea')} onChange={(value) => set('dragArea', value)} />
            <Field label="Drag coefficient" value={component.dragCoefficient} step="0.01" checks={checks('dragCoefficient')} onChange={(value) => set('dragCoefficient', value)} />
            <Field label="Max opening load" value={component.maxOpeningLoadG ?? 15} unit="g" step="0.5" checks={checks('maxOpeningLoadG')} onChange={(value) => set('maxOpeningLoadG', value)} />
          </>
        )}
        {component.type === 'Active Airbrake' && (
          <>
            <Field label="Surface count" value={component.surfaceCount} checks={checks('surfaceCount')} onChange={(value) => set('surfaceCount', value)} />
            <Field label="Surface area" value={component.surfaceArea} unit="m2" step="0.0001" checks={checks('surfaceArea')} onChange={(value) => set('surfaceArea', value)} />
            <Field label="Max angle" value={component.surfaceMaxAngle} unit="deg" checks={checks('surfaceMaxAngle')} onChange={(value) => set('surfaceMaxAngle', value)} />
          </>
        )}
        {component.type === 'Motor' && (
          <>
            <Field label="Manufacturer" type="text" value={component.motorType || ''} onChange={(value) => set('motorType', value)} />
            <Field label="Designation" type="text" value={component.motorModel || ''} onChange={(value) => set('motorModel', value)} />
            <Field label="Avg thrust" value={component.motorThrust} unit="N" checks={checks('motorThrust')} onChange={(value) => set('motorThrust', value)} />
            <Field label="Burn time" value={component.motorBurnTime} unit="s" checks={checks('motorBurnTime')} onChange={(value) => set('motorBurnTime', value)} />
            <Field label="Total impulse" value={component.motorTotalImpulse} unit="Ns" checks={checks('motorTotalImpulse')} onChange={(value) => set('motorTotalImpulse', value)} />
            <Field label="Delay" value={component.motorDelay} unit="s" checks={checks('motorDelay')} onChange={(value) => set('motorDelay', value)} />
          </>
        )}
        {component.type === 'Landing System' && (
          <>
            <Field label="Deploy altitude" value={component.deployAltitude} unit="m" checks={checks('deployAltitude')} onChange={(value) => set('deployAltitude', value)} />
            <Field label="Drag area" value={component.dragArea} unit="m2" step="0.01" checks={checks('dragArea')} onChange={(value) => set('dragArea', value)} />
            <Field label="Drag coefficient" value={component.dragCoefficient} step="0.01" checks={checks('dragCoefficient')} onChange={(value) => set('dragCoefficient', value)} />
            <Field label="Drogue area" value={component.drogueDragArea ?? 0.04} unit="m2" step="0.005" checks={checks('drogueDragArea')} onChange={(value) => set('drogueDragArea', value)} />
            <Field label="Drogue Cd" value={component.drogueDragCoefficient ?? 1.25} step="0.01" checks={checks('drogueDragCoefficient')} onChange={(value) => set('drogueDragCoefficient', value)} />
            <Field label="Safe touchdown" value={component.maxSafeVelocity} unit="m/s" step="0.1" checks={checks('maxSafeVelocity')} onChange={(value) => set('maxSafeVelocity', value)} />
            <Field label="Max opening load" value={component.maxOpeningLoadG ?? 15} unit="g" step="0.5" checks={checks('maxOpeningLoadG')} onChange={(value) => set('maxOpeningLoadG', value)} />
          </>
        )}
      </div>
      {component.type === 'Motor' && (
        <MotorCurvePanel component={component} updateComponent={updateComponent} fieldChecks={fieldChecks} />
      )}
    </div>
  );
}

function MotorBrowser({
  motors,
  loading,
  error,
  query,
  setQuery,
  filters,
  setFilters,
  metadata,
  addMotor
}) {
  const manufacturerOptions = metadata?.manufacturers?.length
    ? metadata.manufacturers
    : Array.from(new Set(motors.map((motor) => motor.manufacturer))).sort();
  const impulseOptions = metadata?.impulse_classes?.length
    ? metadata.impulse_classes
    : Array.from(new Set(motors.map((motor) => motor.impulse).filter(Boolean))).sort();
  const diameterOptions = metadata?.diameters_mm?.length
    ? metadata.diameters_mm
    : Array.from(new Set(motors.map((motor) => motor.diameter).filter(Boolean))).sort((a, b) => a - b);
  const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    const diameter = numberValue(filters.diameter, 0);
    return motors.filter((motor) => {
      if (text && !motor.model.toLowerCase().includes(text)) return false;
      if (filters.manufacturer && motor.manufacturer !== filters.manufacturer) return false;
      if (filters.impulseClass && motor.impulse !== filters.impulseClass) return false;
      if (filters.diameter && Math.abs(motor.diameter - diameter) > 0.05) return false;
      if (filters.tarcOnly && !motor.approvedForTarc) return false;
      return true;
    }).slice(0, 48);
  }, [motors, query, filters]);
  const activeFilterCount = [
    query.trim(),
    filters.manufacturer,
    filters.impulseClass,
    filters.diameter,
    filters.tarcOnly ? 'tarc' : ''
  ].filter(Boolean).length;

  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Motor database</h2>
        <p>Installed motor curves for the current rocket.</p>
      </div>
      <div className="motor-browser-head">
        <strong>{filtered.length} matches</strong>
        <span>{motors.length} catalog motors</span>
      </div>
      <div className="motor-filter-grid">
        <Field label="Designation" type="text" value={query} onChange={setQuery} />
        <Field
          label="Impulse"
          value={filters.impulseClass}
          onChange={(value) => setFilter('impulseClass', value)}
          options={[
            { value: '', label: 'All classes' },
            ...impulseOptions.map((item) => ({ value: item, label: item }))
          ]}
        />
        <Field
          label="Manufacturer"
          value={filters.manufacturer}
          onChange={(value) => setFilter('manufacturer', value)}
          options={[
            { value: '', label: 'All makers' },
            ...manufacturerOptions.map((item) => ({ value: item, label: item }))
          ]}
        />
        <Field
          label="Diameter"
          value={filters.diameter}
          unit="mm"
          onChange={(value) => setFilter('diameter', value)}
          options={[
            { value: '', label: 'All' },
            ...diameterOptions.map((item) => ({ value: String(item), label: formatNumber(item, 0) }))
          ]}
        />
      </div>
      <div className="motor-filter-actions">
        <Toggle
          checked={filters.tarcOnly}
          onChange={(value) => setFilter('tarcOnly', value)}
          label="TARC approved"
        />
        <button
          type="button"
          onClick={() => {
            setQuery('');
            setFilters({ manufacturer: '', impulseClass: '', diameter: '', tarcOnly: false });
          }}
          disabled={!activeFilterCount}
        >
          Clear filters
        </button>
      </div>
      {loading && <div className="inline-status">Loading motors...</div>}
      {error && <div className="inline-status error">{error}</div>}
      <div className="motor-list">
        {filtered.map((motor) => (
          <button key={motor.id} type="button" className="motor-row" onClick={() => addMotor(motor)}>
            <strong>{motor.displayName}</strong>
            <span>{motor.manufacturer}</span>
            <span>{motor.impulse} class</span>
            <span>{formatNumber(motor.totalImpulse, 1)} Ns</span>
            <span>{formatNumber(motor.thrust, 1)} N avg</span>
            <span>{formatNumber(motor.length, 0)} x {formatNumber(motor.diameter, 0)} mm</span>
          </button>
        ))}
        {!loading && !filtered.length && (
          <div className="inline-status">No motors match those filters.</div>
        )}
      </div>
    </div>
  );
}

function FlightSetup({
  config,
  setConfig,
  launchSites,
  applyLaunchSite,
  metrics,
  componentMetrics,
  setRocketOverrides,
  fieldChecks = {}
}) {
  const set = (key, value) => setConfig((current) => ({ ...current, [key]: value }));
  const guide = getLaunchGuideAnalysis(metrics, config);
  const checks = (target) => fieldChecks[target] || [];
  const setOverride = (key, value) => setRocketOverrides((current) => ({
    ...current,
    [key]: value
  }));
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
        <Field label="Pressure" value={config.pressure} unit="Pa" checks={checks('flight.pressure')} onChange={(value) => set('pressure', value)} />
        <Field label="Wind speed" value={config.windSpeed} unit="m/s" step="0.1" onChange={(value) => set('windSpeed', value)} />
        <Field label="Wind direction" value={config.windDirection} unit="deg" onChange={(value) => set('windDirection', value)} />
        <Field label="Guide length" value={config.launchGuideLength} unit="m" step="0.1" checks={checks('flight.launchGuideLength')} onChange={(value) => set('launchGuideLength', value)} />
        <Field label="Guide angle" value={config.launchGuideAngle} unit="deg" step="0.5" checks={checks('flight.launchGuideAngle')} onChange={(value) => set('launchGuideAngle', value)} />
        <Field label="Guide direction" value={config.launchGuideDirection} unit="deg" onChange={(value) => set('launchGuideDirection', value)} />
        <Field label="Min guide speed" value={config.minRailExitVelocity} unit="m/s" step="0.5" checks={checks('flight.minRailExitVelocity')} onChange={(value) => set('minRailExitVelocity', value)} />
        <Field label="Time step" value={config.timeStep} unit="s" step="0.005" checks={checks('flight.timeStep')} onChange={(value) => set('timeStep', value)} />
        <Field label="Max time" value={config.maxTime} unit="s" checks={checks('flight.maxTime')} onChange={(value) => set('maxTime', value)} />
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
          checks={checks('controller.targetApogee')}
          onChange={(value) => setConfig((current) => ({ ...current, controller: { ...current.controller, targetApogee: value } }))}
        />
      </div>
      <div className="sizing-card">
        <div className="comparison-title">Flight mass properties</div>
        <div className="field-grid single mass-property-fields">
          <Field label="Flight mass" value={metrics.mass} unit="g" checks={checks('flight.mass')} onChange={(value) => setOverride('weight', value)} />
          <Field label="Flight CG" value={metrics.cg} unit="mm" checks={checks('flight.cg')} onChange={(value) => setOverride('cg', value)} />
          <Field label="Flight length" value={metrics.totalLength} unit="mm" checks={checks('flight.totalLength')} onChange={(value) => setOverride('totalHeight', value)} />
        </div>
        <div className="sizing-grid">
          <div><span>Component mass</span><strong>{formatNumber(componentMetrics.mass, 0)} g</strong></div>
          <div><span>Component CG</span><strong>{formatNumber(componentMetrics.cg, 0)} mm</strong></div>
          <div><span>Override</span><strong>{metrics.overridesApplied ? 'Active' : 'Off'}</strong></div>
          <div><span>Static margin</span><strong>{formatNumber(metrics.stability, 2)} cal</strong></div>
        </div>
        <div className="sizing-actions mass-property-actions">
          <button type="button" onClick={() => setRocketOverrides({})}>
            Use component totals
          </button>
        </div>
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

function ActiveSetup({
  config,
  setConfig,
  syncAirbrake,
  compileController,
  controllerCompileState,
  metrics,
  activeComponentStation,
  fieldChecks = {}
}) {
  const active = config.activeSystem;
  const controller = config.controller;
  const controllerLanguage = config.controllerLanguage || 'builtin';
  const checks = (target) => fieldChecks[target] || [];
  const activeEnvelope = getActiveEnvelope(metrics, config);
  const setActive = (key, value) => setConfig((current) => ({
    ...current,
    activePneumaticEnabled: key === 'enabled' ? value : current.activePneumaticEnabled,
    activeSystem: { ...current.activeSystem, [key]: value }
  }));
  const setRoot = (key, value) => setConfig((current) => ({
    ...current,
    [key]: value
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
      {checks('active.enabled').length > 0 && (
        <div className="toggle-message">{checks('active.enabled')[0].detail}</div>
      )}
      <div className="field-grid single">
        <Field label="Tank pressure" value={active.tankPressure} unit="Pa" checks={checks('active.tankPressure')} onChange={(value) => setActive('tankPressure', value)} />
        <Field label="Tank volume" value={active.tankVolume} unit="L" step="0.01" checks={checks('active.tankVolume')} onChange={(value) => setActive('tankVolume', value)} />
        <Field label="Regulator pressure" value={active.regulatorPressure} unit="Pa" checks={checks('active.regulatorPressure')} onChange={(value) => setActive('regulatorPressure', value)} />
        <Field label="Valve flow" value={active.valveFlowRate} step="0.1" checks={checks('active.valveFlowRate')} onChange={(value) => setActive('valveFlowRate', value)} />
        <Field label="Cylinder bore" value={active.cylinderBore} unit="m" step="0.001" checks={checks('active.cylinderBore')} onChange={(value) => setActive('cylinderBore', value)} />
        <Field label="Cylinder stroke" value={active.cylinderStroke} unit="m" step="0.001" checks={checks('active.cylinderStroke')} onChange={(value) => setActive('cylinderStroke', value)} />
        <Field label="Airbrake station" value={active.locationFromNose} unit="m" step="0.01" checks={checks('active.locationFromNose')} onChange={(value) => setActive('locationFromNose', value)} />
        <Field
          label="Controller source"
          value={controllerLanguage}
          onChange={(value) => setRoot('controllerLanguage', value)}
          options={[
            { value: 'builtin', label: 'Built-in controller' },
            { value: 'cpp', label: 'C++ controller' }
          ]}
        />
        <Field label="Surface count" value={active.surfaceCount} checks={checks('active.surfaceCount')} onChange={(value) => { setActive('surfaceCount', value); syncAirbrake('surfaceCount', value); }} />
        <Field label="Surface area" value={active.surfaceArea} unit="m2" step="0.0001" checks={checks('active.surfaceArea')} onChange={(value) => { setActive('surfaceArea', value); syncAirbrake('surfaceArea', value); }} />
        <Field label="Max angle" value={active.surfaceMaxAngle} unit="deg" checks={checks('active.surfaceMaxAngle')} onChange={(value) => { setActive('surfaceMaxAngle', value); syncAirbrake('surfaceMaxAngle', value); }} />
        <Field label="Deploy altitude" value={controller.deployAltitude} unit="m" checks={checks('controller.deployAltitude')} onChange={(value) => setController('deployAltitude', value)} />
        <Field label="Kp" value={controller.kp} step="0.001" onChange={(value) => setController('kp', value)} />
        <Field label="Kd" value={controller.kd} step="0.001" onChange={(value) => setController('kd', value)} />
      </div>
      <div className="sizing-card">
        <div className="comparison-title">Airbrake placement</div>
        <div className="sizing-grid">
          <div><span>Force station</span><strong>{formatNumber(activeEnvelope.locationFromNoseMm, 0)} mm</strong></div>
          <div><span>Moment arm</span><strong>{activeEnvelope.momentArmMm >= 0 ? '+' : ''}{formatNumber(activeEnvelope.momentArmMm, 0)} mm</strong></div>
          <div><span>Component center</span><strong>{activeComponentStation === null ? '--' : `${formatNumber(activeComponentStation, 0)} mm`}</strong></div>
          <div><span>CG reference</span><strong>{formatNumber(metrics.cg, 0)} mm</strong></div>
        </div>
        <div className="sizing-actions">
          <button
            type="button"
            onClick={() => setActive('locationFromNose', Number((activeComponentStation / 1000).toFixed(3)))}
            disabled={activeComponentStation === null}
          >
            Use component center
          </button>
          <button type="button" onClick={() => setActive('locationFromNose', Number((metrics.cg / 1000).toFixed(3)))}>
            Set at CG
          </button>
        </div>
      </div>
      {controllerLanguage === 'cpp' && (
        <div className="code-panel">
          <div className="comparison-title">Controller code</div>
          <textarea
            className="code-editor"
            value={config.controlCode || defaultControllerCode}
            spellCheck="false"
            onChange={(event) => setRoot('controlCode', event.target.value)}
          />
          <div className="controller-actions">
            <button type="button" onClick={compileController} disabled={controllerCompileState.status === 'running'}>
              {controllerCompileState.status === 'running' ? 'Compiling...' : 'Compile check'}
            </button>
            <span className={`compile-pill ${controllerCompileState.status}`}>
              {controllerCompileState.message || 'Not checked'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function LandingSetup({ config, setConfig, syncLanding, metrics, fieldChecks = {} }) {
  const landing = config.landingSystem;
  const mainDeployEvent = landing.mainDeployEvent || landing.deployEvent || 'altitude';
  const drogueDeployEvent = landing.drogueDeployEvent || 'apogee';
  const sizing = getLandingSizing(metrics, config);
  const drogueSizing = getLandingSizing(metrics, config, {
    dragArea: landing.drogueDragArea,
    dragCoefficient: landing.drogueDragCoefficient,
    maxSafeVelocity: 25
  });
  const checks = (target) => fieldChecks[target] || [];
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
      {checks('landing.enabled').length > 0 && (
        <div className="toggle-message">{checks('landing.enabled')[0].detail}</div>
      )}
      <div className="field-grid single">
        <Field
          label="System type"
          value={landing.type}
          checks={checks('landing.type')}
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
              checks={checks('landing.drogueDeployEvent')}
              onChange={(value) => setLanding('drogueDeployEvent', value)}
              options={recoveryDeployEvents}
            />
            {drogueDeployEvent === 'altitude' && (
              <Field
                label="Drogue altitude"
                value={landing.drogueDeployAltitude ?? landing.deployAltitude}
                unit="m"
                checks={checks('landing.drogueDeployAltitude')}
                onChange={(value) => setLanding('drogueDeployAltitude', value)}
              />
            )}
          </>
        )}
        <Field
          label={landing.type === 'drogue_main' ? 'Main event' : 'Deploy event'}
          value={mainDeployEvent}
          checks={checks('landing.mainDeployEvent')}
          onChange={(value) => setLanding('mainDeployEvent', value)}
          options={recoveryDeployEvents}
        />
        {mainDeployEvent === 'altitude' && (
          <Field label={landing.type === 'drogue_main' ? 'Main altitude' : 'Deploy altitude'} value={landing.deployAltitude} unit="m" checks={checks('landing.deployAltitude')} onChange={(value) => setLanding('deployAltitude', value)} />
        )}
        <Field label={landing.type === 'drogue_main' ? 'Main area' : 'Drag area'} value={landing.dragArea} unit="m2" step="0.01" checks={checks('landing.dragArea')} onChange={(value) => setLanding('dragArea', value)} />
        <Field label={landing.type === 'drogue_main' ? 'Main Cd' : 'Drag coefficient'} value={landing.dragCoefficient} step="0.01" checks={checks('landing.dragCoefficient')} onChange={(value) => setLanding('dragCoefficient', value)} />
        {landing.type === 'drogue_main' && (
          <>
            <Field label="Drogue area" value={landing.drogueDragArea} unit="m2" step="0.005" checks={checks('landing.drogueDragArea')} onChange={(value) => setLanding('drogueDragArea', value)} />
            <Field label="Drogue Cd" value={landing.drogueDragCoefficient} step="0.01" checks={checks('landing.drogueDragCoefficient')} onChange={(value) => setLanding('drogueDragCoefficient', value)} />
          </>
        )}
        <Field label="Safe touchdown" value={landing.maxSafeVelocity} unit="m/s" step="0.1" checks={checks('landing.maxSafeVelocity')} onChange={(value) => setLanding('maxSafeVelocity', value)} />
        <Field label="Max opening load" value={landing.maxOpeningLoadG ?? 15} unit="g" step="0.5" checks={checks('landing.maxOpeningLoadG')} onChange={(value) => setLanding('maxOpeningLoadG', value)} />
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

function SimulationSetupPanel({
  simulationSetups,
  selectedSetupId,
  setSelectedSetupId,
  runState,
  onCreateSetup,
  onUpdateSetup,
  onDuplicateSetup,
  onDeleteSetup,
  onRestoreSetup,
  onRunSetup,
  onCompareSetup,
  onRenameSetup
}) {
  const selectedSetup = simulationSetups.find((setup) => setup.id === selectedSetupId);
  const describeSetup = (setup) => {
    const activeEnabled = setup.config.activeSystem?.enabled;
    const controllerMode = setup.config.controller?.mode || 'target_apogee';
    const target = numberValue(setup.config.controller?.targetApogee, 0);
    const landing = setup.config.landingSystem || {};
    return {
      active: activeEnabled ? 'Active' : 'Passive',
      controller: controllerMode.replace(/_/g, ' '),
      target: target > 0 ? `${formatNumber(target, 0)} m` : '--',
      recovery: landing.enabled ? recoveryEventDetail(landing.mainDeployEvent || landing.deployEvent || 'altitude', landing.deployAltitude) : 'Recovery off'
    };
  };

  return (
    <div className="inspector-scroll">
      <div className="panel-copy">
        <h2>Simulation setups</h2>
        <p>Save named flight configurations and run them against the current rocket.</p>
      </div>
      <div className="setup-actions">
        <button type="button" onClick={onCreateSetup}>Save current setup</button>
        <button type="button" onClick={onUpdateSetup} disabled={!selectedSetup}>Update selected</button>
      </div>
      <div className="setup-list">
        {simulationSetups.map((setup) => {
          const summary = describeSetup(setup);
          return (
            <button
              type="button"
              className={`setup-row ${setup.id === selectedSetupId ? 'active' : ''}`}
              key={setup.id}
              onClick={() => setSelectedSetupId(setup.id)}
            >
              <strong>{setup.label}</strong>
              <span>{summary.active} / {summary.controller}</span>
              <em>Target {summary.target}; {summary.recovery}</em>
            </button>
          );
        })}
      </div>
      {selectedSetup && (
        <div className="sizing-card setup-detail">
          <div className="comparison-title">Selected setup</div>
          <div className="field-grid single setup-name-field">
            <Field
              label="Setup name"
              type="text"
              value={selectedSetup.label}
              onChange={(value) => onRenameSetup(selectedSetup.id, value)}
            />
          </div>
          <div className="sizing-grid">
            {Object.entries(describeSetup(selectedSetup)).map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <div className="setup-detail-actions">
            <button type="button" onClick={() => onRunSetup(selectedSetup)} disabled={runState === 'running'}>Run setup</button>
            <button type="button" onClick={() => onCompareSetup(selectedSetup)} disabled={runState === 'running'}>Compare</button>
            <button type="button" onClick={() => onRestoreSetup(selectedSetup)}>Restore</button>
            <button type="button" onClick={() => onDuplicateSetup(selectedSetup)}>Duplicate</button>
            <button type="button" onClick={() => onDeleteSetup(selectedSetup.id)} disabled={simulationSetups.length <= 1}>Delete</button>
          </div>
        </div>
      )}
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
  const footprint = data?.landing_footprint || {};
  const recoveryAnalysis = data?.recovery_analysis || {};
  const recoverySafety = data?.recovery_safety || {};
  const launchGuide = data?.launch_guide;
  const recoveryTiming = data?.recovery_timing;
  const events = data?.flight_events || [];
  const controllerLabel = data?.controller?.compiled_cpp ? 'C++' : 'Built-in';
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
    recoverySafety.enabled
      ? {
        label: 'Opening load',
        status: recoverySafety.overall_status === 'safe'
          ? 'good'
          : recoverySafety.overall_status === 'warn'
            ? 'warn'
            : 'bad',
        detail: `Main ${formatNumber(recoverySafety.main_opening_load_g, 2)} g / limit ${formatNumber(recoverySafety.max_opening_load_g, 1)} g`
      }
      : null,
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
      : null,
    {
      label: 'Controller',
      status: data.controller?.failures ? 'bad' : data.controller?.compiled_cpp ? 'good' : 'info',
      detail: data.controller?.compiled_cpp
        ? 'Compiled C++ controller active'
        : `${data.controller?.mode || 'builtin'} mode`
    }
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
        <div className="metric-box"><span>Controller</span><strong>{controllerLabel}</strong></div>
        <div className="metric-box"><span>Stability</span><strong>{formatNumber(metrics.stability, 2)} cal</strong></div>
        <div className="metric-box"><span>Airbrake station</span><strong>{formatNumber((data.active_system?.location_from_nose_m || 0) * 1000, 0)} mm</strong></div>
        <div className="metric-box"><span>Airbrake arm</span><strong>{formatNumber((data.active_system?.moment_arm_m || 0) * 1000, 0)} mm</strong></div>
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
      <div className="footprint-panel">
        <div className="comparison-title">Landing footprint</div>
        <div className="comparison-grid footprint-stats">
          <div><span>Touchdown range</span><strong>{formatNumber(footprint.touchdown_range_m, 1)} m</strong></div>
          <div><span>Bearing</span><strong>{formatNumber(footprint.touchdown_bearing_deg, 1)} deg</strong></div>
          <div><span>Crossrange</span><strong>{formatNumber(footprint.touchdown_y_m, 1)} m</strong></div>
          <div><span>Main drift</span><strong>{formatNumber(footprint.drift_after_main_deploy_m, 1)} m</strong></div>
          <div><span>Drogue drift</span><strong>{formatNumber(footprint.drift_after_drogue_deploy_m, 1)} m</strong></div>
          <div><span>Descent time</span><strong>{formatNumber(footprint.descent_time_s, 2)} s</strong></div>
        </div>
        <LandingFootprintMap footprint={footprint} />
      </div>
      <RecoveryAnalysisPanel analysis={recoveryAnalysis} />
      <RecoverySafetyPanel safety={recoverySafety} />
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
          { label: 'Active pitch', color: '#f2a541', points: momentHistory.map((row) => ({ x: row.time, y: row.active_pitch_moment })) },
          { label: 'Roll', color: '#343a40', points: momentHistory.map((row) => ({ x: row.time, y: row.roll_moment })) }
        ]}
      />
      <div className="result-actions">
        <button type="button" onClick={() => exportResults('json')}>Export JSON</button>
        <button type="button" onClick={() => exportResults('trajectory')}>Trajectory CSV</button>
        <button type="button" onClick={() => exportResults('forces')}>Force/moment CSV</button>
        <button type="button" onClick={() => exportResults('active')}>Active CSV</button>
        <button type="button" onClick={() => exportResults('recovery')}>Recovery CSV</button>
        <button type="button" onClick={() => exportResults('recovery-summary')}>Recovery summary CSV</button>
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
  const [motorFilters, setMotorFilters] = useState({ manufacturer: '', impulseClass: '', diameter: '', tarcOnly: false });
  const [motorMetadata, setMotorMetadata] = useState({ manufacturers: [], impulse_classes: [], diameters_mm: [] });
  const [motorsLoading, setMotorsLoading] = useState(false);
  const [motorError, setMotorError] = useState('');
  const [launchSites, setLaunchSites] = useState([]);
  const [apiStatus, setApiStatus] = useState('checking');
  const [runState, setRunState] = useState('idle');
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [splitPoints, setSplitPoints] = useState([]);
  const [simulationCases, setSimulationCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [simulationSetups, setSimulationSetups] = useState(() => createInitialSimulationSetups(defaultConfig, {}));
  const [selectedSetupId, setSelectedSetupId] = useState(null);
  const [rocketOverrides, setRocketOverrides] = useState({});
  const [controllerCompileState, setControllerCompileState] = useState({ status: 'idle', message: '' });
  const fileInputRef = useRef(null);
  const componentMetrics = useMemo(() => getMetrics(components), [components]);
  const metrics = useMemo(() => applyRocketOverrides(componentMetrics, rocketOverrides), [componentMetrics, rocketOverrides]);
  const massBreakdown = useMemo(() => getMassBreakdown(components), [components]);
  const activeComponentStation = useMemo(() => {
    const activeComponent = components.find((component) => component.type === 'Active Airbrake');
    if (!activeComponent) return null;
    const segment = layoutComponents(components).find((component) => component.id === activeComponent.id);
    return segment ? segment.start + segment.length / 2 : null;
  }, [components]);
  const landingSizing = useMemo(() => getLandingSizing(metrics, config), [metrics, config]);
  const activeEnvelope = useMemo(() => getActiveEnvelope(metrics, config), [metrics, config]);
  const guideAnalysis = useMemo(() => getLaunchGuideAnalysis(metrics, config), [metrics, config]);
  const splitPointViews = useMemo(() => getSplitPointViews(splitPoints, components), [splitPoints, components]);
  const designChecks = useMemo(() => getDesignChecks({
    components,
    splitPoints,
    metrics,
    config,
    landingSizing,
    activeEnvelope,
    guideAnalysis
  }), [components, splitPoints, metrics, config, landingSizing, activeEnvelope, guideAnalysis]);
  const fieldChecks = useMemo(() => getFieldCheckMap(designChecks), [designChecks]);
  const selectedComponent = components.find((component) => component.id === selectedId);
  const selectedSimulationSetup = simulationSetups.find((setup) => setup.id === selectedSetupId);

  const staleResults = () => {
    setResult(null);
    setComparisonResult(null);
    setSelectedCaseId(null);
  };

  const setConfigAndInvalidate = (updater) => {
    setConfig(updater);
    setControllerCompileState((current) => (
      current.status === 'success' ? { status: 'idle', message: 'Controller changed' } : current
    ));
    staleResults();
  };

  const setRocketOverridesAndInvalidate = (updater) => {
    setRocketOverrides(updater);
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
          setMotorMetadata(motorsData.filters || { manufacturers: [], impulse_classes: [], diameters_mm: [] });
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
    if (!simulationSetups.length) {
      if (selectedSetupId !== null) setSelectedSetupId(null);
      return;
    }
    if (!simulationSetups.some((setup) => setup.id === selectedSetupId)) {
      setSelectedSetupId(simulationSetups[0].id);
    }
  }, [simulationSetups, selectedSetupId]);

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
      landingSystem: buildLandingSystemFromRecoveryDevices(components, landing ? {
        ...current.landingSystem,
        mainDeployEvent: landing.mainDeployEvent || current.landingSystem.mainDeployEvent,
        drogueDeployEvent: landing.drogueDeployEvent || current.landingSystem.drogueDeployEvent,
        drogueDeployAltitude: numberValue(landing.drogueDeployAltitude, current.landingSystem.drogueDeployAltitude),
        deployAltitude: numberValue(landing.deployAltitude, current.landingSystem.deployAltitude),
        dragArea: numberValue(landing.dragArea, current.landingSystem.dragArea),
        dragCoefficient: numberValue(landing.dragCoefficient, current.landingSystem.dragCoefficient),
        drogueDragArea: numberValue(landing.drogueDragArea, current.landingSystem.drogueDragArea),
        drogueDragCoefficient: numberValue(landing.drogueDragCoefficient, current.landingSystem.drogueDragCoefficient),
        maxSafeVelocity: numberValue(landing.maxSafeVelocity, current.landingSystem.maxSafeVelocity),
        maxOpeningLoadG: numberValue(landing.maxOpeningLoadG, current.landingSystem.maxOpeningLoadG)
      } : current.landingSystem)
    }));
  }, [components]);

  useEffect(() => {
    setSplitPoints((current) => normalizeSplitPoints(current, components));
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

  const addSplitPoint = (afterComponentId) => {
    setSplitPoints((current) => normalizeSplitPoints([
      ...current,
      {
        id: makeId('split'),
        afterComponentId: String(afterComponentId),
        label: `Split ${current.length + 1}`
      }
    ], components));
    staleResults();
  };

  const removeSplitPoint = (id) => {
    setSplitPoints((current) => current.filter((point) => point.id !== id));
    staleResults();
  };

  const addComponent = (type) => {
    const next = cloneComponent(type);
    if (type === 'Parachute' && components.some((component) => component.type === 'Parachute' && getParachuteRole(component) === 'main')) {
      next.name = 'Drogue parachute';
      next.recoveryRole = 'drogue';
      next.deployEvent = 'apogee';
      next.deployAltitude = 120;
      next.dragArea = 0.04;
      next.dragCoefficient = 1.25;
      next.weight = 18;
    }
    if (attachmentChildTypes.has(type)) {
      const host = type === 'Parachute'
        ? components.find((component) => component.type === 'Recovery Bay') || getDefaultAttachmentHost(components)
        : getDefaultAttachmentHost(components);
      if (host) {
        next.attachedToComponent = host.id;
        if (type === 'Mass Component' || type === 'Parachute') {
          next.axialPosition = getAttachmentHostCenter(host, components, componentMetrics.totalLength * 0.45);
        }
      }
    }
    if (positionalTypes.has(type)) {
      next.axialPosition = getComponentAxialPosition(next, componentMetrics.totalLength);
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
    const host = getDefaultAttachmentHost(components);
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
      axialPosition: getComponentAxialPosition(
        { ...componentDefaults.Motor, length: motor.length || componentDefaults.Motor.length },
        componentMetrics.totalLength
      ),
      attachedToComponent: host?.id || null
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

  const buildSimulationPayload = (overrides = {}, sourceConfig = config, sourceOverrides = rocketOverrides) => {
    const nextConfig = mergeConfig(sourceConfig, overrides);
    const runMetrics = applyRocketOverrides(componentMetrics, sourceOverrides);

    return {
      rocketComponents: components,
      rocketSplitPoints: splitPointViews,
      rocketWeight: runMetrics.mass,
      rocketCG: runMetrics.cg,
      totalHeight: runMetrics.totalLength,
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
      rocket_weight: payload.rocketWeight,
      rocket_cg: payload.rocketCG,
      totalHeight: payload.totalHeight
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

  const runSetup = async (setup, compare = false) => {
    if (!API_URL) {
      setMessage('No local API URL is configured.');
      return;
    }
    if (!setup) {
      setMessage('Select a simulation setup first.');
      return;
    }
    setRunState('running');
    setMessage(compare ? `Comparing ${setup.label}...` : `Running ${setup.label}...`);
    try {
      const active = await submitSimulation(buildSimulationPayload({}, setup.config, setup.rocketOverrides));
      const passive = compare
        ? await submitSimulation(buildSimulationPayload({
          activePneumaticEnabled: false,
          activeSystem: { enabled: false },
          controller: { mode: 'disabled' }
        }, setup.config, setup.rocketOverrides))
        : null;
      const runCase = summarizeRun({ label: compare ? `${setup.label} comparison` : setup.label, active, passive });
      setResult(active);
      setComparisonResult(passive);
      setSelectedCaseId(runCase.id);
      setSimulationCases((current) => [runCase, ...current].slice(0, 12));
      setInspectorTab('results');
      setRunState('complete');
      setMessage(compare ? `${setup.label} comparison complete.` : `${setup.label} complete.`);
    } catch (error) {
      setRunState('error');
      setMessage(error.message);
    }
  };

  const createSetupFromCurrent = () => {
    const setup = createSimulationSetup(`Setup ${simulationSetups.length + 1}`, config, rocketOverrides);
    setSimulationSetups((current) => [setup, ...current]);
    setSelectedSetupId(setup.id);
    setInspectorTab('simulations');
    setMessage(`${setup.label} saved.`);
  };

  const updateSelectedSetupFromCurrent = () => {
    if (!selectedSimulationSetup) return;
    const updatedAt = new Date().toISOString();
    setSimulationSetups((current) => current.map((setup) => (
      setup.id === selectedSimulationSetup.id
        ? {
          ...setup,
          updatedAt,
          config: mergeConfig(defaultConfig, config),
          rocketOverrides: clonePlain(rocketOverrides, {})
        }
        : setup
    )));
    setMessage(`${selectedSimulationSetup.label} updated from current settings.`);
  };

  const renameSimulationSetup = (id, label) => {
    setSimulationSetups((current) => current.map((setup) => (
      setup.id === id ? { ...setup, label, updatedAt: new Date().toISOString() } : setup
    )));
  };

  const duplicateSimulationSetup = (setup) => {
    const copy = createSimulationSetup(`${setup.label} copy`, setup.config, setup.rocketOverrides);
    setSimulationSetups((current) => [copy, ...current]);
    setSelectedSetupId(copy.id);
    setMessage(`${copy.label} created.`);
  };

  const deleteSimulationSetup = (id) => {
    setSimulationSetups((current) => current.filter((setup) => setup.id !== id));
    setMessage('Simulation setup deleted.');
  };

  const restoreSimulationSetup = (setup) => {
    setConfig(mergeConfig(defaultConfig, setup.config));
    setRocketOverrides(clonePlain(setup.rocketOverrides, {}));
    setControllerCompileState({ status: 'idle', message: '' });
    staleResults();
    setMessage(`${setup.label} restored to the workbench.`);
  };

  const compileController = async () => {
    if (!API_URL) {
      setControllerCompileState({ status: 'error', message: 'No local API URL is configured.' });
      return;
    }
    setControllerCompileState({ status: 'running', message: 'Compiling controller...' });
    try {
      const response = await fetch(`${API_URL}/api/control-code/compile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: config.controlCode || defaultControllerCode })
      });
      const body = await response.json();
      setControllerCompileState({
        status: body.success ? 'success' : 'error',
        message: body.message || (body.success ? 'Compilation successful' : 'Compilation failed')
      });
    } catch (error) {
      setControllerCompileState({ status: 'error', message: error.message });
    }
  };

  const saveDesign = () => {
    const data = {
      id: 'browser-saved-active-rocket',
      components,
      config,
      rocketOverrides,
      splitPoints,
      simulationSetups,
      rocketData: {
        weight: metrics.mass,
        cg: metrics.cg,
        totalHeight: metrics.totalLength,
        components,
        splitPoints
      },
      simulationConfig: config,
      savedAt: new Date().toISOString()
    };
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
      const imported = normalizeImportedDesign(data);
      setComponents(imported.components);
      setSplitPoints(imported.splitPoints);
      setConfig(imported.config);
      setRocketOverrides(imported.rocketOverrides);
      setSimulationSetups(imported.simulationSetups);
      setSelectedSetupId(imported.simulationSetups[0]?.id || null);
      setControllerCompileState({ status: 'idle', message: '' });
      setSelectedId(imported.components[0]?.id || null);
      staleResults();
      setSimulationCases([]);
      setMessage('Saved design loaded.');
    } catch (error) {
      setMessage(`Load failed: ${error.message}`);
    }
  };

  const exportDesign = () => {
    const scenario = {
      id: 'active_rocket_design',
      description: 'Active rocket design with simulation-ready configuration.',
      rocketData: {
        weight: metrics.mass,
        cg: metrics.cg,
        totalHeight: metrics.totalLength,
        components,
        splitPoints
      },
      simulationConfig: config,
      components,
      splitPoints,
      config,
      rocketOverrides,
      simulationSetups,
      exportedAt: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(scenario, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'active-rocket-scenario.json';
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
          'active_drag_force',
          'weight_force',
          'net_force_x',
          'net_force_y',
          'net_force_z',
          'dynamic_pressure',
          'drag_coefficient',
          'pitch_moment',
          'yaw_moment',
          'roll_moment',
          'active_pitch_moment',
          'active_yaw_moment',
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
          'downrange_x',
          'crossrange_y',
          'range_m',
          'bearing_deg',
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
      } else if (format === 'recovery-summary') {
        const analysis = result.results.recovery_analysis || {};
        const safety = result.results.recovery_safety || {};
        const rows = [
          ...(analysis.deployment_sequence || []).map((event) => ({
            type: 'event',
            name: event.name,
            time_s: event.time_s,
            altitude_m: event.altitude_m,
            velocity_z_mps: event.velocity_z_mps,
            range_m: event.range_m,
            bearing_deg: event.bearing_deg
          })),
          ...(analysis.phases || []).map((phase) => ({
            type: 'phase',
            name: phase.name,
            start_time_s: phase.start_time_s,
            end_time_s: phase.end_time_s,
            duration_s: phase.duration_s,
            start_altitude_m: phase.start_altitude_m,
            end_altitude_m: phase.end_altitude_m,
            altitude_loss_m: phase.altitude_loss_m,
            average_descent_rate_mps: phase.average_descent_rate_mps,
            drift_m: phase.drift_m
          })),
          {
            type: 'safety',
            name: 'Recovery safety',
            status: safety.overall_status,
            main_terminal_velocity_mps: safety.main_terminal_velocity_mps,
            required_main_drag_area_m2: safety.required_main_drag_area_m2,
            main_area_margin_m2: safety.main_area_margin_m2,
            main_opening_load_g: safety.main_opening_load_g,
            drogue_opening_load_g: safety.drogue_opening_load_g,
            max_opening_load_g: safety.max_opening_load_g
          }
        ];
        const headers = [
          'type',
          'name',
          'status',
          'time_s',
          'altitude_m',
          'velocity_z_mps',
          'range_m',
          'bearing_deg',
          'start_time_s',
          'end_time_s',
          'duration_s',
          'start_altitude_m',
          'end_altitude_m',
          'altitude_loss_m',
          'average_descent_rate_mps',
          'drift_m',
          'main_terminal_velocity_mps',
          'required_main_drag_area_m2',
          'main_area_margin_m2',
          'main_opening_load_g',
          'drogue_opening_load_g',
          'max_opening_load_g'
        ];
        content = rowsToCsv(rows, headers);
        filename = 'active-rocket-recovery-summary.csv';
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
        const imported = normalizeImportedDesign(data);
        setComponents(imported.components);
        setSplitPoints(imported.splitPoints);
        setConfig(imported.config);
        setRocketOverrides(imported.rocketOverrides);
        setSimulationSetups(imported.simulationSetups);
        setSelectedSetupId(imported.simulationSetups[0]?.id || null);
        setControllerCompileState({ status: 'idle', message: '' });
        setSelectedId(imported.components[0]?.id || null);
        staleResults();
        setSimulationCases([]);
        setMessage(`${imported.id || file.name} imported.`);
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
        setSplitPoints([]);
        setRocketOverrides({});
        const nextSetups = createInitialSimulationSetups(defaultConfig, {});
        setSimulationSetups(nextSetups);
        setSelectedSetupId(nextSetups[0]?.id || null);
        setControllerCompileState({ status: 'idle', message: '' });
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
    const nextSetups = createInitialSimulationSetups(defaultConfig, {});
    setComponents(defaultComponents.map((component) => ({ ...component, id: makeId(component.type.toLowerCase().replace(/[^a-z0-9]+/g, '-')) })));
    setSplitPoints([]);
    setConfig(defaultConfig);
    setRocketOverrides({});
    setSimulationSetups(nextSetups);
    setSelectedSetupId(nextSetups[0]?.id || null);
    setControllerCompileState({ status: 'idle', message: '' });
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

  const validationItems = designChecks.length
    ? designChecks.slice(0, 8).map((check) => ({
      label: check.label,
      status: check.severity,
      detail: check.detail
    }))
    : [{
      label: 'Design ready',
      status: 'ok',
      detail: 'No live design issues found.'
    }];

  const inspector = {
    component: <ComponentInspector component={selectedComponent} components={components} updateComponent={updateComponent} metrics={metrics} fieldChecks={fieldChecks} />,
    motors: (
      <MotorBrowser
        motors={motors}
        loading={motorsLoading}
        error={motorError}
        query={motorQuery}
        setQuery={setMotorQuery}
        filters={motorFilters}
        setFilters={setMotorFilters}
        metadata={motorMetadata}
        addMotor={addMotor}
      />
    ),
    flight: (
      <FlightSetup
        config={config}
        setConfig={setConfigAndInvalidate}
        launchSites={launchSites}
        applyLaunchSite={applyLaunchSite}
        metrics={metrics}
        componentMetrics={componentMetrics}
        setRocketOverrides={setRocketOverridesAndInvalidate}
        fieldChecks={fieldChecks}
      />
    ),
    active: (
      <ActiveSetup
        config={config}
        setConfig={setConfigAndInvalidate}
        syncAirbrake={syncAirbrake}
        compileController={compileController}
        controllerCompileState={controllerCompileState}
        metrics={metrics}
        activeComponentStation={activeComponentStation}
        fieldChecks={fieldChecks}
      />
    ),
    landing: <LandingSetup config={config} setConfig={setConfigAndInvalidate} syncLanding={syncLanding} metrics={metrics} fieldChecks={fieldChecks} />,
    simulations: (
      <SimulationSetupPanel
        simulationSetups={simulationSetups}
        selectedSetupId={selectedSetupId}
        setSelectedSetupId={setSelectedSetupId}
        runState={runState}
        onCreateSetup={createSetupFromCurrent}
        onUpdateSetup={updateSelectedSetupFromCurrent}
        onDuplicateSetup={duplicateSimulationSetup}
        onDeleteSetup={deleteSimulationSetup}
        onRestoreSetup={restoreSimulationSetup}
        onRunSetup={(setup) => runSetup(setup, false)}
        onCompareSetup={(setup) => runSetup(setup, true)}
        onRenameSetup={renameSimulationSetup}
      />
    ),
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
            splitPoints={splitPoints}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            moveComponent={moveComponent}
            duplicateComponent={duplicateComponent}
            removeComponent={removeComponent}
            addSplitPoint={addSplitPoint}
            removeSplitPoint={removeSplitPoint}
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
            splitPoints={splitPoints}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            metrics={metrics}
            results={result?.results}
          />

          <div className="lower-grid">
            <ComponentTable components={components} selectedId={selectedId} setSelectedId={setSelectedId} />
            <section className="checks-panel">
              <div className="table-title">Design checks</div>
              <div className="check-list">
                {validationItems.map((item) => (
                  <div className={`check-row ${item.status}`} key={`${item.status}-${item.label}-${item.detail}`}>
                    <span>{item.status === 'error' ? 'Fix' : item.status === 'warn' ? 'Check' : item.status === 'info' ? 'Note' : 'Pass'}</span>
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
              ['simulations', 'Sims'],
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
const root = rootElement._activeRocketRoot || ReactDOM.createRoot(rootElement);
rootElement._activeRocketRoot = root;
root.render(<App />);
