import unittest

from storage_health.collectors import collect_smartctl
from storage_health.command import CommandResult
from storage_health.models import PhysicalDevice


class CollectorTests(unittest.TestCase):
    def test_smartctl_device_error_with_json_is_partial(self) -> None:
        device = PhysicalDevice("sr0", "/dev/sr0", "/sys/devices/sr0", "11:0")

        def runner(command: list[str], timeout: int) -> CommandResult:
            return CommandResult(command, 2, '{"device":{"name":"/dev/sr0"}}', "")

        payload, status = collect_smartctl(device, runner=runner, is_available=lambda _: True)

        self.assertIsNotNone(payload)
        self.assertEqual(status["status"], "partial")

    def test_smartctl_health_bit_does_not_mark_collection_failed(self) -> None:
        device = PhysicalDevice("sda", "/dev/sda", "/sys/devices/sda", "8:0")

        def runner(command: list[str], timeout: int) -> CommandResult:
            return CommandResult(command, 8, '{"smart_status":{"passed":false}}', "")

        _, status = collect_smartctl(device, runner=runner, is_available=lambda _: True)

        self.assertEqual(status["status"], "ok")

    def test_unknown_usb_bridge_uses_scsi_health_fallback(self) -> None:
        device = PhysicalDevice("sdb", "/dev/sdb", "/sys/devices/sdb", "8:16")
        commands = []

        def runner(command: list[str], timeout: int) -> CommandResult:
            commands.append(command)
            if "scsi" in command:
                return CommandResult(command, 4, '{"device":{"protocol":"SCSI"},"smart_status":{"passed":true}}', "")
            return CommandResult(command, 1, '{"smartctl":{"messages":[{"string":"Unknown USB bridge"}]}}', "")

        payload, status = collect_smartctl(device, runner=runner, is_available=lambda _: True)

        self.assertEqual(payload["smart_status"]["passed"], True)
        self.assertEqual(status["status"], "partial")
        self.assertEqual(commands[1], ["smartctl", "--all", "--json", "-d", "scsi", "/dev/sdb"])


if __name__ == "__main__":
    unittest.main()
