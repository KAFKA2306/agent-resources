"""End-to-end git history fixtures for secret scan range selection."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "gitleaks-reusable.yml"
text = WORKFLOW.read_text(encoding="utf-8")
start = text.index("          python3 - <<'PY'\n") + len("          python3 - <<'PY'\n")
end = text.index("          PY\n", start)
source = "\n".join(line[10:] for line in text[start:end].splitlines()) + "\n"
selector = importlib.util.module_from_spec(importlib.util.spec_from_loader("select_gitleaks_range", loader=None))
exec(compile(source, str(WORKFLOW), "exec"), selector.__dict__)


def git(cwd, *args):
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def commit(cwd, text):
    path = cwd / "file.txt"
    path.write_text(text)
    git(cwd, "add", "file.txt")
    git(cwd, "commit", "-m", text)
    return git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    subprocess.check_call(["git", "init", "--bare", str(origin)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "-b", "main", str(work)], stdout=subprocess.DEVNULL)
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.invalid")
    git(work, "remote", "add", "origin", str(origin))
    main = commit(work, "initial")
    git(work, "push", "origin", "main")
    monkeypatch.chdir(work)
    return work, main


def test_new_branch_only_scans_unique_commits(repo):
    work, main = repo
    git(work, "checkout", "-b", "feature")
    head = commit(work, "feature")
    event = {"after": head, "before": selector.ZERO, "ref": "refs/heads/feature", "repository": {"default_branch": "main"}}
    assert selector.select_range(event, "push", head) == (f"{main}..{head}", "new-branch-delta")
    assert git(work, "rev-list", "--count", f"{main}..{head}") == "1"


def test_normal_push_and_pr(repo):
    work, main = repo
    head = commit(work, "second")
    assert selector.select_range({"before": main, "after": head}, "push", head) == (f"{main}..{head}", "push-delta")
    pr = {"pull_request": {"base": {"sha": main}, "head": {"sha": head}}}
    assert selector.select_range(pr, "pull_request", head) == (f"{main}..{head}", "pull-request")


def test_force_push_and_missing_base_fail_closed(repo):
    work, main = repo
    old = commit(work, "old")
    git(work, "reset", "--hard", main)
    new = commit(work, "rewritten")
    with pytest.raises(selector.UnsafeRange):
        selector.select_range({"before": old, "after": new}, "push", new)
    with pytest.raises(selector.UnsafeRange):
        selector.select_range({"before": "f" * 40, "after": new}, "push", new)


def test_orphan_branch_and_invalid_event_fail_closed(repo):
    work, _ = repo
    git(work, "checkout", "--orphan", "unrelated")
    git(work, "rm", "-rf", ".")
    head = commit(work, "orphan")
    event = {"before": selector.ZERO, "after": head, "ref": "refs/heads/unrelated", "repository": {"default_branch": "main"}}
    with pytest.raises(selector.UnsafeRange):
        selector.select_range(event, "push", head)
    with pytest.raises(selector.UnsafeRange):
        selector.select_range(event, "pull_request_target", head)


def test_full_history_only_when_manual(repo):
    _, main = repo
    assert selector.select_range({}, "workflow_dispatch", main) == ("--all", "manual-full-history")
    with pytest.raises(selector.UnsafeRange):
        selector.select_range({"before": selector.ZERO, "after": main, "ref": "refs/heads/main", "repository": {"default_branch": "main"}}, "push", main)
