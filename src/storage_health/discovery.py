from __future__ import annotations

import os
from pathlib import Path

from .models import PhysicalDevice


_EXCLUDED_PREFIXES = ("loop", "ram", "zram", "fd", "sr")


def _read(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return value or None


def discover_linux(sys_block: Path = Path("/sys/class/block")) -> list[PhysicalDevice]:
    """Enumerate whole physical block devices once, keyed by kernel major:minor."""
    devices: dict[str, PhysicalDevice] = {}
    try:
        entries = sorted(sys_block.iterdir(), key=lambda item: item.name)
    except OSError:
        return []

    for entry in entries:
        name = entry.name
        if name.startswith(_EXCLUDED_PREFIXES) or (entry / "partition").exists():
            continue

        resolved = Path(os.path.realpath(entry))
        # Device-mapper, MD, and other virtual block devices have no physical
        # device node beneath /sys/devices. Report their component disks instead.
        if "/virtual/" in str(resolved):
            continue

        major_minor = _read(entry / "dev")
        if not major_minor:
            continue

        transport = _read(entry / "device" / "transport")
        if name.startswith("nvme"):
            transport = "nvme"

        devices.setdefault(
            major_minor,
            PhysicalDevice(
                name=name,
                path=f"/dev/{name}",
                sys_path=str(resolved),
                major_minor=major_minor,
                transport=transport,
            ),
        )

    return sorted(devices.values(), key=lambda device: device.path)
