"""Import a small, useful subset of OpenRocket .ork designs.

OpenRocket files are commonly XML, sometimes wrapped in a zip container. This
parser intentionally focuses on the fields R_SIM can use today: linear rocket
components, fins, motor metadata, mass/CG hints, and clear warnings when values
must be inferred.
"""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


LINEAR_COMPONENT_TAGS = {
    "nosecone": "Nose Cone",
    "bodytube": "Body Tube",
    "transition": "Transition",
}

FIN_COMPONENT_TAGS = {
    "trapezoidfinset",
    "freeformfinset",
    "ellipticalfinset",
    "finset",
}

MASS_COMPONENT_TAGS = {
    "masscomponent",
    "massobject",
    "payload",
}

RECOVERY_COMPONENT_TAGS = {
    "parachute",
    "streamer",
}

RECOVERY_HARDWARE_COMPONENT_TAGS = {
    "shockcord",
}

MOTOR_MOUNT_COMPONENT_TAGS = {
    "innertube",
}

CENTERING_RING_COMPONENT_TAGS = {
    "centeringring",
    "centeringrings",
}

AIRFRAME_HARDWARE_COMPONENT_TAGS = {
    "tubecoupler",
    "bulkhead",
}


@dataclass
class ImportedOpenRocket:
    design_name: str
    rocket_data: Dict
    warnings: List[str]


def parse_openrocket_design(payload: bytes, filename: str = "design.ork") -> ImportedOpenRocket:
    xml_bytes = _extract_xml_payload(payload, filename)
    root = ET.fromstring(xml_bytes)
    warnings: List[str] = []
    design_name = _first_text(root, ["name"]) or _filename_stem(filename) or "Imported OpenRocket Design"

    components: List[Dict] = []
    last_body_id: Optional[int] = None
    next_id = 1

    for element in root.iter():
        tag = _tag(element)
        if tag in LINEAR_COMPONENT_TAGS:
            component = _parse_linear_component(element, next_id, LINEAR_COMPONENT_TAGS[tag])
            components.append(component)
            if component["type"] in {"Body Tube", "Transition"}:
                last_body_id = component["id"]
            next_id += 1
        elif tag in FIN_COMPONENT_TAGS:
            component = _parse_fin_component(element, next_id, last_body_id)
            components.append(component)
            next_id += 1
        elif tag in MASS_COMPONENT_TAGS:
            component = _parse_mass_component(element, next_id, last_body_id)
            components.append(component)
            next_id += 1
        elif tag in RECOVERY_COMPONENT_TAGS:
            component = _parse_recovery_component(element, next_id, last_body_id, tag)
            components.append(component)
            next_id += 1
        elif tag in RECOVERY_HARDWARE_COMPONENT_TAGS:
            component = _parse_shock_cord_component(element, next_id, last_body_id)
            components.append(component)
            next_id += 1
        elif tag in MOTOR_MOUNT_COMPONENT_TAGS:
            component = _parse_motor_mount_component(element, next_id, last_body_id)
            components.append(component)
            next_id += 1
        elif tag in CENTERING_RING_COMPONENT_TAGS:
            component = _parse_centering_ring_component(element, next_id, last_body_id)
            components.append(component)
            next_id += 1
        elif tag in AIRFRAME_HARDWARE_COMPONENT_TAGS:
            component = _parse_airframe_hardware_component(element, next_id, last_body_id, tag)
            components.append(component)
            next_id += 1

    motor = _parse_motor(root, next_id, last_body_id)
    if motor:
        components.append(motor)
    else:
        warnings.append("No motor definition was found in the OpenRocket file; add/select a motor before simulation.")

    if not components:
        raise ValueError("No supported rocket components were found in the OpenRocket file.")

    total_height = _sum_linear_length_mm(components)
    weight = _find_design_mass_g(root) or _sum_component_mass_g(components)
    if not weight:
        weight = max(120.0, total_height * 0.32)
        warnings.append("No design mass was found; estimated rocket weight from imported length.")

    cg = _find_design_cg_mm(root)
    if not cg:
        cg = total_height * 0.47 if total_height else 0.0
        warnings.append("No design CG was found; estimated CG at 47% of imported length from the nose.")

    rocket_data = {
        "components": components,
        "weight": round(weight, 3),
        "cg": round(cg, 3),
        "totalHeight": round(total_height, 3),
    }
    return ImportedOpenRocket(design_name=design_name, rocket_data=rocket_data, warnings=warnings)


def _extract_xml_payload(payload: bytes, filename: str) -> bytes:
    if zipfile.is_zipfile(io.BytesIO(payload)):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith((".ork", ".xml")) and not name.endswith("/")
            ]
            if not candidates:
                raise ValueError("The .ork archive did not contain an XML design file.")
            preferred = sorted(candidates, key=lambda name: (name.lower().endswith(".xml"), len(name)))[0]
            return archive.read(preferred)
    return payload


def _parse_linear_component(element: ET.Element, component_id: int, component_type: str) -> Dict:
    length = _length_mm(_numeric_child(element, ["length", "len"]))
    radius = _numeric_child(element, ["radius", "outerradius", "aftradius", "bottomradius", "foreRadius"])
    fore_radius = _numeric_child(element, ["foreradius", "topradius"])
    aft_radius = _numeric_child(element, ["aftradius", "bottomradius", "outerradius", "radius"])
    diameter = _diameter_mm(radius)
    top_diameter = _diameter_mm(fore_radius) or diameter
    bottom_diameter = _diameter_mm(aft_radius) or diameter
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))

    return {
        "id": component_id,
        "type": component_type,
        "name": _first_text(element, ["name"]) or component_type,
        "length": length,
        "diameter": diameter,
        "topDiameter": top_diameter,
        "bottomDiameter": bottom_diameter,
        "lengthInput": _string_number(length),
        "diameterInput": _string_number(diameter),
        "topDiameterInput": _string_number(top_diameter),
        "bottomDiameterInput": _string_number(bottom_diameter),
        "weight": mass,
        "noseShape": _first_text(element, ["shape"]) if component_type == "Nose Cone" else None,
        "finShape": None,
        "finCount": None,
        "finHeight": None,
        "finWidth": None,
        "finThickness": None,
        "finSweep": None,
        "attachedToComponent": None,
        "importSource": "openrocket",
    }


def _parse_fin_component(element: ET.Element, component_id: int, attached_to: Optional[int]) -> Dict:
    fin_count = int(_numeric_child(element, ["fincount", "count", "numberoffins"]) or 3)
    height = _length_mm(_numeric_child(element, ["height", "span", "semispan"]))
    root_chord = _length_mm(_numeric_child(element, ["rootchord", "rootChord", "width", "length"]))
    tip_chord = _length_mm(_numeric_child(element, ["tipchord", "tipChord"]))
    thickness = _length_mm(_numeric_child(element, ["thickness"]))
    sweep = _length_mm(_numeric_child(element, ["sweep", "sweeplength", "sweepLength"]))
    width = root_chord or tip_chord
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))

    return {
        "id": component_id,
        "type": "Fins",
        "name": _first_text(element, ["name"]) or "Imported Fins",
        "length": 0,
        "diameter": 0,
        "topDiameter": 0,
        "bottomDiameter": 0,
        "lengthInput": "0",
        "diameterInput": "0",
        "topDiameterInput": "0",
        "bottomDiameterInput": "0",
        "weight": mass,
        "finShape": "trapezoidal",
        "finCount": fin_count,
        "finHeight": height,
        "finWidth": width,
        "finThickness": thickness,
        "finSweep": sweep,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_mass_component(element: ET.Element, component_id: int, attached_to: Optional[int]) -> Dict:
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))
    raw_position = _numeric_child(element, ["position", "axialoffset", "componentcg", "cgx"])
    axial_position = _length_mm(raw_position) if raw_position is not None else None

    return {
        "id": component_id,
        "type": "Mass Component",
        "name": _first_text(element, ["name"]) or "Imported Mass Component",
        "length": 0,
        "diameter": 0,
        "weight": mass,
        "massRole": _first_text(element, ["role", "type"]) or "payload",
        "axialPosition": axial_position,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_recovery_component(element: ET.Element, component_id: int, attached_to: Optional[int], tag: str) -> Dict:
    is_streamer = tag == "streamer"
    component_type = "Streamer" if is_streamer else "Parachute"
    name = _first_text(element, ["name"]) or f"Imported {component_type}"
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))
    role = _first_text(element, ["role"]) or ("drogue" if "drogue" in name.lower() else "main")
    deploy_altitude = _length_mm(_numeric_child(element, ["deployaltitude", "deploymentaltitude", "altitude"]))
    cd = _numeric_child(element, ["cd", "dragcoefficient"]) or (1.05 if is_streamer else 1.55)

    if is_streamer:
        streamer_length = _length_m(_numeric_child(element, ["striplength", "streamerlength", "length"]))
        streamer_width = _length_m(_numeric_child(element, ["stripwidth", "streamerwidth", "width"]))
        area = _numeric_child(element, ["dragarea", "area"])
        if not area and streamer_length > 0 and streamer_width > 0:
            area = streamer_length * streamer_width
        streamer_length = streamer_length or 1.2
        streamer_width = streamer_width or 0.08
        return {
            "id": component_id,
            "type": "Streamer",
            "name": name,
            "length": 0,
            "diameter": 0,
            "weight": mass,
            "recoveryRole": "drogue" if str(role).lower() == "drogue" else "main",
            "deployEvent": _first_text(element, ["deployevent", "deploymentevent"]) or ("apogee" if str(role).lower() == "drogue" else "altitude"),
            "deployAltitude": deploy_altitude or 120.0,
            "streamerLength": streamer_length,
            "streamerWidth": streamer_width,
            "dragArea": round(area or (streamer_length * streamer_width), 4),
            "dragCoefficient": cd,
            "maxOpeningLoadG": _numeric_child(element, ["maxopeningloadg", "openingloadlimitg"]) or 12.0,
            "attachedToComponent": attached_to,
            "importSource": "openrocket",
        }

    diameter_mm = _length_mm(_numeric_child(element, ["diameter"]))
    area = _numeric_child(element, ["dragarea", "area"])
    if not area and diameter_mm > 0:
        area = 3.141592653589793 * (diameter_mm / 2000.0) ** 2

    return {
        "id": component_id,
        "type": "Parachute",
        "name": name,
        "length": 0,
        "diameter": 0,
        "weight": mass,
        "recoveryRole": "drogue" if str(role).lower() == "drogue" else "main",
        "deployEvent": _first_text(element, ["deployevent", "deploymentevent"]) or ("apogee" if str(role).lower() == "drogue" else "altitude"),
        "deployAltitude": deploy_altitude or 120.0,
        "dragArea": round(area or 0.18, 4),
        "dragCoefficient": cd,
        "maxOpeningLoadG": _numeric_child(element, ["maxopeningloadg", "openingloadlimitg"]) or 15.0,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_shock_cord_component(element: ET.Element, component_id: int, attached_to: Optional[int]) -> Dict:
    name = _first_text(element, ["name"]) or "Imported Shock Cord"
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))
    cord_length = _length_m(_numeric_child(element, ["length", "cordlength", "shockcordlength"]))
    cord_diameter = _length_mm(_numeric_child(element, ["diameter", "corddiameter", "shockcorddiameter"]))
    max_tension = _numeric_child(element, ["maxtensionn", "maxtension", "maxloadn", "maxload", "strengthn", "strength"])

    return {
        "id": component_id,
        "type": "Shock Cord",
        "name": name,
        "length": 0,
        "diameter": 0,
        "weight": mass,
        "cordLength": cord_length or 3.0,
        "cordDiameter": cord_diameter or 3.0,
        "maxTensionN": max_tension or 450.0,
        "material": _first_text(element, ["material"]) or "nylon",
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_motor_mount_component(element: ET.Element, component_id: int, attached_to: Optional[int]) -> Dict:
    name = _first_text(element, ["name"]) or "Imported Motor Mount"
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))
    mount_length = _length_mm(_numeric_child(element, ["length", "tubeLength", "motorMountLength"]))
    inner_diameter = (
        _diameter_mm(_numeric_child(element, ["innerRadius", "motorRadius"]))
        or _length_mm(_numeric_child(element, ["innerDiameter", "motorDiameter"]))
    )
    outer_diameter = (
        _diameter_mm(_numeric_child(element, ["outerRadius", "radius"]))
        or _length_mm(_numeric_child(element, ["outerDiameter", "diameter"]))
    )
    axial_position = _length_mm(_numeric_child(element, ["position", "axialOffset", "componentCG", "cgx"]))

    if not outer_diameter and inner_diameter:
        outer_diameter = inner_diameter + 4.0
    if not inner_diameter and outer_diameter:
        inner_diameter = max(0.0, outer_diameter - 4.0)

    return {
        "id": component_id,
        "type": "Motor Mount",
        "name": name,
        "length": 0,
        "diameter": 0,
        "weight": mass,
        "mountLength": mount_length or 120.0,
        "innerDiameter": inner_diameter or 29.0,
        "outerDiameter": outer_diameter or 34.0,
        "material": _first_text(element, ["material"]) or "phenolic",
        "axialPosition": axial_position or None,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_centering_ring_component(element: ET.Element, component_id: int, attached_to: Optional[int]) -> Dict:
    name = _first_text(element, ["name"]) or "Imported Centering Ring"
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))
    ring_count = int(_numeric_child(element, ["ringCount", "count", "instanceCount", "numberOfRings"]) or 1)
    inner_diameter = (
        _diameter_mm(_numeric_child(element, ["innerRadius", "motorRadius"]))
        or _length_mm(_numeric_child(element, ["innerDiameter", "motorDiameter"]))
    )
    outer_diameter = (
        _diameter_mm(_numeric_child(element, ["outerRadius", "bodyRadius", "radius"]))
        or _length_mm(_numeric_child(element, ["outerDiameter", "bodyDiameter", "diameter"]))
    )
    thickness = _length_mm(_numeric_child(element, ["thickness", "ringThickness", "length"]))
    axial_position = _length_mm(_numeric_child(element, ["position", "axialOffset", "componentCG", "cgx"]))

    return {
        "id": component_id,
        "type": "Centering Ring",
        "name": name,
        "length": 0,
        "diameter": 0,
        "weight": mass,
        "ringCount": max(1, ring_count),
        "innerDiameter": inner_diameter or 29.0,
        "outerDiameter": outer_diameter or 40.0,
        "thickness": thickness or 3.0,
        "material": _first_text(element, ["material"]) or "plywood",
        "axialPosition": axial_position or None,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_airframe_hardware_component(element: ET.Element, component_id: int, attached_to: Optional[int], tag: str) -> Dict:
    is_bulkhead = tag == "bulkhead"
    component_type = "Bulkhead" if is_bulkhead else "Tube Coupler"
    name = _first_text(element, ["name"]) or f"Imported {component_type}"
    mass = _mass_g(_numeric_child(element, ["mass", "massoverride", "componentmass"]))
    outer_diameter = (
        _diameter_mm(_numeric_child(element, ["outerRadius", "radius"]))
        or _length_mm(_numeric_child(element, ["outerDiameter", "diameter"]))
    )
    thickness = _length_mm(_numeric_child(element, ["thickness", "bulkheadThickness", "length"]))
    axial_position = _length_mm(_numeric_child(element, ["position", "axialOffset", "componentCG", "cgx"]))

    if is_bulkhead:
        return {
            "id": component_id,
            "type": "Bulkhead",
            "name": name,
            "length": 0,
            "diameter": 0,
            "weight": mass,
            "outerDiameter": outer_diameter or 40.0,
            "thickness": thickness or 3.0,
            "material": _first_text(element, ["material"]) or "plywood",
            "axialPosition": axial_position or None,
            "attachedToComponent": attached_to,
            "importSource": "openrocket",
        }

    coupler_length = _length_mm(_numeric_child(element, ["length", "couplerLength", "tubeCouplerLength"]))
    inner_diameter = (
        _diameter_mm(_numeric_child(element, ["innerRadius"]))
        or _length_mm(_numeric_child(element, ["innerDiameter"]))
    )
    if not outer_diameter and inner_diameter:
        outer_diameter = inner_diameter + 4.0
    if not inner_diameter and outer_diameter:
        inner_diameter = max(0.0, outer_diameter - 4.0)

    return {
        "id": component_id,
        "type": "Tube Coupler",
        "name": name,
        "length": 0,
        "diameter": 0,
        "weight": mass,
        "couplerLength": coupler_length or 80.0,
        "innerDiameter": inner_diameter or 48.0,
        "outerDiameter": outer_diameter or 52.0,
        "material": _first_text(element, ["material"]) or "phenolic",
        "axialPosition": axial_position or None,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _parse_motor(root: ET.Element, component_id: int, attached_to: Optional[int]) -> Optional[Dict]:
    motor_element = next((element for element in root.iter() if _tag(element) == "motor"), None)
    if motor_element is None:
        return None

    designation = (
        _first_text(motor_element, ["designation", "digest", "name"])
        or motor_element.attrib.get("designation")
        or motor_element.attrib.get("digest")
        or "Imported Motor"
    )
    manufacturer = _first_text(motor_element, ["manufacturer"]) or motor_element.attrib.get("manufacturer") or ""
    impulse_class = _first_text(motor_element, ["designationclass", "impulseclass", "class"]) or designation[:1]
    diameter = _length_mm(_numeric_child(motor_element, ["diameter"])) or 18.0
    length = _length_mm(_numeric_child(motor_element, ["length"])) or 70.0
    burn_time = _numeric_child(motor_element, ["burntime", "burnTime"]) or 1.6
    total_impulse = _numeric_child(motor_element, ["totalimpulse", "totalImpulse"]) or 10.0
    avg_thrust = _numeric_child(motor_element, ["averagethrust", "avgthrust", "averageThrust"]) or (
        total_impulse / burn_time if burn_time else 6.0
    )
    mass = _mass_g(_numeric_child(motor_element, ["mass", "totalmass", "totalMass"])) or 17.0

    return {
        "id": component_id,
        "type": "Motor",
        "name": " ".join(part for part in [manufacturer, designation] if part).strip() or designation,
        "length": length,
        "diameter": diameter,
        "topDiameter": diameter,
        "bottomDiameter": diameter,
        "lengthInput": _string_number(length),
        "diameterInput": _string_number(diameter),
        "topDiameterInput": _string_number(diameter),
        "bottomDiameterInput": _string_number(diameter),
        "weight": mass,
        "motorType": manufacturer or None,
        "motorModel": designation,
        "motorImpulse": impulse_class,
        "motorThrust": avg_thrust,
        "motorBurnTime": burn_time,
        "motorTotalImpulse": total_impulse,
        "motorWeight": mass,
        "attachedToComponent": attached_to,
        "importSource": "openrocket",
    }


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].replace("-", "").replace("_", "").lower()


def _iter_children(element: ET.Element) -> Iterable[ET.Element]:
    for child in list(element):
        yield child


def _first_text(element: ET.Element, names: List[str]) -> Optional[str]:
    wanted = {_normalize_name(name) for name in names}
    for child in _iter_children(element):
        if _tag(child) in wanted and child.text and child.text.strip():
            return child.text.strip()
    for child in element.iter():
        if child is element:
            continue
        if _tag(child) in wanted and child.text and child.text.strip():
            return child.text.strip()
    return None


def _numeric_child(element: ET.Element, names: List[str]) -> Optional[float]:
    text = _first_text(element, names)
    if text is None:
        return None
    try:
        return float(str(text).strip().split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def _normalize_name(name: str) -> str:
    return name.replace("-", "").replace("_", "").lower()


def _length_mm(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    return round(value * 1000.0, 4) if abs(value) <= 5 else round(value, 4)


def _length_m(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    return round(value / 1000.0, 4) if abs(value) > 20 else round(value, 4)


def _diameter_mm(radius_value: Optional[float]) -> float:
    if radius_value is None:
        return 0.0
    diameter = radius_value * 2.0
    return _length_mm(diameter)


def _mass_g(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    return round(value * 1000.0, 4) if abs(value) <= 10 else round(value, 4)


def _find_design_mass_g(root: ET.Element) -> float:
    rocket = next((element for element in root.iter() if _tag(element) == "rocket"), root)
    return _mass_g(_direct_numeric_child(rocket, ["mass", "massoverride", "totalmass", "rocketmass"]))


def _find_design_cg_mm(root: ET.Element) -> float:
    rocket = next((element for element in root.iter() if _tag(element) == "rocket"), root)
    return _length_mm(_direct_numeric_child(rocket, ["cg", "cgoverride", "centerofgravity", "cgx"]))


def _direct_numeric_child(element: ET.Element, names: List[str]) -> Optional[float]:
    wanted = {_normalize_name(name) for name in names}
    for child in _iter_children(element):
        if _tag(child) in wanted and child.text and child.text.strip():
            try:
                return float(child.text.strip().split()[0])
            except (TypeError, ValueError, IndexError):
                return None
    return None


def _sum_linear_length_mm(components: List[Dict]) -> float:
    internal_types = {
        "Fins",
        "Motor",
        "Mass Component",
        "Parachute",
        "Streamer",
        "Shock Cord",
        "Motor Mount",
        "Centering Ring",
        "Tube Coupler",
        "Bulkhead",
    }
    return sum(component.get("length") or 0 for component in components if component.get("type") not in internal_types)


def _sum_component_mass_g(components: List[Dict]) -> float:
    return sum(component.get("weight") or component.get("motorWeight") or 0 for component in components)


def _filename_stem(filename: str) -> str:
    name = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.rsplit(".", 1)[0]


def _string_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)
