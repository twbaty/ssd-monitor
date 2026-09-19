import tempfile
import unittest
from pathlib import Path

from storage_health.discovery import discover_linux


class DiscoveryTests(unittest.TestCase):
    def test_discovers_whole_physical_devices_and_skips_partitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            block = tmp_path / "block"
            block.mkdir()

            physical = tmp_path / "devices" / "pci0000:00" / "block" / "sda"
            physical.mkdir(parents=True)
            (physical / "dev").write_text("8:0\n")
            (block / "sda").symlink_to(physical, target_is_directory=True)

            partition = physical / "sda1"
            partition.mkdir()
            (partition / "partition").write_text("1\n")
            (partition / "dev").write_text("8:1\n")
            (block / "sda1").symlink_to(partition, target_is_directory=True)

            loop = tmp_path / "devices" / "virtual" / "block" / "loop0"
            loop.mkdir(parents=True)
            (loop / "dev").write_text("7:0\n")
            (block / "loop0").symlink_to(loop, target_is_directory=True)

            optical = tmp_path / "devices" / "pci0000:00" / "block" / "sr0"
            optical.mkdir(parents=True)
            (optical / "dev").write_text("11:0\n")
            (block / "sr0").symlink_to(optical, target_is_directory=True)

            devices = discover_linux(block)

            self.assertEqual(
                [(device.name, device.major_minor) for device in devices],
                [("sda", "8:0")],
            )


if __name__ == "__main__":
    unittest.main()
