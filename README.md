# agent-resources — 公開Agent運用ハブ

https://agent-resources-one.vercel.app/
https://agent-resources-one.vercel.app/site/

[![Skill catalog integrity](https://github.com/KAFKA2306/agent-resources/actions/workflows/skill-catalog.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/skill-catalog.yml)
[![Build and Deploy Docs](https://github.com/KAFKA2306/agent-resources/actions/workflows/docs.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/docs.yml)
[![Validate Dashboard](https://github.com/KAFKA2306/agent-resources/actions/workflows/dashboard-validate.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/dashboard-validate.yml)

KAFKA2306 の公開GitHub作業を横断して、**何が動いているか、何が失敗したか、何に対応が必要か、その証拠はどこか**を確認する人間向けoverviewです。同時に、`agr` / `agrx` で必要なagent skillだけを導入・実行できます。

このrepositoryやDashboard自体を状態の正本にはしません。各repository、GitHub、deployment、productionの直接証拠を優先します。

## できること

### 公開作業を確認する

DashboardはKAFKA2306所有のpublic / non-archived repositoryを対象に、Issue、PR、GitHub Actions、直近activityを横断表示します。

- Live APIの取得状態を明示する
- private repository、secret、private work itemを公開面へ出さない
- repository domainは明示された`agent-zone-*` topicだけを正準値として扱う
- 取得不能な状態を推測で補完しない

詳細な状態はDashboardから各GitHub evidenceへ辿れます。

### Agent skillを使う

このrepositoryのCLIを直接導入します。

```bash
uv tool install git+https://github.com/KAFKA2306/agent-resources.git
```

skillを追加:

```bash
agr add anthropics/skills/frontend-design
```

一時実行:

```bash
agrx anthropics/skills/pdf
```

team dependencyを同期:

```bash
agr sync
```

CLIの詳細は [CLI / Skills docs](https://agent-resources-one.vercel.app/site/) を参照してください。

### Evidence-first UIを再利用する

Dashboardで使う高密度な運用UIを再利用できます。

- [Showcase](https://agent-resources-one.vercel.app/)
- [Design system skill](skills/kafka-evidence-ui/SKILL.md)
- [Agent plugin](plugins/kafka-evidence-ui/README.md)

## 開発

```bash
uv run pytest
uv run ruff check .
uv run ty check
npm run test:dashboard
```

主要配置:

```text
dashboard/     public state collectors / build / tests
docs/          public Dashboard / CLI docs sources
skills/        reusable agent skills
plugins/       packaged integrations
src/           agr / agrx implementation
```

repository運用契約、merge/release evidence、documentation policy、security boundaryは [AGENTS.md](AGENTS.md) を正準とします。

## License

[MIT License](LICENSE)
