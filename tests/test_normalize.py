import unittest

from storage_health.models import PhysicalDevice
from storage_health.normalize import normalize


class NormalizationTests(unittest.TestCase):
    def test_normalizes_nvme_without_inventing_missing_values(self) -> None:
        device = PhysicalDevice(
            "nvme0n1", "/dev/nvme0n1", "/sys/devices/nvme0n1", "259:0", "nvme"
        )
        record = normalize(
            device,
            {
                "model": "Example NVMe",
                "serial": "ABC123",
                "size_bytes": 1000,
                "rotational": False,
            },
            None,
            {"temperature": 304, "percentage_used": 7, "media_errors": 0},
            [{"source": "nvme-cli", "status": "ok"}],
        ).to_dict()

        self.assertEqual(record["identity"]["model"], "Example NVMe")
        self.assertEqual(record["temperature"]["celsius"], 30.85)
        self.assertEqual(record["health"]["percentage_used"], 7)
        self.assertIsNone(record["health"]["smart_passed"])
        self.assertIsNone(record["usage"]["power_on_hours"])

    def test_prefers_smart_identity_and_temperature(self) -> None:
        device = PhysicalDevice("sda", "/dev/sda", "/sys/devices/sda", "8:0")
        record = normalize(
            device,
            {"model": "sysfs model", "size_bytes": 1000},
            {
                "model_name": "SMART model",
                "serial_number": "SERIAL",
                "device": {"protocol": "ATA"},
                "smart_status": {"passed": True},
                "temperature": {"current": 33},
                "power_on_time": {"hours": 120},
            },
            None,
            [{"source": "smartctl", "status": "ok"}],
        ).to_dict()

        self.assertEqual(record["identity"]["model"], "SMART model")
        self.assertEqual(record["device"]["transport"], "ata")
        self.assertTrue(record["health"]["smart_passed"])
        self.assertEqual(record["temperature"]["celsius"], 33)
        self.assertEqual(record["usage"]["power_on_hours"], 120)

    def test_bx500_vendor_attributes(self) -> None:
        device = PhysicalDevice("sda", "/dev/sda", "/sys/devices/sda", "8:0")
        smart = {
            "model_name": "CT480BX500SSD1",
            "ata_smart_attributes": {"table": [
                {"id": 5, "raw": {"value": 0}},
                {"id": 187, "raw": {"value": 0}},
                {"id": 199, "raw": {"value": 0}},
                {"id": 202, "name": "Percent_Lifetime_Remain", "value": 95, "raw": {"value": 5}},
            ]},
        }
        record = normalize(device, {}, smart, None, []).to_dict()

        self.assertEqual(record["health"]["lifetime_remaining_percent"], 95)
        self.assertEqual(record["errors"]["reallocated_nand_blocks"], 0)
        self.assertEqual(record["errors"]["reported_uncorrectable_errors"], 0)
        self.assertEqual(record["errors"]["interface_crc_errors"], 0)

        smart["model_name"] = "Other SSD"
        unrelated = normalize(device, {}, smart, None, []).to_dict()
        self.assertIsNone(unrelated["health"]["lifetime_remaining_percent"])
        self.assertIsNone(unrelated["errors"]["reallocated_nand_blocks"])

    def test_scsi_zero_temperature_is_not_reported(self) -> None:
        device = PhysicalDevice("sdb", "/dev/sdb", "/sys/devices/sdb", "8:16")
        smart = {
            "device": {"protocol": "SCSI"},
            "smart_status": {"passed": True},
            "temperature": {"current": 0},
        }
        record = normalize(device, {}, smart, None, []).to_dict()

        self.assertTrue(record["health"]["smart_passed"])
        self.assertIsNone(record["temperature"]["celsius"])


if __name__ == "__main__":
    unittest.main()
