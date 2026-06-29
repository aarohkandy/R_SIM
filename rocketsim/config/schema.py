"""Pydantic schema used by the Phase-0 YAML configuration scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class ConfigDocument(BaseModel):
    """Shared wrapper for versioned YAML config files.

    Later phases should replace or extend this with domain-specific schemas while keeping
    strict validation and versioned documents.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_must_be_slug(cls, value: str) -> str:
        if not value.replace("_", "-").replace("-", "").isalnum():
            msg = "name must contain only letters, numbers, underscores, or hyphens"
            raise ValueError(msg)
        return value
