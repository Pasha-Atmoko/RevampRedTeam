# backend/src/common/scope_guard.py
from __future__ import annotations

import ipaddress
import os
from functools import lru_cache
from urllib.parse import urlparse

import boto3

SCOPE_PARAM = os.environ.get("SCOPE_PARAM_NAME", "/tier2/scope-allowlist")


class ScopeError(Exception):
    """Raised when a target is not covered by the configured allowlist."""


@lru_cache(maxsize=1)
def _ssm():
    return boto3.client("ssm")


def _load_allowlist() -> list[str]:
    resp = _ssm().get_parameter(Name=SCOPE_PARAM)
    raw = resp["Parameter"]["Value"]
    return [s.strip() for s in raw.replace(",", "\n").splitlines() if s.strip()]


def _split_host_port(target: str) -> tuple[str, int | None]:
    parsed = urlparse(target if "://" in target else f"//{target}")
    return parsed.hostname or "", parsed.port


def _matches(host: str, port: int | None, entry: str) -> bool:
    if "/" in entry:
        try:
            return ipaddress.ip_address(host) in ipaddress.ip_network(entry, strict=False)
        except ValueError:
            return False
    if ":" in entry:
        e_host, _, e_port = entry.partition(":")
        return host == e_host and (port is None or str(port) == e_port)
    return host == entry


def assert_in_scope(target: str, allowlist: list[str] | None = None) -> None:
    host, port = _split_host_port(target)
    if not host:
        raise ScopeError(f"Cannot parse host from target: {target!r}")
    entries = allowlist if allowlist is not None else _load_allowlist()
    if not entries:
        raise ScopeError("Scope allowlist is empty - refusing to scan anything.")
    if any(_matches(host, port, e) for e in entries):
        return
    raise ScopeError(f"Target {host}:{port or '*'} is NOT in the authorized scope allowlist.")
