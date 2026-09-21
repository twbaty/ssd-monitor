from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PhysicalDevice:
    name: str
    path: str
    sys_path: str
    major_minor: str | None
    transport: str | None = None
    stable_id: str | None = None


@dataclass
class TelemetryRecord:
    schema_version: str = "1.0"
    device: dict[str, Any] = field(default_factory=dict)
    identity: dict[str, Any] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    temperature: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, Any] = field(default_factory=dict)
    collection: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
