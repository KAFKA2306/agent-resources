https://agent-resources-one.vercel.app/

# agent-resources — Software Factory Control Tower

[![Skill catalog integrity](https://github.com/KAFKA2306/agent-resources/actions/workflows/skill-catalog.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/skill-catalog.yml)
[![Build and Deploy Docs](https://github.com/KAFKA2306/agent-resources/actions/workflows/docs.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/docs.yml)
[![Validate Control Tower](https://github.com/KAFKA2306/agent-resources/actions/workflows/dashboard-validate.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/dashboard-validate.yml)

KAFKA2306 のソフトウェア運用を、**人がタスクを回す仕組み**から、**自律的に発見・修復・検証・配布するソフトウェア工場**へ移すための観測・制御基盤です。

公開UIの正式名称は **Software Factory Control Tower**。各repository、GitHub、deployment、productionの直接証拠を横断して、工場全体の状態を人間が監査できる形にします。

## Factory loop

~~~text
observe
→ discover work
→ classify / prioritize / route
→ execute
→ verify
→ repair / re-verify
→ merge
→ release / deploy
→ production probe
→ rollback or fix-forward
→ close
→ learn
~~~

目標は agent の稼働数ではなく、**routine human intervention = 0**。CI失敗、model/provider停止、runner停止、merge conflict、deploy失敗などは通知で終わらせず、自動修復ループへ戻します。

## Control Tower

Control Tower は工場の第二の正本ではありません。表示される状態から必ず canonical evidence へ戻れることを優先します。

- LIVE / SNAPSHOT / STALE / UNVERIFIED を区別する
- Issue / PR / Actions / deployment / production evidence を横断する
- 失敗を表示するだけでなく、どの工程で止まったかを示す
- routine human intervention を automation gap として扱う
- private repository、secret、private work itemを公開面へ出さない

公開UI: https://agent-resources-one.vercel.app/

設計説明: https://agent-resources-one.vercel.app/site/control-tower/

## North-star metrics

- Routine human intervention
- E2E yield / first-pass yield
- Lead time p50 / p95
- Queue time vs execution time
- Self-heal success rate
- Failure Pareto / recurrence
- Auto-merge / auto-deploy / rollback success

## AGR CLI / Skills

このrepositoryは Control Tower に加えて、AI agent skillを導入・共有・一時実行する `agr` / `agrx` も提供します。

~~~bash
uv tool install git+https://github.com/KAFKA2306/agent-resources.git
agr add anthropics/skills/frontend-design
agrx anthropics/skills/pdf
agr sync
~~~

CLI docs: https://agent-resources-one.vercel.app/site/cli/

## Authority

- owner repository: 実装とrepository固有state
- GitHub Issue / PR / Actions / Checks / Rulesets: 作業・検証・統合state
- deployment provider / canonical production: 配布・稼働state
- artifact / attestation: build lineage
- agent-resources: controller contract、横断observability、AGR CLI / skills

未観測状態を推測で埋めず、unknown / missing evidence は `UNVERIFIED` のまま扱います。

## Web UI / Evidence UI

KAFKA2306 の共有Web UI authorityは `KAFKA2306/design` です。Control Tower側に第二のdesign systemを作らず、ここでは工場stateとevidenceの見せ方だけを持ちます。

- [Web UI改善Skill](skills/kafka-evidence-ui/SKILL.md)
- [Agent plugin](plugins/kafka-evidence-ui/README.md)
## Repository map

~~~text
dashboard/     Control Tower collectors / control contracts / tests
docs/dashboard/ public Control Tower UI
docs/content/   public documentation
api/            live overlay API
skills/         reusable agent skills
plugins/        packaged integrations
src/            agr / agrx
~~~

内部互換のため `dashboard/`、`dashboard.json`、`/api/dashboard-live` など既存の技術識別子は維持します。製品名は Software Factory Control Tower に統一します。

## Development

~~~bash
uv run pytest
uv run ruff check .
uv run ty check
npm run test:dashboard
~~~

repository運用契約、security boundary、autonomous factory invariant は [AGENTS.md](AGENTS.md) を正準とします。

## License

[MIT License](LICENSE)
