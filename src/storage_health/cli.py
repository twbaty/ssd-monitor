from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

from .dashboard import serve
from .history import default_data_dir, save_snapshot
from .scanner import scan_linux


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storage-health")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="scan physical storage devices")
    scan.add_argument("--json", action="store_true", help="emit normalized JSON")
    record = subparsers.add_parser("record", help="save a scan for the dashboard")
    record.add_argument("--data-dir", type=Path, default=default_data_dir())
    dashboard = subparsers.add_parser("dashboard", help="open a local dashboard server")
    dashboard.add_argument("--data-dir", type=Path, default=default_data_dir())
    dashboard.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if platform.system() != "Linux":
        print("storage-health: this proof of concept currently supports Linux", file=sys.stderr)
        return 2

    if args.command == "dashboard":
        serve(args.data_dir, args.port)
        return 0

    records = [record.to_dict() for record in scan_linux()]
    if args.command == "record":
        path = save_snapshot(records, args.data_dir)
        print(f"Saved {len(records)} device(s) to {path}")
        return 0
    if args.json:
        print(json.dumps(records, indent=2, sort_keys=True))
    else:
        for record in records:
            device = record["device"]
            identity = record["identity"]
            health = record["health"]
            print(f"{device['path']}: {identity['model'] or 'unknown'} smart_passed={health['smart_passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
