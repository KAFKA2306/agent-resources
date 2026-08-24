---
title: OpenClaw Local Autonomous Worker
---

# OpenClaw Local Autonomous Worker

GitHub Issue を **1 Issue = 1 one-shot OpenCode ACP run** として処理するローカル coding worker の運用契約です。FreeToken + Ornith がローカル推論を提供し、OpenClaw は ACP control plane、Python supervisor は deterministic control plane、OpenCode は repository 編集だけを担当します。

## 正準構成

```text
GitHub open Issue
  -> autonomous supervisor
  -> isolated Git worktree
  -> bounded task file
  -> OpenClaw coding-worker (runtime.type=acp, mode=oneshot)
  -> OpenCode ACP (cwd = exact Issue worktree)
  -> local code change + repository validation
  -> supervisor commit / push / PR
  -> exact-head CI
  -> merge
  -> optional existing release verification
```

OpenClaw 内にIssue全文を読む親LLM routerは置きません。Issueを跨ぐ共有LLM sessionも使いません。compactionをjob isolationの代用にしません。

## 責務境界

### Supervisor

- allowlist対象repositoryからopen Issueを取得・選択する
- Issue専用worktreeをdefault branchから用意する
- Issue本文を上限付きのuntrusted task dataとしてlocal stateへmaterializeする
- `coding-worker` のACP runtimeを `opencode` / `oneshot` / exact worktree `cwd` にread-back付きで固定する
- runごとに新しいsession keyを発行する
- OpenCode終了後にrepository既存のtest / lint / type check / buildを実測する
- commit / push / canonical PR / exact-head CI / mergeを管理する
- runtime state、retry、結果を保存する

### OpenClaw

OpenClawはACP sessionの起動・routingだけを担当します。`coding-worker` はembedded model agentではなく次のruntime contractを持ちます。

```json
{
  "type": "acp",
  "acp": {
    "agent": "opencode",
    "mode": "oneshot"
  }
}
```

実run直前にsupervisorが `runtime.acp.cwd` をIssue専用worktreeへ固定し、read-backします。

### OpenCode

OpenCodeは指定worktreeだけを作業対象にします。

- repositoryを読んでIssueを実装する
- repository-local validationを実行する
- changed files / commands / exit codes / risksを返す

OpenCodeにはGitHub control-plane責務を持たせません。Issue/comment作成、commit、push、PR、merge、release、deploy、schedule、外部network利用は禁止します。

## Context isolation

LLM contextの寿命とdaemonの寿命を分離します。

```text
FreeToken / OpenClaw Gateway / supervisor: long-lived
Issue inference context:                    one-shot
```

各runでは新規session keyを使います。同じ `coding-worker` transcriptへ #14 → #8 → #45 のように別Issueを蓄積しません。

Issue本文は `issue_body_max_chars` で上限を設け、task fileへ保存して `openclaw agent --message-file` で直接OpenCode ACPへ渡します。親Ornithに一度読ませてからOpenCodeへ再転送する二重contextはありません。

## 削除済みの旧経路

旧実装の親LLM router、外部dispatch wrapper、共有session、compaction依存、native-subagent fallback、親agentへのfilesystem権限追加、llama.cpp runtimeは正準構成から削除済みです。互換経路は保持しません。

## 設定

repository側のexampleは `scripts/openclaw-autonomous-worker/config.example.json` です。主要項目:

```json
{
  "openclaw_bin": "/root/.openclaw/bin/openclaw",
  "openclaw_agent": "coding-worker",
  "openclaw_harness": "opencode",
  "issue_body_max_chars": 12000,
  "agent_timeout_seconds": 7200
}
```

`install-systemd.sh` は既存の `coding-worker` からembedded-router用の `model` / `tools` / `subagents` / context overrideを除去し、one-shot OpenCode ACP runtimeへ置換します。agentが無ければ作成します。`acp.allowedAgents` は既存値を保持したまま `opencode` を追加します。

ローカル推論は FreeToken `0.1.2` と `ornith-ai/Ornith-1.5-35B-A3B-NVFP4` を使います。installerはhardware preflightと `ft bench bw --dtype nvfp4` を実行し、FreeToken endpointを起動して実completionとruntime/cache evidenceを確認してからsupervisorを開始します。

## systemd

長寿命processは3つです。

```text
freetoken.service
openclaw-gateway.service
openclaw-autonomous-worker.service
```

```bash
scripts/openclaw-autonomous-worker/install-systemd.sh
```

installerはrepositoryを処理する前にconfig、GitHub auth、GPU/CUDA、FreeToken installation / bandwidth benchmark、FreeToken health / model / completion、OpenClaw ACP config、Gateway healthを検証します。workerはFreeTokenとGatewayの実health確認後に起動します。旧 `llama-server.service` はinstallerが停止・削除します。

## State

runtime stateはrepositoryへcommitしません。

```text
~/.local/state/openclaw-autonomous-worker/
  state.json
  events.jsonl
  freetoken-preflight.json
  freetoken-evidence/
  runs/<task-id>/<run-id>/
    task.md
    result.json
    stderr.log  # stderrがある場合のみ
```

state schema versionは `2` です。旧stateは再利用せず、新しいjob-isolated contractで作り直します。

credentialやDashboard token付きURLはtask/state/logへ保存しません。

## Verification

repository-level verification:

```bash
python -m py_compile scripts/openclaw-autonomous-worker/supervisor.py
python -m pytest -q tests/test_openclaw_autonomous_worker.py
bash -n scripts/openclaw-autonomous-worker/install-systemd.sh
```

host E2E完了条件:

1. FreeToken / Gateway / supervisorがsystemdで復帰する
2. FreeToken `/health` と `/v1/models` が成功し、Ornith modelを返す
3. OpenAI-compatible `/v1/chat/completions` の実completionが成功する
4. `coding-worker` runtime read-backが `acp -> opencode -> oneshot` である
5. 1 Issueにつきfresh session keyが発行される
6. ACP childのcwdがそのIssue専用worktreeと一致する
7. 親embedded LLM sessionを生成しない
8. OpenCodeがworktreeを変更し、local validation結果を返す
9. supervisorがvalidationを再実測する
10. 成功変更をcommit / push / canonical PRへ反映する
11. exact PR head SHAのCIを確認する
12. merge条件を満たす場合だけmergeする
13. 既存release pathがある場合だけreleaseと直接verificationを行う
14. 失敗Issueがあってもretry stateを保存し、daemon自体は継続可能である

CI greenはhost E2Eやproduction成功の代用ではありません。repositoryへ統合しただけの段階ではhost runtimeを `UNVERIFIED` とします。

## Primary upstream contract

OpenClaw `v2026.7.1-2` の公式ACP contractを基準にします。

- ACP agents: `docs/tools/acp-agents.md`
- ACP setup: `docs/tools/acp-agents-setup.md`
- Agent CLI: `docs/cli/agent.md`
- Config CLI: `docs/cli/config.md`

OpenCodeは公式ACPX harness id `opencode` を使用し、独自ACP wrapperを追加しません。
