# Agent Resources

このファイルをrepository運用の正準とします。`CLAUDE.md` などtool固有のinstruction fileには、ここにない差分だけを書きます。

## Scope

このrepositoryは主に次を保守します。

- public GitHub状態を観測するDashboard / API / snapshot
- `agr` / `agrx` CLI
- reusable skills / plugins
- GitHub Pages上のCLI documentation

public Dashboardはprivate repository、secret、private work itemを扱いません。

## Commands

Python環境は `uv` を使います。Python commandは原則 `uv run` で実行します。

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run ty check
uv run agr --help
uv run agrx --help
```

Dashboard変更ではrepository内の既存test/build commandを優先し、該当するGitHub Actionsも確認します。

## Change policy

- current user instruction > このファイル > current official upstream docs > current GitHub/production state > historical context の順で判断する。
- 既存の標準機能・既存実装を再利用し、`DELETE > MERGE > REPLACE > ADD` を優先する。
- 同じ責務のwrapper、config、workflow、schema、documentation、status authorityを増やさない。
- repository固有の略語、maturity level、named gate、confidence score、独自taxonomyを、外部標準や実要件なしに作らない。
- Dashboardではlive / snapshot / unavailableを区別し、未観測状態を推測で埋めない。
- repository domain classificationは現在のexplicit `agent-zone-*` authorityに従い、repo名・language・LLM推測から正準値を作らない。
- `skills/` をrepository内skillの正準配置とする。
- `agr` と `agrx` の共有責務は可能な限り共通実装へ寄せ、挙動を不必要に分岐させない。

## Documentation

Documentationもmaintained surfaceとして扱います。

- `README.md`: 人間向けの短い入口、主要surface、最短の利用・検証経路
- `AGENTS.md`: repository/agent運用契約
- `docs/docs/`: CLI利用者向けの恒久的なguide/reference
- その他のdocs: 独立した現在有効な役割がある場合だけ残す

obsoleteな文書は削除し、重複文書は統合します。source code、schema、workflow、upstream docsを長文で複製せず、安定した正準sourceへlinkします。削除済みfile、command、workflow、endpointへの参照を残しません。

## GitHub writes

1. write直前に対象branch / PR / Issue / CIを再取得する。
2. 既存のcanonical branch / PRを再利用し、duplicate worklineを作らない。
3. 同じrepository stateへのmutationは1つずつ行い、write後にread-backする。
4. mergeはexact PR headで必要なCIがgreenであることを確認し、可能ならexpected head SHAを固定する。
5. host-side rejectionを認証失敗と決めつけず、stateを再取得して同じcanonical actionを1回だけ再試行する。2回目も拒否されたらそのrunのmutationを止める。
6. merge後はmain / PR / Issue / branchを再確認してからcleanupする。未完了branchを削除しない。
7. 未実行・未観測のtest、deployment、runtime layerをPASSと報告しない。

## Security

- credentialをbrowser bundle、public snapshot、fixture、log、docsへ入れない。
- external skillを実行する前にsource、`SKILL.md`、shell/network/file mutation、secret要求、helper dependencyを確認する。
- destructive actionや権限拡大は現在stateと明示的な意図を確認する。

## Primary references

- Agent Skills: https://agentskills.io/
- AGENTS.md: https://agents.md/

各tool固有仕様は必要時にそのtoolの現行公式documentationを参照し、このファイルへコピーしません。
