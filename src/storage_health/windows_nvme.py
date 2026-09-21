from __future__ import annotations

import ctypes
import os
import struct
from ctypes import wintypes
from typing import Any


IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
STORAGE_DEVICE_PROTOCOL_SPECIFIC_PROPERTY = 50
PROPERTY_STANDARD_QUERY = 0
PROTOCOL_TYPE_NVME = 3
NVME_DATA_TYPE_LOG_PAGE = 2
NVME_HEALTH_LOG_PAGE = 2
NVME_HEALTH_LOG_SIZE = 512
PROTOCOL_DATA_SIZE = 40
QUERY_HEADER_SIZE = 8


def parse_nvme_health_log(data: bytes) -> dict[str, Any]:
    if len(data) < NVME_HEALTH_LOG_SIZE:
        raise ValueError("NVMe health log is shorter than 512 bytes")

    def uint128(offset: int) -> int:
        return int.from_bytes(data[offset : offset + 16], "little")

    temperature = struct.unpack_from("<H", data, 1)[0]
    return {
        "critical_warning": data[0],
        "temperature": temperature or None,
        "avail_spare": data[3],
        "spare_thresh": data[4],
        "percentage_used": data[5],
        "data_units_read": uint128(32),
        "data_units_written": uint128(48),
        "host_read_commands": uint128(64),
        "host_write_commands": uint128(80),
        "controller_busy_time": uint128(96),
        "power_cycles": uint128(112),
        "power_on_hours": uint128(128),
        "unsafe_shutdowns": uint128(144),
        "media_errors": uint128(160),
        "error_log_entries": uint128(176),
    }


def query_nvme_health(device_path: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if os.name != "nt":
        return None, {"source": "windows-nvme", "status": "unsupported_on_platform"}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    device_io_control = kernel32.DeviceIoControl
    device_io_control.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    device_io_control.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        device_path,
        0,
        0x00000001 | 0x00000002,
        None,
        3,
        0,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        error = ctypes.get_last_error()
        return None, {"source": "windows-nvme", "status": "error", "winerror": error}

    buffer_size = QUERY_HEADER_SIZE + PROTOCOL_DATA_SIZE + NVME_HEALTH_LOG_SIZE
    buffer = ctypes.create_string_buffer(buffer_size)
    struct.pack_into(
        "<IIIIIIIIIIII",
        buffer,
        0,
        STORAGE_DEVICE_PROTOCOL_SPECIFIC_PROPERTY,
        PROPERTY_STANDARD_QUERY,
        PROTOCOL_TYPE_NVME,
        NVME_DATA_TYPE_LOG_PAGE,
        NVME_HEALTH_LOG_PAGE,
        0,
        PROTOCOL_DATA_SIZE,
        NVME_HEALTH_LOG_SIZE,
        0,
        0,
        0,
        0,
    )
    returned = wintypes.DWORD()
    try:
        success = device_io_control(
            handle,
            IOCTL_STORAGE_QUERY_PROPERTY,
            buffer,
            buffer_size,
            buffer,
            buffer_size,
            ctypes.byref(returned),
            None,
        )
        if not success:
            error = ctypes.get_last_error()
            return None, {"source": "windows-nvme", "status": "error", "winerror": error}

        data_offset = struct.unpack_from("<I", buffer, QUERY_HEADER_SIZE + 16)[0]
        data_length = struct.unpack_from("<I", buffer, QUERY_HEADER_SIZE + 20)[0]
        start = QUERY_HEADER_SIZE + data_offset
        if data_length < NVME_HEALTH_LOG_SIZE or start + NVME_HEALTH_LOG_SIZE > returned.value:
            return None, {
                "source": "windows-nvme",
                "status": "error",
                "message": "invalid protocol data returned by Windows",
            }
        payload = parse_nvme_health_log(buffer.raw[start : start + NVME_HEALTH_LOG_SIZE])
        return payload, {"source": "windows-nvme", "status": "ok"}
    finally:
        close_handle(handle)
