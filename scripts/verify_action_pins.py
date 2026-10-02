from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path('.github/workflows')
USES_RE = re.compile(r'^\s*(?:-\s*)?uses:\s*([^\s#]+)')
FULL_SHA_RE = re.compile(r'^[0-9a-fA-F]{40}$')


def main() -> int:
    failures: list[str] = []
    checked = 0
    for path in sorted(WORKFLOWS.glob('*.yml')) + sorted(WORKFLOWS.glob('*.yaml')):
        for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            match = USES_RE.match(line)
            if not match:
                continue
            target = match.group(1)
            if target.startswith('./') or target.startswith('docker://'):
                continue
            if '@' not in target:
                failures.append(f'{path}:{line_no}: action has no ref: {target}')
                continue
            action, ref = target.rsplit('@', 1)
            if action.startswith('${{'):
                continue
            checked += 1
            if not FULL_SHA_RE.fullmatch(ref):
                failures.append(
                    f'{path}:{line_no}: external action is not pinned to a full commit SHA: {target}'
                )
    if failures:
        print('\n'.join(failures))
        return 1
    print(f'verified {checked} external action references are pinned to full commit SHAs')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
