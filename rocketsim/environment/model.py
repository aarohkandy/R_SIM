"""Environment aggregate loader and model."""

from __future__ import annotations

from pathlib import Path

import yaml

from rocketsim.environment.atmosphere import ISAAtmosphere
from rocketsim.environment.rail import LaunchRail
from rocketsim.environment.schema import EnvironmentDefinition
from rocketsim.environment.wind import WindModel


class EnvironmentModel:
    """Aggregate environment model for atmosphere, wind, and launch rail."""

    def __init__(self, definition: EnvironmentDefinition) -> None:
        self.definition = definition
        self.atmosphere = ISAAtmosphere(definition.data.atmosphere)
        self.wind = WindModel(definition.data.wind)
        self.launch_rail = LaunchRail(definition.data.launch_rail)

    @classmethod
    def from_config_path(cls, path: Path | str) -> EnvironmentModel:
        return cls(load_environment_definition(path))


def load_environment_definition(path: Path | str) -> EnvironmentDefinition:
    """Load config/environment.yaml into a strict environment definition."""

    environment_path = Path(path)
    raw = yaml.safe_load(environment_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{environment_path} must contain a YAML mapping"
        raise TypeError(msg)
    return EnvironmentDefinition.model_validate(raw)
