from __future__ import annotations

import subprocess
import sys
import time


MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 3


def main() -> int:
    command = [sys.executable, "dashboard/tests/dashboard_repository_operations_production_e2e.py"]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = subprocess.run(command, text=True)
        if result.returncode == 0:
            if attempt > 1:
                print(f"production browser E2E recovered on bounded retry {attempt}/{MAX_ATTEMPTS}")
            return 0
        if attempt == MAX_ATTEMPTS:
            return result.returncode
        print(
            f"production browser E2E attempt {attempt}/{MAX_ATTEMPTS} failed; "
            f"retrying in {RETRY_DELAY_SECONDS}s",
            file=sys.stderr,
        )
        time.sleep(RETRY_DELAY_SECONDS)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
