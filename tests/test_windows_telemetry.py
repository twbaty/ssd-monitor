import unittest
import struct
from unittest.mock import patch

from storage_health.windows_telemetry import (
    WindowsDisk, calculate_rates, collect_smart_records, discover_windows_disks,
    match_smart_records, parse_storage_descriptor,
)


class WindowsTelemetryTests(unittest.TestCase):
    def test_parse_direct_storage_descriptor(self) -> None:
        vendor, product, serial = b"Crucial\0", b"BX500\0", b"SERIAL A\0"
        data = bytearray(36 + len(vendor) + len(product) + len(serial))
        product_offset = 36 + len(vendor)
        serial_offset = product_offset + len(product)
        struct.pack_into("<IIBBBBIIIIII", data, 0, 36, len(data), 0, 0, 0, 0,
                         36, product_offset, 0, serial_offset, 7, 0)
        data[36:] = vendor + product + serial
        self.assertEqual(parse_storage_descriptor(data, 2),
                         WindowsDisk("PhysicalDrive2", "Crucial BX500", "SERIAL A"))
        self.assertIsNone(parse_storage_descriptor(b"short", 2))

    def test_discovery_uses_io_keys_when_direct_query_is_denied(self) -> None:
        with patch("storage_health.windows_telemetry.query_physical_drive", return_value=None):
            disks = discover_windows_disks(["PhysicalDrive0", "PhysicalDrive18"])
        self.assertEqual([disk.key for disk in disks], ["PhysicalDrive0", "PhysicalDrive18"])

    def test_match_serial_first_and_unique_model_only(self) -> None:
        disks = [WindowsDisk("PhysicalDrive0", "Same Model", "SERIAL A"),
                 WindowsDisk("PhysicalDrive1", "Same Model", "SERIAL B"),
                 WindowsDisk("PhysicalDrive2", "Unique Model", None)]
        records = [
            {"identity": {"model": "Same Model", "serial": "SERIALB"}},
            {"identity": {"model": "Same Model", "serial": "SERIALA"}},
            {"identity": {"model": "Unique Model", "serial": None}},
        ]
        matched = match_smart_records(disks, records)
        self.assertIs(matched["PhysicalDrive0"], records[1])
        self.assertIs(matched["PhysicalDrive1"], records[0])
        self.assertIs(matched["PhysicalDrive2"], records[2])

        ambiguous = match_smart_records(
            [WindowsDisk("PhysicalDrive0", "Duplicate"), WindowsDisk("PhysicalDrive1", "Duplicate")],
            [{"identity": {"model": "Duplicate"}}],
        )
        self.assertEqual(ambiguous, {})
        duplicate_serial = match_smart_records(
            [WindowsDisk("PhysicalDrive0", serial="BRIDGE"),
             WindowsDisk("PhysicalDrive1", serial="BRIDGE")],
            [{"identity": {"serial": "BRIDGE"}}],
        )
        self.assertEqual(duplicate_serial, {})

    def test_rates_reset_on_missing_or_decreased_counters(self) -> None:
        self.assertEqual(calculate_rates({"PhysicalDrive0": (100, 200)},
                                         {"PhysicalDrive0": (300, 500)}, 2),
                         {"PhysicalDrive0": (100.0, 150.0)})
        self.assertEqual(calculate_rates({"PhysicalDrive0": (300, 500)},
                                         {"PhysicalDrive0": (10, 20)}, 2),
                         {"PhysicalDrive0": (None, None)})

    def test_smart_scan_preserves_device_type_and_normalizes_bx500(self) -> None:
        responses = [
            {"devices": [{"name": "/dev/sda", "type": "sat"}]},
            {"model_name": "CT480BX500SSD1", "serial_number": "EXAMPLE",
             "smart_status": {"passed": True},
             "ata_smart_attributes": {"table": [{"id": 202, "raw": {"value": 5}}]}},
        ]
        with patch("storage_health.windows_telemetry._smartctl_json", side_effect=responses) as run:
            records = collect_smart_records("smartctl.exe")
        self.assertEqual(run.call_args_list[1].args[0],
                         ["smartctl.exe", "--all", "--json", "-d", "sat", "/dev/sda"])
        self.assertEqual(records[0]["health"]["lifetime_remaining_percent"], 95)


if __name__ == "__main__":
    unittest.main()
