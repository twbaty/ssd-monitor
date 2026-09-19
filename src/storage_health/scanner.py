from __future__ import annotations

from .collectors import collect_nvme, collect_smartctl, collect_sysfs
from .discovery import discover_linux
from .models import TelemetryRecord
from .normalize import normalize


def scan_linux() -> list[TelemetryRecord]:
    records: list[TelemetryRecord] = []
    for device in discover_linux():
        sysfs = collect_sysfs(device)
        smart, smart_status = collect_smartctl(device)
        nvme, nvme_status = collect_nvme(device)
        sources = [{"source": "sysfs", "status": "ok"}, smart_status, nvme_status]
        records.append(normalize(device, sysfs, smart, nvme, sources))
    return records

