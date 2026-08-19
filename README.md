# agent-resources — Public Agent Operations Hub

[![Skill catalog integrity](https://github.com/KAFKA2306/agent-resources/actions/workflows/skill-catalog.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/skill-catalog.yml)
[![Build and Deploy Docs](https://github.com/KAFKA2306/agent-resources/actions/workflows/docs.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/docs.yml)
[![Validate Dashboard](https://github.com/KAFKA2306/agent-resources/actions/workflows/dashboard-validate.yml/badge.svg)](https://github.com/KAFKA2306/agent-resources/actions/workflows/dashboard-validate.yml)

**AIエージェントを増やすほど、「いま何が動いていて、何が止まっていて、どこまで任せられるか」が見えなくなる。**

`agent-resources` は、KAFKA2306 の公開GitHub作業を横断して現在状態を観測し、必要なagent skillを導入・一時実行し、証拠と状態を優先するUIで運用を確認する中央ハブです。

- Live Dashboard: https://agent-resources-one.vercel.app/
- Live API: https://agent-resources-one.vercel.app/api/dashboard-live
- GitHub Pages fallback: https://kafka2306.github.io/agent-resources/dashboard/
- CLI / Skills docs: https://kafka2306.github.io/agent-resources/site/
- PyPI: https://pypi.org/project/agent-resources/

## Vision

AIエージェント運用を「裏で何かが動いている」状態から、**人間が現在の仕事・証拠・失敗・次actionを一目で確認し、必要な能力だけを安全に追加できる運用体験**へ変えます。

このrepositoryは主に3つのsurfaceを持ちます。

1. **Public Agent Operations Dashboard** — public repo / Issue / PR / Actions の現在状態を見る
2. **`agr` / `agrx`** — agent skillを導入・同期・一時実行する
3. **KAFKA Evidence UI** — evidence / provenance / stateを中心にした運用UIを再利用する

3つを別productとして並べるのではなく、**「agentの能力と作業状態を、人間が監査可能なまま運用する」**という一つの目的で接続します。

## Design philosophy

- **現在状態を推測しない。** Dashboardはpublic GitHub stateと生成snapshotを読み、架空の進捗を作らない。
- **分類根拠を混ぜない。** project zoneは`agent-zone-*` topicで定義し、programming languageからdomainを推測しない。
- **Liveとsnapshotを分ける。** Live APIが取れない場合はfallbackを明示し、古いsnapshotを「最新」と表示しない。
- **private境界を越えない。** public dashboardへprivate repo・secret・private work itemを混ぜない。
- **skillは最小必要量だけ導入する。** 恒久installが不要なら`agrx`で一時実行する。
- **UI assetをtruth sourceにしない。** visual表現とoperational stateを分離する。
- **tech stackを価値扱いしない。** Vercel / GitHub Pages / CLI / schemaは、観測可能性と再現性を守るための手段。

## Why / 差別化

agent運用で難しいのは、モデルを呼び出すことより、**多数のprojectを跨いだときに「何が本当に進んでいるか」を失わないこと**です。

このrepositoryの差別化は、agent数やskill数ではなく次の点にあります。

- open Issue / PR / workflow runを同じwork laneへ投影する
- Live stateとsnapshot fallbackを区別する
- source不明の分類を`unclassified`として残す
- skillの取得元と実行権限を利用者が確認できる
- evidence-first UIを他dashboardへ再利用できる

## 1. Public Agent Operations Dashboard

Dashboardは `KAFKA2306` 所有の **public / non-archived repository** をGitHub APIから自動収集します。private repositoryは対象外です。

### 見えるもの

- project zone → repository → Issue / PR / workflow
- work lane: `working / waiting / done / failed`
- repositoryごとの現在work item
- 直近7日間のactivity
- monthly public GitHub activity
- attention ordering

baselineは `docs/dashboard/dashboard.json` へ生成し、schema validationとpublic boundary auditを通したものだけ配信します。

Vercel版はpage open / focus復帰時にLive APIを取得し、baselineへoverlayします。Live取得に失敗した場合は `SNAPSHOT FALLBACK` を表示します。

### Work lane

| lane | 主な状態 |
|---|---|
| `working` | open Issue、queued / in-progress workflow |
| `waiting` | open PR、確認待ち |
| `done` | closed Issue / PR、successful / skipped workflow |
| `failed` | failed / cancelled workflow |

### Project zone

```text
agent-zone-<name>
```

例:

```text
agent-zone-finance
agent-zone-vr
agent-zone-research
agent-zone-automation
```

topicがなければ `unclassified` です。Python / TypeScript等のlanguageからdomainを推測しません。

### 更新

GitHub Pages snapshot:

- relevant pathの`main`更新
- 毎日09:17 JST
- `workflow_dispatch`

Vercel Live APIは閲覧時に最新public stateをoverlayします。

## 2. `agr` / `agrx` — 必要なskillだけ使う

Install:

```bash
pip install agr
```

skillを追加:

```bash
agr add anthropics/skills/frontend-design
agr add -g anthropics/skills/frontend-design
```

一時実行:

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/pdf --tool cursor
```

team dependency:

```toml
dependencies = [
  {handle = "anthropics/skills/frontend-design", type = "skill"},
]
```

```bash
agr sync
```

主なcommand:

| command | purpose |
|---|---|
| `agr add <handle>` | skillを追加 |
| `agr remove <handle>` | skillを削除 |
| `agr sync` | `agr.toml`を同期 |
| `agr list` | installed skill表示 |
| `agr init` | config / skill初期化 |
| `agr onboard` | 対話onboarding |
| `agrx <handle>` | temporary execution |

## 3. KAFKA Evidence UI

高密度dashboard / catalog / monitoring向けのevidence-first design systemです。

- [Showcase](https://agent-resources-one.vercel.app/)
- [Design system skill](skills/kafka-evidence-ui/SKILL.md)
- [Agent plugin](plugins/kafka-evidence-ui/README.md)

visual asset自身にはstatusを持たせません。状態・link・work itemはDashboard snapshot / Live APIが正本です。

## Data flow

```text
public GitHub
  → collectors
  → schema / privacy validation
  → canonical snapshot
  → GitHub Pages fallback
  → Vercel Live API overlay
  → operator decision
```

skill側:

```text
trusted source / local path
  → inspect
  → agr add / agrx
  → target tool
  → explicit removal / sync
```

## Development / validation

```bash
pip install -r dashboard/requirements.txt
python -m unittest discover -s dashboard/tests -p 'test_*.py' -v
npm run test:dashboard
```

中心処理:

```text
dashboard/collectors/*
  → dashboard/build.py
  → JSON Schema validation
  → docs/dashboard/dashboard.json
  → Pages snapshot
  → Vercel Live overlay
```

## Security boundary

skillを実行する前に確認するもの:

- repository owner / source
- `SKILL.md`
- shell / network / file mutation
- secret access要求
- helper scripts / dependencies

Dashboard側:

- public repositories only
- archived repo除外
- private work item除外
- `DASHBOARD_GITHUB_TOKEN` はserver-side only
- browser bundleへcredentialを埋め込まない

## Repository map

```text
dashboard/     collectors / schema / build / tests
docs/          Pages snapshot / CLI docs
skills/        reusable agent skills
plugins/       packaged integrations
src/           agr / agrx implementation
tests/         CLI contracts
```

## Done

このrepositoryの成功指標は「agentを何個動かしたか」ではありません。

**人間が、現在のpublic作業状態を誤認せず、必要な能力だけを追加し、どの証拠を根拠に次actionを取るか判断できること**をDoneとします。

## License

[MIT License](LICENSE)
