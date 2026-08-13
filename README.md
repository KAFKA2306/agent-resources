# agent-resources — Public Agent Operations Hub

**KAFKA2306 の公開 GitHub 作業を、ひとつの画面で観測するための中央ハブです。**

このリポジトリは現在、主に次の3つを担っています。

1. **Public Agent Operations Dashboard** — 公開 repository / Issue / PR / GitHub Actions を横断して、現在の作業状態を可視化する
2. **`agr` / `agrx`** — AIエージェント用スキルを追加・同期・一時実行するCLI
3. **KAFKA Evidence UI** — 証拠・状態・provenanceを優先する公開データUI / dashboard向けデザイン資産

## Open

- **Public Dashboard:** https://kafka2306.github.io/agent-resources/dashboard/
- **CLI / Skills Documentation:** https://kafka2306.github.io/agent-resources/site/
- **Repository:** https://github.com/KAFKA2306/agent-resources
- **PyPI:** https://pypi.org/project/agent-resources/

リポジトリのGitHub Pagesルート `https://kafka2306.github.io/agent-resources/` も dashboard へリダイレクトします。

---

## 1. Public Agent Operations Dashboard

Dashboard は、`KAFKA2306` が所有する **public かつ non-archived な repository** を GitHub API から自動収集します。repository の個別 allowlist は持ちません。

表示対象は公開情報だけです。private repository は snapshot に入りません。

### 何が見えるか

- **Live Agent World** — project区画 → repository station → Issue / PR / workflow agent
- **work lanes** — `working` / `waiting` / `done` / `failed`
- **repository details** — 各 repository の現在の work item
- **Recent Activity** — 直近 **7日間** の Issue / PR 活動と、各 repository の最新 workflow 状態
- **GitHub activity stats** — public repository を対象にした月次 Commit / PR / Issue 推移
- **heat / attention ordering** — 対応が必要な work を上位に出すための表示優先度

Dashboard の状態は `docs/dashboard/dashboard.json` へ生成され、schema validation と public boundary audit を通ったものだけが GitHub Pages に配信されます。

### work lane の意味

| lane | 主な状態 |
| --- | --- |
| `working` | open Issue、queued / in-progress workflow |
| `waiting` | open PR、または明示分類できず確認が必要な状態 |
| `done` | closed Issue / PR、successful / skipped workflow |
| `failed` | failed / cancelled workflow |

### project zone の付け方

project の意味的な区画は GitHub repository topic で指定します。

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

`agent-zone-*` が無い repository は `unclassified` に入ります。

**programming language は project zone の代替には使いません。** Python / JavaScript などの実装言語と、project の目的・責務を混同しないためです。

### 更新タイミング

GitHub Pages の build は次の契機で実行されます。

- `main` の `docs/**` / `dashboard/**` 等が更新されたとき
- **毎時17分** の scheduled build
- `workflow_dispatch`

build 時に GitHub API から repository、work item、workflow run、7日間の activity、public GitHub stats を再収集し、canonical snapshot を生成します。

### 公開境界

Dashboard は **public-only** を契約にしています。

- owner: `KAFKA2306`
- public repository のみ
- archived repository は除外
- private repository は除外
- stats も `scope = public`
- snapshot は JSON Schema で検証
- Pages build 時に public artifact boundary を再監査

---

## 2. `agr` — Agent Skill Manager

`agr` は、GitHub またはローカルディレクトリ上のエージェントスキルを、Claude Code、Codex、Cursor、OpenCode、GitHub Copilot、Antigravity などのスキル配置先へ導入するCLIです。

`agrx` は、スキルを恒久インストールせず、一時的に取得・実行・削除します。

### Install

```bash
pip install agr
```

リモートから取得する場合はローカル環境に `git` が必要です。

### Add a skill

```bash
agr add anthropics/skills/frontend-design
agr add -g anthropics/skills/frontend-design
agr add anthropics/skills/pdf anthropics/skills/mcp-builder
```

handle:

```text
username/skill-name
username/repo/skill-name
./path/to/skill
```

- `username/skill-name` — ユーザーの標準 `skills` repository から取得
- `username/repo/skill-name` — repository を明示
- `./path/to/skill` — local directory から追加

2要素形式は標準で `skills` repository を参照します。移行期間中は、見つからない場合に `agent-resources` も確認して警告します。

### Run temporarily with `agrx`

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/skill-creator -i
agrx anthropics/skills/pdf --tool cursor
```

### Share dependencies with a team

依存スキルは `agr.toml` に記録します。

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/brand-guidelines", type = "skill"},
]
```

```bash
agr sync
agr sync -g
```

### Create a skill

```bash
agr init my-skill
```

この repository へ追加する場合は `skills/` 配下へ置き、ローカルで検証できます。

```bash
agr add ./skills/my-skill
```

### Initialize / onboard

```bash
agr init
agr onboard
```

- `agr init` — `agr.toml` を作成し、既存ツール設定を検出
- `agr onboard` — ツール選択、スキル探索、移行、設定を対話形式で実行

### Main commands

| command | purpose |
| --- | --- |
| `agr add <handle>` | skill を追加 |
| `agr add -g <handle>` | global に追加 |
| `agr remove <handle>` | skill を削除 |
| `agr remove -g <handle>` | global から削除 |
| `agr sync` | `agr.toml` を同期 |
| `agr sync -g` | global dependency を同期 |
| `agr list` | installed skill を表示 |
| `agr list -g` | global skill を表示 |
| `agr init` | `agr.toml` を作成 |
| `agr init <name>` | 新しい skill を作成 |
| `agr onboard` | 対話形式で初期設定 |
| `agr config ...` | 設定を表示・変更 |
| `agrx <handle>` | skill を一時実行 |

詳細は **CLI / Skills Documentation** を参照してください。

---

## 3. KAFKA Evidence UI

高密度な dashboard、catalog、monitoring、公開データUI向けの evidence-first design system を同梱しています。

- [公開ショーケース](https://kafka2306.github.io/agent-resources/)
- [Design system skill](skills/kafka-evidence-ui/SKILL.md)
- [Agent plugin](plugins/kafka-evidence-ui/README.md)

Agent World の visual asset は表示専用です。状態・リンク・work item の正準データは dashboard snapshot 側から取得し、visual asset 自体へ operational truth を持たせません。

---

## Development / validation

Dashboard の主要QA:

```bash
pip install -r dashboard/requirements.txt
python -m unittest discover -s dashboard/tests -p 'test_*.py' -v
npm run test:dashboard
```

JavaScript syntax と visual asset manifest も GitHub Actions で検証されます。

Dashboard build の中心処理は次です。

```text
dashboard/collectors/*
        ↓
dashboard/build.py
        ↓
JSON Schema validation
        ↓
docs/dashboard/dashboard.json
        ↓
GitHub Pages
```

---

## Security

エージェントスキルは、AIツールへ実行手順や権限の使い方を与えるファイルです。追加・実行する前に、少なくとも次を確認してください。

- 配布元と repository owner
- `SKILL.md` の全文
- shell command、network access、file mutation の内容
- API key / secret へのアクセス要求
- 補助scriptと依存関係

信頼できない skill を、機密情報や書き込み権限がある環境で実行しないでください。

Dashboard 側も public-only boundary を前提にしています。private data を public snapshot へ混ぜないでください。

## License

[MIT License](LICENSE)

**README最終監査:** 2026-08-13
