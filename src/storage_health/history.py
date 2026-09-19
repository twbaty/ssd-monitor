from __future__ import annotations

import json
import os
import pwd
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_data_dir() -> Path:
    owner_uid = os.environ.get("SUDO_UID") or os.environ.get("PKEXEC_UID")
    home = Path(pwd.getpwuid(int(owner_uid)).pw_dir) if owner_uid and owner_uid.isdigit() else Path.home()
    return home / ".local" / "share" / "ssd-monitor"


def save_snapshot(records: list[dict[str, Any]], data_dir: Path) -> Path:
    owner_uid = os.environ.get("SUDO_UID") or os.environ.get("PKEXEC_UID")
    if os.geteuid() == 0 and owner_uid and owner_uid.isdigit() and data_dir == default_data_dir():
        uid = int(owner_uid)
        gid = pwd.getpwuid(uid).pw_gid
        home = Path(pwd.getpwuid(uid).pw_dir)
        for parent in (home / ".local", home / ".local" / "share"):
            if not parent.exists():
                parent.mkdir(mode=0o700)
                os.chown(parent, uid, gid)
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    data_dir.chmod(0o700)
    if os.geteuid() == 0 and owner_uid and owner_uid.isdigit():
        uid = int(owner_uid)
        os.chown(data_dir, uid, pwd.getpwuid(uid).pw_gid)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = data_dir / f"{timestamp}.json"
    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=data_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(records, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        if os.geteuid() == 0 and owner_uid and owner_uid.isdigit():
            uid = int(owner_uid)
            os.chown(temporary, uid, pwd.getpwuid(uid).pw_gid)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def load_snapshots(data_dir: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    if not data_dir.is_dir():
        return snapshots
    for path in sorted(data_dir.glob("*.json"))[-365:]:
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            device = record.get("device") or {}
            identity = record.get("identity") or {}
            health = record.get("health") or {}
            errors = record.get("errors") or {}
            temperature = record.get("temperature") or {}
            usage = record.get("usage") or {}
            collection = record.get("collection") or {}
            snapshots.append({
                "timestamp": collection.get("timestamp_utc") or path.stem,
                "device": device.get("path"),
                "model": identity.get("model"),
                "smart_passed": health.get("smart_passed"),
                "lifetime_remaining_percent": health.get("lifetime_remaining_percent"),
                "temperature_celsius": temperature.get("celsius"),
                "power_on_hours": usage.get("power_on_hours"),
                "reallocated_nand_blocks": errors.get("reallocated_nand_blocks"),
                "reported_uncorrectable_errors": errors.get("reported_uncorrectable_errors"),
                "interface_crc_errors": errors.get("interface_crc_errors"),
            })
    return sorted(snapshots, key=lambda item: item["timestamp"])
