"""PostToolUse hook: lint the single file Claude just wrote/edited.

Reads the hook JSON from stdin, lints only that file, and never blocks on missing tools.
Exit 2 (with stderr) feeds lint errors back to Claude; exit 0 otherwise.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT_S = 60


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 0, f"lint skipped: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    path = Path(file_path).resolve()
    if not path.is_file():
        return 0

    backend, frontend = root / "autoserve-server", root / "autoserve-client"
    problems: list[str] = []

    if path.suffix == ".py" and backend in path.parents and (backend / "pyproject.toml").exists() and shutil.which("uv"):
        code, out = run(["uv", "run", "--quiet", "ruff", "check", "--fix", str(path)], backend)
        if code != 0:
            problems.append(f"ruff:\n{out}")
        run(["uv", "run", "--quiet", "ruff", "format", str(path)], backend)

    elif path.suffix in {".ts", ".tsx"} and frontend in path.parents and (frontend / "node_modules").exists():
        npx = shutil.which("npx")
        if npx:
            code, out = run([npx, "--no-install", "eslint", "--fix", str(path)], frontend)
            if code != 0:
                problems.append(f"eslint:\n{out}")

    if problems:
        print(f"Lint issues in {path.name}:\n" + "\n\n".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
