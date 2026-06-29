"""Vehicle mass properties."""

from rocketsim.vehicle.mass import (
    MassProperties,
    PartMassState,
    VehicleModel,
    load_vehicle_definition,
    mass_properties,
    properties_as_dict,
)
from rocketsim.vehicle.schema import (
    DepletionPoint,
    DepletionProfile,
    DeployableLegKinematics,
    PartDefinition,
    PositionPoint,
    PositionProfile,
    VehicleDefinition,
)

__all__ = [
    "DepletionPoint",
    "DepletionProfile",
    "DeployableLegKinematics",
    "MassProperties",
    "PartDefinition",
    "PartMassState",
    "PositionPoint",
    "PositionProfile",
    "VehicleDefinition",
    "VehicleModel",
    "load_vehicle_definition",
    "mass_properties",
    "properties_as_dict",
]
