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

Linux telemetry proof of concept implemented.

## Run it

Requires Python 3.10 or newer. Install `smartmontools` and `nvme-cli` for full
telemetry; the command still emits explicit partial records when either tool is
missing or access is denied.

```bash
python -m pip install .
sudo storage-health scan --json
```

Run the test suite without additional test dependencies:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
