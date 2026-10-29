"""Harmless mock tools. They only read local synthetic JSON.

Destructive names exist as stubs so policy tests can prove they never succeed.
They do not touch cloud APIs, shells, or the filesystem beyond the catalog.
"""

from __future__ import annotations

import json
from typing import Any

from safeops import catalog


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2)


def list_incidents() -> str:
    """List synthetic open incidents."""
    rows = [
        {
            "incident_id": row["incident_id"],
            "title": row["title"],
            "severity": row["severity"],
            "resource_name": row["resource_name"],
        }
        for row in catalog.incidents()
    ]
    return _json(rows)


def get_incident(incident_id: str) -> str:
    """Return one synthetic incident by id."""
    try:
        return _json(catalog.get_incident(incident_id))
    except catalog.CatalogError as exc:
        return _json({"error": str(exc)})


def get_resource(resource: str) -> str:
    """Describe a synthetic compute resource by name or mock instance id."""
    try:
        return _json(catalog.get_resource(resource))
    except catalog.CatalogError as exc:
        return _json({"error": str(exc)})


def get_metrics(resource: str) -> str:
    """Return synthetic latency and error metrics for a resource."""
    data = catalog.load_catalog()
    try:
        row = catalog.get_resource(resource)
    except catalog.CatalogError as exc:
        return _json({"error": str(exc)})
    metrics = data["metrics"].get(row["name"], {})
    return _json({"resource": row["name"], "metrics": metrics})


def get_logs(resource: str) -> str:
    """Return synthetic application logs for a resource."""
    data = catalog.load_catalog()
    try:
        row = catalog.get_resource(resource)
    except catalog.CatalogError as exc:
        return _json({"error": str(exc)})
    lines = data["logs"].get(row["name"], [])
    return _json({"resource": row["name"], "lines": lines})


def list_alarms() -> str:
    """List synthetic cloudwatch-style alarms."""
    return _json(catalog.load_catalog()["alarms"])


def reboot_instance(resource_id: str) -> str:
    """Stub. Must never run; policy blocks it first."""
    raise RuntimeError(
        f"blocked: reboot_instance({resource_id!r}) is destructive and is not implemented"
    )


def terminate_instance(resource_id: str) -> str:
    """Stub. Must never run; policy blocks it first."""
    raise RuntimeError(
        f"blocked: terminate_instance({resource_id!r}) is destructive and is not implemented"
    )


def delete_volume(volume_id: str) -> str:
    """Stub. Must never run; policy blocks it first."""
    raise RuntimeError(
        f"blocked: delete_volume({volume_id!r}) is destructive and is not implemented"
    )
