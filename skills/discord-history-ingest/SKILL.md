---
name: discord-history-ingest
description: Keep a local Discord Desktop cache archive flowing into Graphiti with zero routine human work by observing supervisor state, applying bounded self-recovery, and never requesting Discord user tokens, bot setup, manual exports, or manual scrolling.
---

# Discord history ingest

Use this skill when Discord history ingestion should operate without routine user involvement.

## Contract

The steady-state target is:

- no Discord Bot or Developer Portal setup
- no Discord user token extraction
- no selfbot
- no manual export
- no manual channel selection or scrolling
- no routine database inspection
- no routine restart, update, backup, or reindex work
- no notification when automatic recovery succeeds

The collector reads only the local Discord Desktop cache through discrawl wiretap. It does not make Graphiti call Discord as the user.

## Canonical local state

Prefer GRAPHITI_DISCORD_HOME when set.

Otherwise on Windows use %LOCALAPPDATA%\Graphiti\discord-history\.

Important files: supervisor-state.json, discrawl.sqlite, graphiti-checkpoint.json, logs/supervisor.log, logs/discrawl-wiretap.log, logs/graphiti-worker.log, and backups/.

Do not copy these files into a public repository, issue, log attachment, or artifact. They may contain private Discord identifiers or content.

## Normal operation

Read supervisor-state.json. A healthy system should show status=healthy, live collector_pid and worker_pid values, a recent updated_at_unix, no persistent last_error, and graphiti_lag either not pending or pending only briefly below the stall threshold.

If the state is healthy, do nothing. Do not produce a routine all-good notification unless the caller explicitly asked for one.

## Bootstrap

If the state file is absent and the implementation module is available locally, run:

    python -m graphiti_core.integrations.discord.supervisor --bootstrap

The bootstrap owns local runtime creation, Discord Desktop cache discovery, managed discrawl installation from the official release, wiretap-only configuration, startup registration, and supervisor startup.

Do not ask the user to install a Discord bot, copy a token, run DiscordChatExporter, or start Discord History Tracker as a fallback.

If Discord Desktop is not present yet, leave the system in waiting_for_discord_desktop. Do not convert this into recurring user maintenance.

## Autonomous recovery

When status=degraded, inspect last_error, graphiti_lag, and local logs. Prefer the existing supervisor recovery loop first. It owns process restart with bounded backoff, SQLite backup and restore, WAL/SHM-safe database replacement, discrawl candidate validation, incompatible-update rejection, binary rollback, Graphiti catch-up, log rotation, and low-disk cleanup.

Do not create a second watchdog, scheduler, state database, backup directory, or updater.

If the supervisor process itself is absent, rerun the bootstrap command. Then re-read the state file and verify that updated_at_unix advances.

## Failure classification

Collector stopped: allow the supervisor restart loop to act, verify a new collector_pid, verify updated_at_unix advances, and verify coverage/status returns. Do not ask the user to relaunch discrawl.

Graphiti unavailable: the collector must continue independently. Verify discrawl.sqlite continues to update, graphiti_lag.pending becomes true, allow the worker to retry, and verify lag clears after Graphiti recovers.

SQLite integrity failure: the supervisor stops data users, quarantines the current DB, restores the last-known-good SQLite backup atomically, restarts collector and worker, and rechecks integrity. Do not ask the user to replace SQLite files.

Discrawl update failure: keep candidates out of production unless checksum, writer smoke, diagnostics, and adapter compatibility pass. If a promoted candidate regresses, restore the previous binary and matching pre-update database backup. Do not tell the user to downgrade manually.

Disk pressure: remove only rebuildable or redundant operational data such as old backups beyond retention, stale candidate or failed binary directories, older quarantine copies, and rotated logs. Never delete canonical discrawl.sqlite for space.

## Hard stops

A hard stop is an external condition the local software has no authority to resolve, such as Discord Desktop never having created a local cache, OS policy blocking execution/startup registration, unavailable Graphiti/database credentials, or no access to the official release host when no managed discrawl binary exists.

For a hard stop, report the exact missing authority or prerequisite. Do not disguise it as success.

## Coverage honesty

discrawl wiretap archives messages Discord Desktop has cached locally. It is not a complete account-history fetch. Do not claim unseen or evicted history is archived. Preserve skipped and unresolved counters as coverage gaps. Do not introduce manual scrolling or DHT as a routine completeness repair.

## Verification

Do not declare recovery from process or code state alone. Verify supervisor-state.json refreshes, collector and worker PIDs are live when expected, discrawl diagnostics report a healthy readable archive, Graphiti lag is not stalled, repeated scans do not duplicate Graphiti episodes, and injected recoverable process/database faults return to healthy without user action.

If the local runtime cannot be inspected, mark runtime verification as not verified. Do not replace it with issue text, a commit, or a pull request.
