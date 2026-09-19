from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.stdout)
        except (json.JSONDecodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None


def available(program: str) -> bool:
    return shutil.which(program) is not None


def run(command: list[str], timeout: int = 15) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(command, completed.returncode, completed.stdout, completed.stderr)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(command, 124, exc.stdout or "", "command timed out")
    except OSError as exc:
        return CommandResult(command, 127, "", str(exc))

