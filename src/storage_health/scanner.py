from __future__ import annotations

import platform

from .collectors import collect_nvme, collect_smartctl, collect_sysfs
from .discovery import discover_linux
from .models import TelemetryRecord
from .normalize import normalize
from .windows import scan_windows


def scan_linux(native_only: bool = False) -> list[TelemetryRecord]:
    records: list[TelemetryRecord] = []
    for device in discover_linux():
        sysfs = collect_sysfs(device)
        if native_only:
            smart, smart_status = None, {"source": "smartctl", "status": "disabled"}
            nvme, nvme_status = None, {"source": "nvme-cli", "status": "disabled"}
        else:
            smart, smart_status = collect_smartctl(device)
            nvme, nvme_status = collect_nvme(device)
        sources = [{"source": "sysfs", "status": "ok"}, smart_status, nvme_status]
        records.append(normalize(device, sysfs, smart, nvme, sources))
    return records


def scan(native_only: bool = False) -> list[TelemetryRecord]:
    system = platform.system()
    if system == "Linux":
        return scan_linux(native_only=native_only)
    if system == "Windows":
        return scan_windows(native_only=native_only)
    raise RuntimeError(f"unsupported operating system: {system}")
