# SSD Monitor

Cross-platform storage health monitoring focused on defensible, normalized telemetry from physical storage devices.

## First milestone

`storage-health scan --json` enumerates each physical storage device exactly once and emits one normalized JSON record per device.

Linux telemetry may come from:

- `smartctl`
- `nvme-cli`
- `/sys`
- `udev`

Missing or unsupported attributes are represented explicitly and are never guessed.

## Status

Initial project setup. Implementation begins with the Linux telemetry proof of concept.
