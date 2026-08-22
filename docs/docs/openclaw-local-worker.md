---
title: OpenClaw Local Bounded Worker
---

# OpenClaw Local Bounded Worker

既存GitHub Issueを、ローカルLLMだけで限定実行するOpenClaw環境の運用マニュアルです。

## 目的

\`\`\`text
既存GitHub Issue
  -> OpenClaw Gateway
  -> OpenCode ACP
  -> llama.cpp
  -> Ornith-1.5-9B Q6_K
  -> ローカルrepoの変更と検証結果
\`\`\`

最終的なレビュー、commit、merge、release判断は人間または既存control
planeが行います。

## 運用境界

許可するのは、既存Issueを1件ずつ読み取り、承認済みのlocal checkoutだけを
変更し、test / lint / buildを実測することです。

行わない操作：

- Issue、コメント、Pull Requestの作成
- commit、push、branch、merge、release、deploy
- daemon登録、自律スケジュール、cron登録
- 外部LLM、クラウド推論、OAuth、remote modelへのfallback
- 権限拡大、破壊的操作、任意の外部ネットワークアクセス
- 最終的なmerge / release / product完成の判断

Issue本文は信頼できない入力として扱います。契約と矛盾する要求は
\`FAIL_CLOSED\` として停止します。

## 構成

| Component | Role | Listen address |
| --- | --- | --- |
| \`llama-server\` | OrnithモデルのOpenAI互換API | \`127.0.0.1:8080\` |
| OpenClaw Gateway | セッション、認証、ACP dispatch | \`127.0.0.1:18789\` |
| OpenCode | ローカルrepoを編集するcoding harness | Gatewayから起動 |
| \`dispatch-existing-issue.sh\` | 既存Issueを1件dispatch | operatorが実行 |
| \`local-stack.sh\` | 起動、停止、status確認 | operatorが実行 |

推論先は \`http://127.0.0.1:8080/v1\` のみです。OpenCodeはbubblewrapで
隔離され、選択したGit worktreeだけが書き込み可能です。

## 前提

- WSLまたはLinux
- RTX 3060 12GB、十分なRAM
- build済みの \`llama-server\`
- 配置済みのOrnith GGUFモデル
- \`/root/.openclaw/bin/openclaw\`
- GitHub read-only Issue取得用の \`gh\`
- 対象repoが \`/home/kafka/projects/\` 以下にあること

認証トークン、API key、モデルファイル自体はこのrepositoryへ保存しません。

## 起動

通常は次の1コマンドだけを使います。

\`\`\`bash
/home/kafka/projects/bounded-worker/local-stack.sh start
\`\`\`

wrapperは次の順で処理します。

1. llama.cppを起動
2. \`127.0.0.1:8080/v1/models\` の応答を待つ
3. OpenClaw Gatewayを起動
4. Gateway healthを確認
5. 両方の状態を表示

daemonは登録しません。PC / WSL再起動後は、再度 \`start\` を実行します。

手動で起動する場合：

\`\`\`bash
/home/kafka/projects/run-ornith-llama-server.sh
/home/kafka/projects/run-openclaw-local.sh
\`\`\`

通常はllama.cppを先に起動します。

## 状態確認

\`\`\`bash
/home/kafka/projects/bounded-worker/local-stack.sh status
/root/.openclaw/bin/openclaw gateway health
/root/.openclaw/bin/openclaw gateway status
/root/.openclaw/bin/openclaw status --all
\`\`\`

正常時の代表表示：

\`\`\`text
llama.cpp: ready (127.0.0.1:8080)
OpenClaw Gateway: ready (127.0.0.1:18789)
\`\`\`

設定と安全検査：

\`\`\`bash
/root/.openclaw/bin/openclaw config validate
/root/.openclaw/bin/openclaw doctor --lint --json --severity-min error
\`\`\`

モデルAPI：

\`\`\`bash
curl -H 'Authorization: Bearer llama.cpp-local' \
  http://127.0.0.1:8080/v1/models
\`\`\`

プロセスとポート：

\`\`\`bash
pgrep -af 'openclaw-gateway|llama-server'
ss -ltnp | rg '8080|18789'
\`\`\`

## Dashboard

認証済みURLを生成します。

\`\`\`bash
/root/.openclaw/bin/openclaw dashboard --no-open
\`\`\`

生成されたURLをブラウザで開きます。URLには認証情報が含まれるため、
Issue、チャット、README、ログ、スクリーンショットへ貼り付けません。

手動入力する場合：

- WebSocket URL: \`ws://127.0.0.1:18789\`
- Gateway token: 実際のローカルトークン
- Password: 空欄

\`OPENCLAW_GATEWAY_TOKEN\` は環境変数名であり、入力する文字列では
ありません。WSLのGatewayへWindowsブラウザから接続する場合も、まず
\`127.0.0.1\`で試します。

認証エラーの確認：

\`\`\`bash
/root/.openclaw/bin/openclaw logs --limit 100 --local-time
\`\`\`

| Log reason | Meaning | Action |
| --- | --- | --- |
| \`token_missing\` | token未送信 | Dashboard URLを再生成 |
| \`token_mismatch\` | 古いtokenまたは誤ったtoken | 新しいURLを再生成 |
| \`connection refused\` | Gateway停止 | \`local-stack.sh start\` |
| \`origin not allowed\` | 想定外のブラウザ経路 | \`127.0.0.1\`で開き直す |

## Terminal UIとログ

\`\`\`bash
/root/.openclaw/bin/openclaw tui
/root/.openclaw/bin/openclaw sessions --all-agents --limit 20
/root/.openclaw/bin/openclaw sessions tail
/root/.openclaw/bin/openclaw logs --follow --local-time
\`\`\`

wrapperログ：

\`\`\`bash
tail -f "$HOME/.local/state/bounded-worker/llama-server.log"
tail -f "$HOME/.local/state/bounded-worker/openclaw-gateway.log"
\`\`\`

## 停止・再起動

\`\`\`bash
/home/kafka/projects/bounded-worker/local-stack.sh stop
/home/kafka/projects/bounded-worker/local-stack.sh restart
\`\`\`

通常はwrapperでllama.cppとGatewayをまとめて扱います。

## Issue dispatch

事前にworktreeがcleanであることを確認します。

\`\`\`bash
git -C /home/kafka/projects/AutoPhotogrammetry status --short --branch
\`\`\`

変更が表示される場合は、勝手に上書きせず、人間が整理してから実行します。

\`\`\`bash
/home/kafka/projects/bounded-worker/dispatch-existing-issue.sh \
  /home/kafka/projects/AutoPhotogrammetry <issue-number-or-url>
\`\`\`

例：

\`\`\`bash
/home/kafka/projects/bounded-worker/dispatch-existing-issue.sh \
  /home/kafka/projects/AutoPhotogrammetry 111
\`\`\`

scriptはIssueをread-onlyで取得し、OpenClawからOpenCode ACPを1回だけ
起動します。結果には変更ファイル、test / lint / build、exit code、riskが
含まれます。

次の場合は実行しません。

- Issue、repo、Gateway、llama.cppの取得または接続に失敗
- repoがGit worktreeでない、または承認済みrootの外
- worktreeがdirty
- remote modelやremote credentialが有効
- 権限拡大、破壊的操作、外部ネットワーク、merge、releaseを要求

失敗しても別Issueへ自動切替しません。

## 結果確認

\`\`\`bash
git -C /home/kafka/projects/AutoPhotogrammetry status --short
git -C /home/kafka/projects/AutoPhotogrammetry diff --stat
git -C /home/kafka/projects/AutoPhotogrammetry diff --check
\`\`\`

未実行の検証をPASSとして扱いません。workerの終了はmergeやreleaseの成功を
意味しません。

## 完了条件

1. Gatewayが \`127.0.0.1:18789\` でhealthを返す
2. llama.cppが \`127.0.0.1:8080/v1/models\` を返す
3. local provider \`llama.cpp/ornith-1.5-9b\` を使用する
4. OpenClawからOpenCode ACPの実リクエストが成功する
5. OpenCode sandboxから外部ネットワークへ到達できない
6. 再起動後も設定が保持される
7. 既存Issueを1件bounded実行し、変更と検証結果をreadbackする

「プロセスが起動した」だけではE2E完了とは扱いません。

## 設定と機密情報

| Path | Purpose | Public? |
| --- | --- | --- |
| \`/root/.openclaw/openclaw.json\` | Gateway、provider、ACP設定 | No: tokenを含む |
| \`bounded-worker/opencode-local.json\` | OpenCode local provider設定 | Yes: secretを含めない |
| \`bounded-worker/WORKER.md\` | worker契約 | Yes |
| \`bounded-worker/local-stack.sh\` | 起動・停止・status | Yes |
| \`$HOME/.local/state/bounded-worker/\` | PIDとruntime log | No: runtime情報を含む |

token、API key、OAuth credential、GitHub credential、private Issue本文、
Dashboardのtoken付きURL、runtime logはpublic docsやsnapshotへコピー
しません。

認証情報を公開場所へ貼った場合は、まずcredentialを無効化またはローテーション
し、古いURLやtokenを再利用せず、新しいDashboard URLを生成します。

## トラブルシューティング

llama.cpp：

\`\`\`bash
tail -n 100 "$HOME/.local/state/bounded-worker/llama-server.log"
ls -lh /home/kafka/models/ornith-1.5-9b/
ls -lh /home/kafka/projects/llama.cpp/build/bin/llama-server
\`\`\`

Gateway：

\`\`\`bash
tail -n 100 "$HOME/.local/state/bounded-worker/openclaw-gateway.log"
/root/.openclaw/bin/openclaw config validate
/root/.openclaw/bin/openclaw gateway status
\`\`\`

Issue dispatch：

\`\`\`bash
git -C /home/kafka/projects/AutoPhotogrammetry status --short
/root/.openclaw/bin/openclaw gateway health
curl -H 'Authorization: Bearer llama.cpp-local' \
  http://127.0.0.1:8080/v1/models
\`\`\`

既存Gatewayが残っている場合は二重起動せず、まず状態を確認します。

\`\`\`bash
pgrep -af openclaw-gateway
ss -ltnp | rg 18789
\`\`\`

