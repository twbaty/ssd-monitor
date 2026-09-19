from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence

from .scanner import scan_linux


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storage-health")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="scan physical storage devices")
    scan.add_argument("--json", action="store_true", help="emit normalized JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "scan":
        return 2
    if platform.system() != "Linux":
        print("storage-health: this proof of concept currently supports Linux", file=sys.stderr)
        return 2

    records = [record.to_dict() for record in scan_linux()]
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

