from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "openclaw-autonomous-worker"
    / "supervisor.py"
)
INSTALLER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "openclaw-autonomous-worker"
    / "install-systemd.sh"
)
spec = importlib.util.spec_from_file_location("openclaw_autonomous_supervisor", MODULE_PATH)
assert spec and spec.loader
worker = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = worker
spec.loader.exec_module(worker)


def candidate(repo: str = "KAFKA2306/demo", number: int = 7, created: str = "2026-01-01T00:00:00Z"):
    return worker.Candidate(
        repo=repo,
        repo_path=Path("/tmp/demo"),
        number=number,
        title="demo",
        url=f"https://github.com/{repo}/issues/{number}",
        created_at=created,
        updated_at="2026-01-02T00:00:00Z",
        labels=(),
    )


def test_parse_remote_https_and_ssh():
    assert worker.parse_remote("https://github.com/KAFKA2306/demo.git") == "KAFKA2306/demo"
    assert worker.parse_remote("git@github.com:KAFKA2306/demo.git") == "KAFKA2306/demo"
    assert worker.parse_remote("https://example.com/KAFKA2306/demo.git") is None


def test_task_id_is_stable_and_repo_scoped():
    a = worker.stable_task_id("KAFKA2306/demo", 7)
    b = worker.stable_task_id("KAFKA2306/demo", 7)
    c = worker.stable_task_id("KAFKA2306/other", 7)
    assert a == b
    assert a != c


def test_choose_candidate_is_deterministic_oldest_first():
    newer = candidate(number=8, created="2026-02-01T00:00:00Z")
    older = candidate(number=9, created="2026-01-01T00:00:00Z")
    chosen = worker.choose_candidate([newer, older], {"tasks": {}})
    assert chosen == older


def test_terminal_task_is_skipped_until_issue_changes():
    item = candidate()
    state = {
        "tasks": {
            item.task_id: {
                "status": "merged",
                "source_updated_at": item.updated_at,
            }
        }
    }
    assert worker.choose_candidate([item], state) is None

    changed = worker.Candidate(
        **{**item.__dict__, "updated_at": "2026-01-03T00:00:00Z"}
    )
    assert worker.choose_candidate([changed], state) == changed


def test_docs_only_requires_nonempty_and_doc_suffixes():
    assert worker.docs_only(["README.md", "docs/guide.rst"])
    assert not worker.docs_only([])
    assert not worker.docs_only(["README.md", "src/main.py"])


def test_installer_does_not_dispatch_issue_during_preflight():
    text = INSTALLER_PATH.read_text()
    assert "supervisor.py\" --config \"$CONFIG_FILE\" --once" not in text
    assert "gh auth status" in text
    assert "dispatch_command" in text
