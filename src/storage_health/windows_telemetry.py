from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .models import PhysicalDevice
from .normalize import normalize


@dataclass(frozen=True)
class WindowsDisk:
    key: str
    model: str | None = None
    serial: str | None = None


def _identity(value: Any) -> str:
    return re.sub(r"\s+", "", value).casefold() if isinstance(value, str) else ""


def _descriptor_string(data: bytes, offset: int) -> str | None:
    if offset <= 0 or offset >= len(data):
        return None
    value = data[offset:].split(b"\0", 1)[0].decode("ascii", "replace").strip()
    return value or None


def parse_storage_descriptor(data: bytes, index: int) -> WindowsDisk | None:
    """Read the device descriptor returned by IOCTL_STORAGE_QUERY_PROPERTY."""
    if len(data) < 36:
        return None
    fields = struct.unpack_from("<IIBBBBIIIIII", data)
    declared_size = fields[1]
    if declared_size < 36:
        return None
    data = data[:min(declared_size, len(data))]
    vendor = _descriptor_string(data, fields[6])
    product = _descriptor_string(data, fields[7])
    model = " ".join(part for part in (vendor, product) if part) or None
    return WindowsDisk(f"PhysicalDrive{index}", model, _descriptor_string(data, fields[9]))


def query_physical_drive(index: int) -> WindowsDisk | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                       wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateFileW(f"\\\\.\\PhysicalDrive{index}", 0, 0x3, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        return None
    try:
        query = ctypes.create_string_buffer(struct.pack("<II", 0, 0))
        result = ctypes.create_string_buffer(4096)
        returned = wintypes.DWORD()
        success = kernel.DeviceIoControl(handle, 0x002D1400, query, len(query), result,
                                         len(result), ctypes.byref(returned), None)
        return parse_storage_descriptor(result.raw[:returned.value], index) if success else None
    finally:
        kernel.CloseHandle(handle)


def discover_windows_disks(io_keys: Iterable[str] = ()) -> list[WindowsDisk]:
    indices = set(range(16))
    for key in io_keys:
        match = re.fullmatch(r"PhysicalDrive(\d+)", key, re.IGNORECASE)
        if match:
            indices.add(int(match.group(1)))
    disks: list[WindowsDisk] = []
    for index in sorted(indices):
        disk = query_physical_drive(index)
        if disk is not None:
            disks.append(disk)
        elif any(key.casefold() == f"physicaldrive{index}" for key in io_keys):
            disks.append(WindowsDisk(f"PhysicalDrive{index}"))
    return disks


def smartctl_path() -> str | None:
    found = shutil.which("smartctl")
    if found:
        return found
    for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if root:
            candidate = Path(root) / "smartmontools" / "bin" / "smartctl.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def _smartctl_json(command: list[str], timeout: int = 20) -> dict[str, Any] | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        payload = json.loads(result.stdout)
        return payload if isinstance(payload, dict) else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def collect_smart_records(program: str | None = None) -> list[dict[str, Any]]:
    program = program or smartctl_path()
    if not program:
        return []
    scan = _smartctl_json([program, "--scan-open", "--json"])
    devices = scan.get("devices", []) if scan else []
    if not isinstance(devices, list):
        return []
    records: list[dict[str, Any]] = []
    for entry in devices:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        name = entry["name"]
        command = [program, "--all", "--json"]
        if isinstance(entry.get("type"), str) and entry["type"] not in ("auto", ""):
            command.extend(["-d", entry["type"]])
        payload = _smartctl_json([*command, name])
        if payload is None:
            continue
        device = PhysicalDevice(name=name, path=name, sys_path="", major_minor="")
        record = normalize(device, {}, payload, None, [
            {"source": "smartctl", "status": "partial" if payload.get("smartctl", {}).get("exit_status", 0) & 0b111 else "ok"}
        ]).to_dict()
        records.append(record)
    return records


def match_smart_records(
    disks: list[WindowsDisk], records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Match only unambiguous identities; never attach health to the wrong disk."""
    matched: dict[str, dict[str, Any]] = {}
    used_records: set[int] = set()
    for disk in disks:
        serial = _identity(disk.serial)
        if not serial or sum(_identity(item.serial) == serial for item in disks) != 1:
            continue
        candidates = [i for i, record in enumerate(records)
                      if _identity(record.get("identity", {}).get("serial")) == serial]
        if len(candidates) == 1 and candidates[0] not in used_records:
            matched[disk.key] = records[candidates[0]]
            used_records.add(candidates[0])
    for disk in disks:
        if disk.key in matched:
            continue
        model = _identity(disk.model)
        if not model or sum(_identity(item.model) == model for item in disks) != 1:
            continue
        candidates = [i for i, record in enumerate(records)
                      if _identity(record.get("identity", {}).get("model")) == model]
        if len(candidates) == 1 and candidates[0] not in used_records:
            matched[disk.key] = records[candidates[0]]
            used_records.add(candidates[0])
    return matched


def calculate_rates(
    previous: dict[str, tuple[int, int]],
    current: dict[str, tuple[int, int]],
    elapsed: float,
) -> dict[str, tuple[float | None, float | None]]:
    rates: dict[str, tuple[float | None, float | None]] = {}
    for key, (read_bytes, write_bytes) in current.items():
        prior = previous.get(key)
        if prior is None or elapsed <= 0 or read_bytes < prior[0] or write_bytes < prior[1]:
            rates[key] = (None, None)
        else:
            rates[key] = ((read_bytes - prior[0]) / elapsed, (write_bytes - prior[1]) / elapsed)
    return rates
