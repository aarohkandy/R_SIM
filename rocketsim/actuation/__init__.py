"""Bang-bang valve actuation and control allocation."""

from rocketsim.actuation.model import (
    AllocationResult,
    ControlAllocator,
    ControlDemand,
    SolenoidValveBank,
    ValveCommands,
    allocation_matrix,
)
from rocketsim.actuation.schema import (
    ActuationConfig,
    ActuationData,
    AllocationConfig,
    FaultInjectionConfig,
    load_actuation_config,
)

__all__ = [
    "ActuationConfig",
    "ActuationData",
    "AllocationConfig",
    "AllocationResult",
    "ControlAllocator",
    "ControlDemand",
    "FaultInjectionConfig",
    "SolenoidValveBank",
    "ValveCommands",
    "allocation_matrix",
    "load_actuation_config",
]
