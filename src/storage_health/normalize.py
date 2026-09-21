from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import PhysicalDevice, TelemetryRecord


def _first(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _nested(data: dict[str, Any] | None, *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _kelvin_to_celsius(value: Any) -> int | float | None:
    if not isinstance(value, (int, float)):
        return None
    # nvme-cli commonly reports Kelvin, while some versions report Celsius.
    return round(value - 273.15, 2) if value > 200 else value


def normalize(
    device: PhysicalDevice,
    sysfs: dict[str, Any],
    smart: dict[str, Any] | None,
    nvme: dict[str, Any] | None,
    source_status: list[dict[str, Any]],
) -> TelemetryRecord:
    smart_temp = _nested(smart, "temperature", "current")
    nvme_temp = _first(_nested(nvme, "temperature"), _nested(nvme, "composite_temperature"))
    passed = _nested(smart, "smart_status", "passed")
    critical_warning = _nested(nvme, "critical_warning")
    smart_protocol = _nested(smart, "device", "protocol")
    if isinstance(smart_protocol, str):
        smart_protocol = smart_protocol.lower()

    return TelemetryRecord(
        device={
            "id": _first(device.stable_id, device.major_minor, device.path),
            "path": device.path,
            "name": device.name,
            "major_minor": device.major_minor,
            "transport": _first(device.transport, smart_protocol),
            "rotational": sysfs.get("rotational"),
            "capacity_bytes": _first(sysfs.get("size_bytes"), smart and smart.get("user_capacity", {}).get("bytes")),
        },
        identity={
            "model": _first(smart and smart.get("model_name"), sysfs.get("model")),
            "vendor": sysfs.get("vendor"),
            "serial": _first(smart and smart.get("serial_number"), sysfs.get("serial")),
            "firmware": _first(smart and smart.get("firmware_version"), sysfs.get("firmware")),
        },
        health={
            "native_status": sysfs.get("native_status"),
            "smart_passed": passed if isinstance(passed, bool) else None,
            "nvme_critical_warning": critical_warning if isinstance(critical_warning, int) else None,
            "percentage_used": _first(_nested(nvme, "percentage_used"), _nested(smart, "nvme_smart_health_information_log", "percentage_used")),
            "available_spare_percent": _first(_nested(nvme, "avail_spare"), _nested(smart, "nvme_smart_health_information_log", "available_spare")),
        },
        usage={
            "power_on_hours": _first(_nested(nvme, "power_on_hours"), _nested(smart, "power_on_time", "hours"), _nested(smart, "nvme_smart_health_information_log", "power_on_hours")),
            "power_cycles": _first(_nested(nvme, "power_cycles"), _nested(smart, "power_cycle_count"), _nested(smart, "nvme_smart_health_information_log", "power_cycles")),
            "data_units_read": _first(_nested(nvme, "data_units_read"), _nested(smart, "nvme_smart_health_information_log", "data_units_read")),
            "data_units_written": _first(_nested(nvme, "data_units_written"), _nested(smart, "nvme_smart_health_information_log", "data_units_written")),
        },
        temperature={"celsius": _first(smart_temp, _kelvin_to_celsius(nvme_temp))},
        errors={
            "media_errors": _first(_nested(nvme, "media_errors"), _nested(smart, "nvme_smart_health_information_log", "media_errors")),
            "unsafe_shutdowns": _first(_nested(nvme, "unsafe_shutdowns"), _nested(smart, "nvme_smart_health_information_log", "unsafe_shutdowns")),
        },
        collection={
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sources": source_status,
        },
    )
