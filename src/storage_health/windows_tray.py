from __future__ import annotations

import json
import os
import platform
import re
import threading
import time
from pathlib import Path
from typing import Any

from .windows_telemetry import (
    WindowsDisk, calculate_rates, collect_smart_records, discover_windows_disks,
    match_smart_records, smartctl_path,
)


def _rate(value: float | None) -> str:
    if value is None:
        return "—"
    for unit, divisor in (("GiB/s", 1024 ** 3), ("MiB/s", 1024 ** 2), ("KiB/s", 1024)):
        if value >= divisor:
            return f"{value / divisor:.1f} {unit}"
    return f"{value:.0f} B/s"


def _temperature(value: Any, unit: str) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{value * 9 / 5 + 32:.1f} °F" if unit == "imperial" else f"{value} °C"


def _value(value: Any, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def _preferences_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return base / "SSDMonitor" / "settings.json"


class TrayApp:
    def __init__(self, psutil: Any, pystray: Any, image_module: Any, draw_module: Any) -> None:
        self.psutil = psutil
        self.pystray = pystray
        self.image_module = image_module
        self.draw_module = draw_module
        self.lock = threading.Lock()
        self.menu_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.refresh_event = threading.Event()
        self.disks: list[WindowsDisk] = []
        self.health: dict[str, dict[str, Any]] = {}
        self.rates: dict[str, tuple[float | None, float | None]] = {}
        self.io_keys: set[str] = set()
        self.smartctl_available = smartctl_path() is not None
        try:
            saved = json.loads(_preferences_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        self.selected = saved.get("selected") if isinstance(saved.get("selected"), str) else None
        self.unit = "imperial" if saved.get("unit") == "imperial" else "metric"
        self.icon: Any = None

    def _save_preferences(self) -> None:
        path = _preferences_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"selected": self.selected, "unit": self.unit}), encoding="utf-8")

    def _icon_image(self, warning: bool = False) -> Any:
        image = self.image_module.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = self.draw_module.Draw(image)
        color = "#e4a343" if warning else "#58c9b2"
        draw.rounded_rectangle((9, 5, 55, 59), radius=9, fill="#142337", outline=color, width=4)
        draw.line((17, 19, 47, 19), fill=color, width=4)
        draw.ellipse((39, 43, 47, 51), fill=color)
        return image

    def _menu(self) -> Any:
        Menu = self.pystray.Menu
        Item = self.pystray.MenuItem
        disabled = lambda icon, item: None
        with self.lock:
            disk_map = {disk.key: disk for disk in self.disks}
            keys = sorted(set(disk_map) | self.io_keys,
                          key=lambda value: int(re.search(r"\d+$", value).group())
                          if re.search(r"\d+$", value) else -1)
            if self.selected is None and keys:
                self.selected = keys[0]
            selected = self.selected
            disk = disk_map.get(selected)
            health = self.health.get(selected, {})
            identity = health.get("identity") or {}
            status = health.get("health") or {}
            errors = health.get("errors") or {}
            temperature = (health.get("temperature") or {}).get("celsius")
            read, write = self.rates.get(selected, (None, None))
            unit = self.unit
            smartctl_available = self.smartctl_available
        drive_name = disk.model if disk and disk.model else identity.get("model") or selected or "No drive"
        drive_items = [Item(f"{'✓ ' if key == selected else ''}{key} · {disk_map[key].model if key in disk_map and disk_map[key].model else 'Drive'}",
                            lambda icon, item, key=key: self._select(key)) for key in keys]
        if not drive_items:
            drive_items = [Item("No physical drives found", disabled, enabled=False)]
        smart = status.get("smart_passed")
        smart_text = "passed" if smart is True else "warning" if smart is False else "unknown"
        if not smartctl_available:
            smart_text += " (smartctl not installed)"
        return Menu(
            Item(f"{drive_name} ({selected or 'none'})", disabled, enabled=False),
            Item(f"Read: {_rate(read)}", disabled, enabled=False),
            Item(f"Write: {_rate(write)}", disabled, enabled=False),
            Menu.SEPARATOR,
            Item(f"SMART: {smart_text}", disabled, enabled=False),
            Item(f"Lifetime remaining: {_value(status.get('lifetime_remaining_percent'), '%')}", disabled, enabled=False),
            Item(f"Temperature: {_temperature(temperature, unit)}", disabled, enabled=False),
            Item(f"Reallocated NAND blocks: {_value(errors.get('reallocated_nand_blocks'))}", disabled, enabled=False),
            Item(f"Uncorrectable errors: {_value(errors.get('reported_uncorrectable_errors'))}", disabled, enabled=False),
            Item(f"Interface CRC errors: {_value(errors.get('interface_crc_errors'))}", disabled, enabled=False),
            Menu.SEPARATOR,
            Item("Select drive", Menu(*drive_items)),
            Item("Temperature units", Menu(
                Item(f"{'✓ ' if unit == 'metric' else ''}Metric (°C)", lambda icon, item: self._set_unit("metric")),
                Item(f"{'✓ ' if unit == 'imperial' else ''}Imperial (°F)", lambda icon, item: self._set_unit("imperial")),
            )),
            Item("Refresh SMART", lambda icon, item: self.refresh_event.set()),
            Item("Quit SSD Monitor", lambda icon, item: self._quit()),
        )

    def _update_menu(self) -> None:
        if self.icon is None:
            return
        with self.menu_lock:
            self.icon.menu = self._menu()
            with self.lock:
                selected = self.selected
                warning = (self.health.get(selected, {}).get("health") or {}).get("smart_passed") is False
            self.icon.icon = self._icon_image(warning)
            self.icon.title = f"SSD Monitor · {selected or 'no drive'}"
            self.icon.update_menu()

    def _select(self, key: str) -> None:
        with self.lock:
            self.selected = key
        self._save_preferences()
        self._update_menu()

    def _set_unit(self, unit: str) -> None:
        with self.lock:
            self.unit = unit
        self._save_preferences()
        self._update_menu()

    def _quit(self) -> None:
        self.stop_event.set()
        self.refresh_event.set()
        if self.icon is not None:
            self.icon.stop()

    def _poll_io(self) -> None:
        previous: dict[str, tuple[int, int]] = {}
        prior_time = 0.0
        while not self.stop_event.is_set():
            try:
                raw = self.psutil.disk_io_counters(perdisk=True) or {}
                current = {f"PhysicalDrive{int(match.group(1))}": (counter.read_bytes, counter.write_bytes)
                           for key, counter in raw.items()
                           if (match := re.fullmatch(r"PhysicalDrive(\d+)", key, re.IGNORECASE))}
            except (OSError, RuntimeError, ValueError):
                current = {}
            now = time.monotonic()
            rates = calculate_rates(previous, current, now - prior_time)
            with self.lock:
                self.rates = rates
                self.io_keys = set(current)
                if self.selected is None and current:
                    self.selected = sorted(current)[0]
            self._update_menu()
            previous, prior_time = current, now
            self.stop_event.wait(2)

    def _poll_health(self) -> None:
        while not self.stop_event.is_set():
            with self.lock:
                io_keys = tuple(self.io_keys)
            disks = discover_windows_disks(io_keys)
            records = collect_smart_records()
            matched = match_smart_records(disks, records)
            with self.lock:
                self.disks = disks
                self.health = matched
                self.smartctl_available = smartctl_path() is not None
                if self.selected is None and disks:
                    self.selected = disks[0].key
            self._update_menu()
            self.refresh_event.wait(600)
            self.refresh_event.clear()

    def _setup(self, icon: Any) -> None:
        self.icon = icon
        icon.visible = True
        threading.Thread(target=self._poll_io, daemon=True).start()
        threading.Thread(target=self._poll_health, daemon=True).start()

    def run(self) -> None:
        self.icon = self.pystray.Icon("ssd-monitor", self._icon_image(), "SSD Monitor", menu=self._menu())
        self.icon.run(setup=self._setup)


def main() -> int:
    if platform.system() != "Windows":
        print("SSD Monitor tray runs on Windows. Use the Cinnamon applet on Linux.")
        return 2
    try:
        import psutil
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as error:
        print(f"Missing Windows tray dependency: {error}. Install with: pip install 'storage-health[windows]'")
        return 2
    TrayApp(psutil, pystray, Image, ImageDraw).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
