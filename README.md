# agent-resources（agr）— AIエージェント用スキル管理CLI

**ドキュメント・公開ページ:** https://kafka2306.github.io/agent-resources/

`agr`は、GitHub上のエージェントスキルを、Claude Code、Codex、Cursor、OpenCode、GitHub Copilot、Antigravityなどのスキルディレクトリへ導入するCLIです。

`agrx`を使うと、スキルを恒久インストールせず、一時的に取得・実行・削除できます。

## インストール

```bash
pip install agr
```

最初のスキルを追加する例:

```bash
agr add anthropics/skills/frontend-design
```

リモートから取得する場合は、ローカル環境に`git`が必要です。

## 主な機能

- GitHubまたはローカルディレクトリからスキルを追加
- プロジェクト単位またはユーザー全体へインストール
- `agr.toml`による依存スキルの共有
- 複数ツールのスキル配置先を自動検出
- スキルの追加、削除、一覧、同期
- 新しい`SKILL.md`テンプレートを生成
- `agrx`による一時実行
- 対話形式の初期設定

## スキルを追加する

```bash
agr add anthropics/skills/frontend-design
agr add -g anthropics/skills/frontend-design
agr add anthropics/skills/pdf anthropics/skills/mcp-builder
agr add anthropics/skills/pdf --source github
```

### ハンドル形式

```text
username/skill-name
username/repo/skill-name
./path/to/skill
```

- `username/skill-name` — ユーザーの標準`skills`リポジトリから取得
- `username/repo/skill-name` — リポジトリを明示して取得
- `./path/to/skill` — ローカルディレクトリから追加

2要素形式は、標準で`skills`という名前のリポジトリを参照します。移行期間中は、見つからない場合に`agent-resources`を確認し、警告を表示する実装です。

## 一時実行する

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/skill-creator -i
agrx anthropics/skills/pdf --tool cursor
```

`agrx`はスキルを一時的に取得して実行し、終了後にクリーンアップします。

## チームで同期する

依存スキルは`agr.toml`へ記録します。

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/brand-guidelines", type = "skill"},
]
```

他のメンバーは次を実行します。

```bash
agr sync
```

ユーザー全体の依存関係を同期する場合:

```bash
agr sync -g
```

## 新しいスキルを作る

```bash
agr init my-skill
```

生成される基本形:

```markdown
---
name: my-skill
description: What this skill does.
---

# My Skill

Instructions for the agent.
```

このリポジトリへ追加する場合は`skills/`配下へ配置します。

ローカル検証:

```bash
agr add ./skills/my-skill
```

GitHubへ公開すると、他の利用者は次の形式で取得できます。

```bash
agr add your-username/my-skill
```

## リポジトリを初期化する

```bash
agr init
agr onboard
```

- `agr init` — `agr.toml`を作成し、既存のツール設定を検出
- `agr onboard` — ツール選択、スキル探索、移行、設定を対話形式で実行

## コマンド一覧

| コマンド | 内容 |
| --- | --- |
| `agr add <handle>` | スキルを追加 |
| `agr add -g <handle>` | ユーザー全体へ追加 |
| `agr remove <handle>` | スキルを削除 |
| `agr remove -g <handle>` | ユーザー全体から削除 |
| `agr sync` | `agr.toml`の依存関係を同期 |
| `agr sync -g` | グローバル依存関係を同期 |
| `agr list` | インストール済みスキルを表示 |
| `agr list -g` | グローバルスキルを表示 |
| `agr init` | `agr.toml`を作成 |
| `agr init <name>` | 新しいスキルを作成 |
| `agr onboard` | 対話形式で初期設定 |
| `agr config ...` | 設定を表示・変更 |
| `agrx <handle>` | スキルを一時実行 |

## KAFKA Evidence UI

高密度なダッシュボード、カタログ、監視画面、公開データUI向けの証拠優先デザインシステムを同梱しています。

- [公開ショーケース](https://kafka2306.github.io/agent-resources/)
- [デザインシステム・スキル](skills/kafka-evidence-ui/SKILL.md)
- [エージェントプラグイン](plugins/kafka-evidence-ui/README.md)

## `npx skills`との違い

`agr`のハンドルは、リポジトリ全体ではなく、具体的なスキルを指定します。

| 目的 | npx skills | agr |
| --- | --- | --- |
| リポジトリ内のスキル | `npx skills add owner/repo` | `agr add owner/repo/skill-name` |
| 標準リポジトリ内のスキル | — | `agr add owner/skill-name` |

2要素形式で見つからない場合は、対応するリポジトリを確認し、利用可能なハンドル候補を提示します。

## セキュリティ上の注意

エージェントスキルは、AIツールへ実行手順や権限の使い方を与えるファイルです。追加・実行する前に、必ず次を確認してください。

- 配布元とリポジトリ所有者
- `SKILL.md`の全文
- シェルコマンド、ネットワーク通信、ファイル変更の内容
- APIキーや秘密情報へのアクセス要求
- 追加される補助スクリプトや依存関係

信頼できないスキルを、機密情報や書き込み権限がある環境で実行しないでください。

## ライセンス

[MIT License](LICENSE)

**README最終監査:** 2026-08-01
