"""Controller backend seam and native SIL implementation."""

from rocketsim.control.backend import ControllerBackend
from rocketsim.control.backend_renode import (
    RenodeBlocker,
    RenodeComponentStatus,
    RenodeHILBackend,
    RenodeHilReport,
    RenodeHilStatusResult,
    RenodeUnavailableError,
    actuator_levels_to_valves,
    build_renode_hil_report,
    read_latest_hil_status,
    run_renode_hil_status,
    sensor_packet_to_injection_frame,
)
from rocketsim.control.backend_sil import NativeSILBackend, PendingCommand, valve_timeline_durations
from rocketsim.control.schema import (
    ControlConfig,
    ControlData,
    RenodeActuationConfig,
    RenodeHilConfig,
    RenodeInterMcuLinkConfig,
    RenodeMachineConfig,
    RenodeSensorInjectionConfig,
    SILControllerConfig,
    load_control_config,
)

__all__ = [
    "ControlConfig",
    "ControlData",
    "ControllerBackend",
    "NativeSILBackend",
    "PendingCommand",
    "RenodeActuationConfig",
    "RenodeBlocker",
    "RenodeComponentStatus",
    "RenodeHILBackend",
    "RenodeHilConfig",
    "RenodeHilReport",
    "RenodeHilStatusResult",
    "RenodeInterMcuLinkConfig",
    "RenodeMachineConfig",
    "RenodeSensorInjectionConfig",
    "RenodeUnavailableError",
    "SILControllerConfig",
    "actuator_levels_to_valves",
    "build_renode_hil_report",
    "load_control_config",
    "read_latest_hil_status",
    "run_renode_hil_status",
    "sensor_packet_to_injection_frame",
    "valve_timeline_durations",
]
