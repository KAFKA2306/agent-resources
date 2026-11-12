#!/usr/bin/env python3
"""Minimal Claude Code Hooks: clean deploy, score plateau, final verification, compaction."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ["AGENT_LITE_RUN_ROOT"])
STATE_PATH = ROOT / "score-state.json"
STALL = int(os.environ.get("AGENT_LITE_STALL_SECONDS", "1800"))
FREEZE = int(os.environ.get("AGENT_LITE_FREEZE_SECONDS", "2400"))
DEADLINE = int(os.environ.get("AGENT_LITE_DEADLINE_EPOCH", "0"))


def state_read():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def state_write(state):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def context(event, message):
    if message:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                                  "additionalContext": message}}, ensure_ascii=False))


def pre(payload):
    command = payload.get("tool_input", {}).get("command", "").strip()
    # An opt-in guard for the two conventional commands. Native deploy entrypoints
    # must ALSO enforce this; permission rules alone are not OS containment.
    if not re.fullmatch(r"make (?:bench|deploy)", command):
        return
    check = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                           cwd=payload.get("cwd") or os.getcwd(), check=False)
    if check.returncode or check.stdout.strip():
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
             "permissionDecision": "deny",
             "permissionDecisionReason": "Uncommitted changes or git status failed. Commit a rollback point before make bench/deploy."}}))


def post(payload):
    now = int(time.time())
    state = state_read()
    command = payload.get("tool_input", {}).get("command", "").strip()
    stdout = payload.get("tool_response", {}).get("stdout", "")
    if command == "make bench" and isinstance(stdout, str):
        found = re.findall(r"^AGENT_SCORE=(\d+(?:\.\d+)?)\s*$", stdout, re.M)
        if found:
            score = max(float(s) for s in found)
            if state.get("best") is None or score > state["best"]:
                state["best"] = score
                state["best_at"] = now
                state.pop("audit_at", None)
    reminders = []
    if state.get("best_at") is not None and now - state["best_at"] >= STALL:
        if now - state.get("audit_at", 0) >= STALL:
            state["audit_at"] = now
            reminders.append("Best benchmark score has not improved for 30 minutes. Start an independent audit subagent to review the bottleneck and reverted changes. Use the real remaining budget; do not automatically apply its ideas.")
    if DEADLINE and 0 < DEADLINE - now <= FREEZE and not state.get("freeze_sent"):
        state["freeze_sent"] = True
        reminders.append("Deadline is within 40 minutes. Stop large changes. Verify cold restart, persistence, deploy from the last committed state, and the final benchmark where these checks apply.")
    if reminders:
        context("PostToolUse", " ".join(reminders))
    state_write(state)


def compact(_payload):
    conditions = (ROOT / "CONDITIONS.md").read_text(encoding="utf-8")
    context("SessionStart", "Run conditions (reloaded after compaction):\n" + conditions)


if __name__ == "__main__":
    action = sys.argv[1]
    payload = json.load(sys.stdin)
    if action == "pre":
        pre(payload)
    elif action == "post":
        post(payload)
    elif action == "compact":
        compact(payload)
    else:
        raise SystemExit("unknown hook")