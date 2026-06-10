# backend/src/common/models.py
from __future__ import annotations

import dataclasses
import enum
from typing import Any


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[self.value]


@dataclasses.dataclass
class Target:
    ip: str
    port: int
    endpoint: str

    @classmethod
    def from_parts(cls, ip: str, port: int, endpoint: str) -> "Target":
        ep = endpoint if endpoint.startswith("/") else "/" + endpoint
        return cls(ip=ip, port=int(port), endpoint=ep)

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    def to_dict(self) -> dict[str, Any]:
        return {"ip": self.ip, "port": self.port, "endpoint": self.endpoint, "url": self.url}


@dataclasses.dataclass
class ScanContext:
    scan_id: str
    target: str            # base URL
    endpoint: str = "/"
    options: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Finding:
    scan_id: str
    finding_id: str
    title: str
    severity: Severity
    endpoint: str
    evidence: str
    poc: str = ""
    remediation: str = ""
    attack_method: str = ""
    persona: str = ""

    def to_item(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "Finding":
        item = dict(item)
        item["severity"] = Severity(item["severity"])
        return cls(**item)
