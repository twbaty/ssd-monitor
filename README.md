# SSD Monitor

Cross-platform storage health monitoring focused on defensible, normalized telemetry from physical storage devices. Linux and Windows discovery are implemented.

## First milestone

`storage-health scan --json` enumerates each physical storage device exactly once and emits one normalized JSON record per device.

Telemetry may come from:

- `smartctl`
- `nvme-cli`
- `/sys`
- `udev`
- Windows CIM / Storage Management

Missing or unsupported attributes are represented explicitly and are never guessed.

## Status

Linux telemetry proof of concept implemented.

## Run it

Requires Python 3.10 or newer. Install `smartmontools` (and `nvme-cli` on Linux)
for full telemetry; the command still emits explicit partial records when an
optional tool is missing or access is denied.

```bash
mkdir -p ~/code
cd ~/code
git clone https://github.com/twbaty/ssd-monitor.git
cd ssd-monitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
sudo .venv/bin/storage-health scan --json
```

Run the test suite without additional test dependencies:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
