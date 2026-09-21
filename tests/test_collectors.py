import unittest
from pathlib import Path

from storage_health.collectors import collect_smartctl, resolve_smartctl
from storage_health.command import CommandResult
from storage_health.models import PhysicalDevice


class CollectorTests(unittest.TestCase):
    def test_finds_standard_windows_smartctl_install(self) -> None:
        expected = Path("C:/Program Files/smartmontools/bin/smartctl.exe")

        resolved = resolve_smartctl(
            is_available=lambda _: False,
            environ={"ProgramFiles": "C:/Program Files"},
            path_exists=lambda path: path == expected,
        )

        self.assertEqual(resolved, str(expected))

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


if __name__ == "__main__":
    unittest.main()
