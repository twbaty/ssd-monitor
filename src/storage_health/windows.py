from __future__ import annotations

import json
from typing import Any, Callable

from .collectors import collect_smartctl
from .command import CommandResult, available, run
from .models import PhysicalDevice, TelemetryRecord
from .normalize import normalize

Runner = Callable[[list[str], int], CommandResult]

_POWERSHELL_SCRIPT = """
$ErrorActionPreference = 'Stop'
$physical = @{}
Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object {
  $physical[[string]$_.DeviceId] = $_
}
Get-CimInstance Win32_DiskDrive | ForEach-Object {
  $p = $physical[[string]$_.Index]
  [pscustomobject]@{
    Index = $_.Index
    DeviceID = $_.DeviceID
    Model = $_.Model
    SerialNumber = $_.SerialNumber
    FirmwareRevision = $_.FirmwareRevision
    InterfaceType = $_.InterfaceType
    Size = $_.Size
    Status = $_.Status
    PNPDeviceID = $_.PNPDeviceID
    BusType = if ($p) { [string]$p.BusType } else { $null }
    MediaType = if ($p) { [string]$p.MediaType } else { [string]$_.MediaType }
    HealthStatus = if ($p) { [string]$p.HealthStatus } else { $null }
    OperationalStatus = if ($p) { @($p.OperationalStatus | ForEach-Object { [string]$_ }) } else { @() }
  }
} | ConvertTo-Json -Depth 4 -Compress
""".strip()


def _powershell() -> str | None:
    if available("powershell.exe"):
        return "powershell.exe"
    if available("pwsh"):
        return "pwsh"
    return None


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def parse_windows_disks(payload: Any) -> list[tuple[PhysicalDevice, dict[str, Any], str]]:
    disks: list[tuple[PhysicalDevice, dict[str, Any], str]] = []
    for item in _as_list(payload):
        index = item.get("Index")
        if not isinstance(index, int):
            continue
        device_id = item.get("DeviceID") or rf"\\.\PHYSICALDRIVE{index}"
        media_type = item.get("MediaType")
        media_text = str(media_type).lower() if media_type is not None else ""
        rotational = False if "ssd" in media_text or "solid state" in media_text else None
        transport = item.get("BusType") or item.get("InterfaceType")
        transport = str(transport).lower() if transport else None
        size = item.get("Size")
        try:
            size_bytes = int(size) if size is not None else None
        except (TypeError, ValueError):
            size_bytes = None

        device = PhysicalDevice(
            name=f"PhysicalDrive{index}",
            path=str(device_id),
            sys_path=str(item.get("PNPDeviceID") or ""),
            major_minor=None,
            transport=transport,
            stable_id=f"windows:{index}",
        )
        native = {
            "model": _clean(item.get("Model")),
            "vendor": None,
            "serial": _clean(item.get("SerialNumber")),
            "firmware": _clean(item.get("FirmwareRevision")),
            "rotational": rotational,
            "size_bytes": size_bytes,
            "native_status": {
                "status": item.get("Status"),
                "health": item.get("HealthStatus"),
                "operational": _string_list(item.get("OperationalStatus")),
            },
        }
        disks.append((device, native, f"/dev/pd{index}"))
    return disks


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [cleaned for item in values if (cleaned := _clean(item))]


def scan_windows(runner: Runner = run) -> list[TelemetryRecord]:
    shell = _powershell()
    if not shell:
        raise RuntimeError("PowerShell is required for Windows disk discovery")
    result = runner([shell, "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_SCRIPT], 30)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        message = result.stderr.strip() or "PowerShell returned invalid JSON"
        raise RuntimeError(message) from exc

    records: list[TelemetryRecord] = []
    for device, native, smart_path in parse_windows_disks(payload):
        smart, smart_status = collect_smartctl(device, runner=runner, smart_path=smart_path)
        sources = [
            {"source": "windows-cim", "status": "ok"},
            smart_status,
            {"source": "nvme-cli", "status": "unsupported_on_platform"},
        ]
        records.append(normalize(device, native, smart, None, sources))
    return records
