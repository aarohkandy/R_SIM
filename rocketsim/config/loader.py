"""YAML configuration loader for Phase 0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rocketsim.config.schema import ConfigDocument


def load_config(path: Path | str) -> ConfigDocument:
    """Load and validate a single YAML config document."""

    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{config_path} must contain a YAML mapping"
        raise TypeError(msg)
    return ConfigDocument.model_validate(raw)


def dump_config(config: ConfigDocument, path: Path | str) -> None:
    """Write a validated config document as deterministic YAML."""

    config_path = Path(path)
    payload: dict[str, Any] = config.model_dump(mode="python")
    text = yaml.safe_dump(payload, sort_keys=True)
    config_path.write_text(text, encoding="utf-8")


def load_config_dir(path: Path | str) -> dict[str, ConfigDocument]:
    """Load all YAML documents in a directory keyed by stem."""

    config_dir = Path(path)
    return {item.stem: load_config(item) for item in sorted(config_dir.glob("*.yaml"))}
