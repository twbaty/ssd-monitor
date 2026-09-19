from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .command import CommandResult, available, run
from .models import PhysicalDevice

Runner = Callable[[list[str], int], CommandResult]


def _read(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return value or None


def collect_sysfs(device: PhysicalDevice) -> dict[str, Any]:
    base = Path("/sys/class/block") / device.name
    sectors = _read(base / "size")
    logical = _read(base / "queue" / "logical_block_size")
    size_bytes = None
    if sectors and logical:
        try:
            size_bytes = int(sectors) * int(logical)
        except ValueError:
            pass

    return {
        "model": _read(base / "device" / "model"),
        "vendor": _read(base / "device" / "vendor"),
        "serial": _read(base / "device" / "serial"),
        "firmware": _read(base / "device" / "rev"),
        "rotational": _as_bool(_read(base / "queue" / "rotational")),
        "size_bytes": size_bytes,
    }


def _as_bool(value: str | None) -> bool | None:
    if value == "1":
        return True
    if value == "0":
        return False
    return None


def collect_smartctl(
    device: PhysicalDevice,
    runner: Runner = run,
    is_available: Callable[[str], bool] = available,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not is_available("smartctl"):
        return None, {"source": "smartctl", "status": "unavailable"}
    result = runner(["smartctl", "--all", "--json", device.path], 20)
    payload = result.json()
    status = "ok" if payload is not None else "error"
    return payload, {
        "source": "smartctl",
        "status": status,
        "exit_code": result.returncode,
        "message": result.stderr.strip() or None,
    }


def collect_nvme(
    device: PhysicalDevice,
    runner: Runner = run,
    is_available: Callable[[str], bool] = available,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if device.transport != "nvme" and not device.name.startswith("nvme"):
        return None, {"source": "nvme-cli", "status": "not_applicable"}
    if not is_available("nvme"):
        return None, {"source": "nvme-cli", "status": "unavailable"}
    result = runner(["nvme", "smart-log", "-o", "json", device.path], 20)
    payload = result.json()
    status = "ok" if payload is not None else "error"
    return payload, {
        "source": "nvme-cli",
        "status": status,
        "exit_code": result.returncode,
        "message": result.stderr.strip() or None,
    }

