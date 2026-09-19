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

## Local dashboard

Save a scan, then start the dashboard as your normal user:

```bash
sudo .venv/bin/storage-health record
.venv/bin/storage-health dashboard
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) on this computer.
Run `record` again whenever you want another point on the graphs. The page
reads newly saved scans when refreshed. Snapshot files are stored under
`~/.local/share/ssd-monitor/` with private file permissions. The dashboard
listens only on `127.0.0.1` and does not show drive serial numbers.

Use `--data-dir PATH` with both commands to choose another snapshot directory.
Use `--port PORT` with `dashboard` if port 8765 is occupied. A single snapshot
shows the current reading; trends appear as more snapshots are recorded.

## Cinnamon panel applet

The Cinnamon applet in `cinnamon/ssd-monitor@local/` uses a fixed-size panel
icon. Click it for live disk read and write rates, SMART status, lifetime
remaining, temperature, error counters, and the age of the latest recorded
snapshot.
Use **Select drive** in its menu to switch between attached drives. USB drives
and additional SSDs appear when Linux exposes them as physical block devices;
the choice is remembered. If a selected drive is unplugged, the icon changes
to a warning and its tooltip says disconnected until another drive is selected.
Some USB enclosures do not pass SMART data through, so read/write rates can be
available while health fields remain unknown.
Use **Temperature units** in the applet menu to choose metric (°C) or imperial
(°F). The choice is remembered and applies to the details menu.
Read/write activity remains in bytes per second in either setting.
Read/write rates refresh every two seconds from Linux disk counters. SMART
details come from the private snapshots made by `storage-health record`.
The tooltip marks a snapshot stale after 24 hours.

To install it for the current user, copy the `ssd-monitor@local` folder into
`~/.local/share/cinnamon/applets/`, then add **SSD Monitor** to the panel in
Cinnamon's Applets settings. Run `sudo .venv/bin/storage-health record` to
refresh the SMART details. The panel applet itself does not require root.

The collector's normalized JSON snapshots are separate from the Cinnamon UI,
which lets the Windows tray companion use the same health fields.

## Windows system tray

The Windows tray companion lives in `src/storage_health/windows_tray.py`. Its
icon stays a fixed size; right-click it for live per-disk read/write rates,
SMART health, temperature, wear, error counts, drive selection, and Celsius or
Fahrenheit. It remembers the selected drive and units. Physical disk identity
comes directly from the Windows storage API. SMART readings come from
`smartctl` when it is installed and can access the drive. Missing or ambiguous
SMART data is shown as unknown rather than assigned to the wrong disk.

On the Windows computer, from PowerShell in a clone of this repository:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[windows]"
.\.venv\Scripts\ssd-monitor-tray.exe
```

The tray launcher has no console window. Install smartmontools separately for
SMART health; live read/write rates work without it. If rates are unavailable,
Windows may need its physical disk performance counters enabled and a reboot.
Run the tray once on the Windows computer before relying on its health display:
Windows permissions, USB bridges, and disk counter names vary by system.

Run the test suite without additional test dependencies:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
