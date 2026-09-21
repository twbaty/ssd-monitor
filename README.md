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

Requires Python 3.10 or newer. Windows uses native CIM, Storage Management, and
storage reliability counters. Linux uses sysfs for native discovery.
`smartmontools` and Linux `nvme-cli` are optional enrichment/fallback providers;
the application does not require either tool to run.

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
