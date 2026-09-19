import tempfile
import unittest
from pathlib import Path

from storage_health.history import load_snapshots, save_snapshot


class HistoryTests(unittest.TestCase):
    def test_saves_and_loads_dashboard_readings_without_serial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "history"
            path = save_snapshot([{
                "device": {"path": "/dev/sda"},
                "identity": {"model": "CT480BX500SSD1", "serial": "PRIVATE"},
                "health": {"smart_passed": True, "lifetime_remaining_percent": 95},
                "errors": {"reallocated_nand_blocks": 0},
                "temperature": {"celsius": 40},
                "usage": {"power_on_hours": 9865},
                "collection": {"timestamp_utc": "2026-09-19T18:00:00+00:00"},
            }], data_dir)

            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(data_dir.stat().st_mode & 0o777, 0o700)
            snapshots = load_snapshots(data_dir)
            self.assertEqual(snapshots[0]["lifetime_remaining_percent"], 95)
            self.assertEqual(snapshots[0]["reallocated_nand_blocks"], 0)
            self.assertNotIn("serial", snapshots[0])


if __name__ == "__main__":
    unittest.main()
