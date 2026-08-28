from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def require_executable(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    if sys.platform == "win32":
        resolved = shutil.which(f"{name}.cmd")
        if resolved:
            return resolved
    raise SystemExit(f"required executable is missing: {name}")


def main() -> None:
    node = require_executable("node")
    npm = require_executable("npm")

    run([sys.executable, "-m", "compileall", "-q", "dashboard"])
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "dashboard/tests",
            "-p",
            "test_*.py",
            "-v",
        ]
    )
    run([npm, "run", "test:dashboard"])

    javascript_paths = sorted((ROOT / "docs" / "dashboard").glob("*.js"))
    javascript_paths.extend([ROOT / "dashboard" / "live-core.js", ROOT / "api" / "dashboard-live.js"])
    for path in javascript_paths:
        run([node, "--check", str(path.relative_to(ROOT))])

    print("dashboard contract validation PASS")


if __name__ == "__main__":
    main()
