from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rocketsim.config import dump_config, load_config, load_config_dir

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def test_all_phase0_configs_load() -> None:
    documents = load_config_dir(CONFIG_DIR)

    assert set(documents) == {
        "actuation",
        "aero",
        "coldgas",
        "control",
        "environment",
        "motor",
        "sensors",
        "sim",
        "structural",
        "thermal",
        "vehicle",
    }
    assert all(document.placeholder for document in documents.values())


def test_config_round_trip(tmp_path: Path) -> None:
    original = load_config(CONFIG_DIR / "sim.yaml")
    target = tmp_path / "sim.yaml"

    dump_config(original, target)

    assert load_config(target) == original


def test_strict_validation_rejects_unknown_fields(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "name: invalid",
                "description: Invalid config with extra field.",
                "placeholder: true",
                "unexpected: value",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_config(invalid)


def test_config_name_must_be_slug(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "name: invalid name",
                "description: Invalid config with bad name.",
                "placeholder: true",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="name must contain"):
        load_config(invalid)


def test_loader_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML mapping"):
        load_config(invalid)
