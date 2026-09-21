from __future__ import annotations

import platform

from .collectors import collect_nvme, collect_smartctl, collect_sysfs
from .discovery import discover_linux
from .models import TelemetryRecord
from .normalize import normalize
from .windows import scan_windows


def scan_linux() -> list[TelemetryRecord]:
    records: list[TelemetryRecord] = []
    for device in discover_linux():
        sysfs = collect_sysfs(device)
        smart, smart_status = collect_smartctl(device)
        nvme, nvme_status = collect_nvme(device)
        sources = [{"source": "sysfs", "status": "ok"}, smart_status, nvme_status]
        records.append(normalize(device, sysfs, smart, nvme, sources))
    return records


def scan() -> list[TelemetryRecord]:
    system = platform.system()
    if system == "Linux":
        return scan_linux()
    if system == "Windows":
        return scan_windows()
    raise RuntimeError(f"unsupported operating system: {system}")
