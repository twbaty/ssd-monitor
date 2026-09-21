import unittest

from storage_health.windows import parse_windows_disks


class WindowsDiscoveryTests(unittest.TestCase):
    def test_parses_single_windows_disk_record(self) -> None:
        payload = {
            "Index": 0,
            "DeviceID": r"\\.\PHYSICALDRIVE0",
            "Model": "Example SSD",
            "SerialNumber": " SERIAL-1 ",
            "FirmwareRevision": "1.0",
            "InterfaceType": "SCSI",
            "BusType": "NVMe",
            "MediaType": "SSD",
            "Size": 1000000,
            "Status": "OK",
            "HealthStatus": "Healthy",
            "OperationalStatus": ["OK"],
            "Temperature": 42,
            "TemperatureMax": 71,
            "Wear": 4,
            "PowerOnHours": 22156,
            "ReadErrorsTotal": 0,
            "WriteErrorsTotal": 0,
            "StartStopCycleCount": 108,
            "PNPDeviceID": "PCI\\EXAMPLE",
        }

        disks = parse_windows_disks(payload)

        self.assertEqual(len(disks), 1)
        device, native, smart_path = disks[0]
        self.assertEqual(device.stable_id, "windows:0")
        self.assertEqual(device.path, r"\\.\PHYSICALDRIVE0")
        self.assertEqual(device.transport, "nvme")
        self.assertEqual(native["serial"], "SERIAL-1")
        self.assertFalse(native["rotational"])
        self.assertEqual(native["native_status"]["health"], "Healthy")
        self.assertEqual(native["native_status"]["operational"], ["OK"])
        self.assertEqual(native["temperature_celsius"], 42)
        self.assertEqual(native["percentage_used"], 4)
        self.assertEqual(native["power_on_hours"], 22156)
        self.assertEqual(native["read_errors_total"], 0)
        self.assertEqual(native["start_stop_cycles"], 108)
        self.assertEqual(smart_path, "/dev/pd0")

    def test_normalizes_single_operational_status_to_list(self) -> None:
        payload = {
            "Index": 1,
            "DeviceID": r"\\.\PHYSICALDRIVE1",
            "OperationalStatus": "OK",
        }

        _, native, _ = parse_windows_disks(payload)[0]

        self.assertEqual(native["native_status"]["operational"], ["OK"])


if __name__ == "__main__":
    unittest.main()
