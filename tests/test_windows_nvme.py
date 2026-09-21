import unittest

from storage_health.windows_nvme import parse_nvme_health_log


class WindowsNvmeTests(unittest.TestCase):
    def test_parses_nvme_health_log(self) -> None:
        data = bytearray(512)
        data[0] = 0
        data[1:3] = (332).to_bytes(2, "little")
        data[3] = 100
        data[4] = 10
        data[5] = 4
        values = {
            32: 79_533_659,
            48: 73_892_930,
            112: 108,
            128: 22_156,
            144: 44,
            160: 0,
            176: 0,
        }
        for offset, value in values.items():
            data[offset : offset + 16] = value.to_bytes(16, "little")

        parsed = parse_nvme_health_log(bytes(data))

        self.assertEqual(parsed["temperature"], 332)
        self.assertEqual(parsed["avail_spare"], 100)
        self.assertEqual(parsed["percentage_used"], 4)
        self.assertEqual(parsed["data_units_read"], 79_533_659)
        self.assertEqual(parsed["power_on_hours"], 22_156)
        self.assertEqual(parsed["unsafe_shutdowns"], 44)
        self.assertEqual(parsed["media_errors"], 0)


if __name__ == "__main__":
    unittest.main()
