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

For Crucial BX500 drives, the scan also reports lifetime remaining from ATA
SMART attribute 202 and raw counts for reallocated NAND blocks (5), reported
uncorrectable errors (187), and SATA interface CRC errors (199). These fields
remain `null` for drives without this supported mapping. The lifetime value is
derived from attribute 202's raw percent used, as documented by smartmontools.

## Status

Linux telemetry proof of concept implemented.

## Run it

Requires Python 3.10 or newer. Install `smartmontools` and `nvme-cli` for full
telemetry; the command still emits explicit partial records when either tool is
missing or access is denied.

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
