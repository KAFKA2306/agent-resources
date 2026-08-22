---
title: OpenClaw Local Autonomous Worker
---

# OpenClaw Local Autonomous Worker

OpenClaw / OpenCode / llama.cpp を使い、GitHub Issue の backlog をローカルLLMだけで継続処理する自律 coding worker の運用契約です。

通常運用では人間の dispatch、commit、PR作成、merge判断を要求しません。常駐 supervisor が対象Issueの選択から検証、GitHub反映、次Issueへの遷移までを行います。

## 目的

```text
GitHub open Issues
  -> autonomous supervisor daemon
  -> isolated Git worktree
  -> OpenClaw Gateway
  -> OpenCode ACP
  -> llama.cpp
  -> Ornith-1.5-9B Q6_K
  -> code change
  -> test / lint / build
  -> commit / push / Pull Request
  -> exact-SHA CI verification
  -> merge
  -> branch/worktree cleanup
  -> next Issue
```

release / deploy についても、人間の承認を最終gateにはしません。対象repositoryに既存の実行可能なrelease pathと直接検証手段がある場合は、merge後にそれを実行・観測します。release pathが定義されていないrepositoryでは、releaseを推測して新設せず、mergeをそのrunの終端とします。

## 自律化の境界

workerは次を自動実行します。

- 許可されたrepository群からopen Issueを取得する
- deterministicに次のIssueを選ぶ
- default branchを同期し、Issue専用worktree / branchを作る
- Issue本文を入力としてOpenCodeを実行する
- test / lint / build / schema validation等、repositoryで実行可能な検証を実測する
- 変更をcommit / pushする
- Pull Requestを作成または既存canonical PRを更新する
- exact PR head SHAに紐づくCIを監視する
- repositoryのmerge条件を満たしたPRをexpected head SHA付きでmergeする
- merge / close後のhead branchと一時worktreeを削除する
- release / deploy pathが既に定義されていれば実行し、対応するruntime / production結果を直接確認する
- 成功・失敗状態をlocal stateへ保存し、次のIssueへ進む

人間の承認待ちを通常状態にしません。

ただし完全自律は無制限実行を意味しません。次は自動化対象外です。

- allowlist外repositoryへの書き込み
- branch protectionやrequired checkの無効化・回避
- protected/default branchへのforce pushやhistory rewrite
- credential、token、private dataのrepository / log / Issueへの書き出し
- coding sandboxからの任意外部ネットワークアクセス
- Issue本文の指示だけを根拠にした権限拡大
- repositoryに既存のrelease contractがない状態での推測によるrelease手順の新設・実行

Issue本文は信頼できない入力として扱います。policy違反のIssueはそのIssueだけ失敗状態として記録し、daemon全体は停止せず次のeligible Issueへ進みます。

## Component

| Component | Role | Lifetime |
| --- | --- | --- |
| `llama-server` | OrnithモデルのOpenAI互換API | daemon |
| OpenClaw Gateway | session / auth / ACP dispatch | daemon |
| autonomous supervisor | Issue選択、worktree、GitHub state machine、retry | daemon |
| OpenCode | 1 Issueのローカルrepo編集 | one-shot |
| GitHub Actions | PR headのrepository-level検証 | per PR |

推論先は `http://127.0.0.1:8080/v1` のlocal providerだけを使用します。coding processは選択したworktreeだけを書き込み可能にし、外部ネットワークを遮断します。GitHub APIへのread/writeはcoding processではなくsupervisor側だけに持たせます。

## 起動モデル

3つの長寿命processをsystemdで常駐させます。

```text
llama-server.service
        |
        v
openclaw-gateway.service
        |
        v
openclaw-autonomous-worker.service
```

通常運用はsystemdに任せます。

```bash
systemctl --user enable --now llama-server.service
systemctl --user enable --now openclaw-gateway.service
systemctl --user enable --now openclaw-autonomous-worker.service
```

serviceは異常終了時に再起動し、PC / WSL再起動後にも復帰する構成にします。login sessionがなくてもuser serviceを起動し続ける必要がある環境では、systemdのlingerを有効にします。

```bash
loginctl enable-linger "$USER"
```

`local-stack.sh start` を毎回手動実行する運用は正準にしません。手動start / stopは保守・debug用だけに残します。

## Supervisor state machine

supervisorは1 Issueずつ次のstate machineを実行します。

```text
DISCOVER
  -> SELECT
  -> PREPARE_WORKTREE
  -> EXECUTE
  -> VERIFY_LOCAL
  -> COMMIT
  -> PUSH
  -> OPEN_OR_UPDATE_PR
  -> WAIT_CI
  -> MERGE
  -> VERIFY_RELEASE_IF_DEFINED
  -> CLEANUP
  -> DISCOVER
```

### DISCOVER / SELECT

対象は明示的なrepository allowlist内のopen Issueだけです。

同じIssueを二重実行しないため、次は除外します。

- 現在active lockを持つIssue
- 同じIssue用のopen canonical PRがあるもの
- local stateでretry待ちになっているもの
- policy違反として記録済みで、入力が更新されていないもの

複数候補がある場合は、repository側に明示されたpriority情報があればそれを使い、なければ古いeligible Issueから選択します。LLMの自由判断だけで優先順位を作りません。

### PREPARE_WORKTREE

共有checkoutを直接編集しません。default branchの最新SHAからIssue専用worktreeを作ります。

branch名はrepository内で一意かつ再利用可能なdeterministic名にします。既存canonical branch / PRがあれば新規に増やさず再利用します。

### EXECUTE

Issue本文、repository instruction、現在のcode/configをOpenCodeへ渡します。OpenCodeはそのIssueのworktreeだけを変更できます。

LLMはlocal llama.cpp providerだけを使用し、remote modelへのfallbackは行いません。

### VERIFY_LOCAL

変更surfaceに対応するrepository既存のtest / lint / build / type check / schema validationを実行します。

未実行の検証をPASSとして扱いません。検証失敗時は失敗内容をstateへ保存し、同一入力に対する無限再実行を避けて次のIssueへ進みます。

### COMMIT / PUSH / PR

local verificationを通過した変更だけをcommitします。

supervisorはGitHub write credentialを使ってbranchをpushし、canonical PRを作成または更新します。既存PRがある場合はduplicate PRを作りません。

### WAIT_CI / MERGE

merge判定はPRのexact head SHAに対して行います。

- required checksが成功している
- merge conflictがない
- head SHAが検証後に変わっていない
- repository固有のmerge条件を満たす
- branch protectionを回避していない

条件を満たしたらexpected head SHAを固定してmergeします。人間レビューをrepository設定が必須としていない限り、人間承認を追加gateにはしません。

CI失敗時はPRを勝手に成功扱いせず、失敗原因を次のrepair runの入力にします。修正可能なら同じcanonical branchへ追加commitし、再度exact SHAでCIを確認します。

### VERIFY_RELEASE_IF_DEFINED

mergeとreleaseは別stateです。

repositoryに既存のrelease / deploy workflowがあり、実行条件とverification targetが明示されている場合だけ自動実行します。

```text
merge success
  -> deploy / publish / package
  -> runtime / production / artifact verification
  -> release success or release failure
```

CI greenをrelease成功の代用にしません。deployment成功だけでも、production/runtime verificationが必要な製品では完了扱いしません。

### CLEANUP

PRがmergeまたはcloseされたらhead branchと一時worktreeを削除します。

cleanup後にbranch一覧とworktree一覧をread-backし、orphanが残っていないことを確認してから次のIssueへ進みます。

## Retryと継続運転

1件の失敗でdaemon全体を停止しません。

- llama.cpp / Gateway / GitHub APIなど一時障害: backoffして再試行
- local test failure: state保存後、次Issueへ進む
- CI failure: 同一PRのrepair runへ戻す
- merge conflict: default branchを再同期して同じcanonical worklineで解消を試みる
- policy違反: Issue入力が変わるまで再実行しない
- release verification failure: merge済み状態は維持し、releaseを失敗状態として保存する

無限loopを避けるため、同一Issue・同一入力hash・同一失敗原因へのretry回数と次回実行時刻をstateへ保持します。

## 状態保存

runtime stateはrepositoryへcommitしません。

```text
$HOME/.local/state/openclaw-autonomous-worker/
  state.json
  locks/
  runs/
  logs/
```

少なくとも次を保存します。

- repository / issue number / issue updated_at
- issue input hash
- branch / PR / head SHA
- current state
- local validation結果
- CI結果
- merge SHA
- release / production verification結果
- retry count / next retry time
- last error

credential、Issueのprivate本文、Dashboard token付きURLはstate snapshotやpublic docsへ複製しません。

## Health check

```bash
systemctl --user status llama-server.service
systemctl --user status openclaw-gateway.service
systemctl --user status openclaw-autonomous-worker.service

curl -H 'Authorization: Bearer llama.cpp-local' \
  http://127.0.0.1:8080/v1/models

/root/.openclaw/bin/openclaw gateway health
/root/.openclaw/bin/openclaw status --all
```

supervisorはprocess aliveだけでhealthyとしません。少なくとも次を監視します。

- llama.cpp model APIが応答する
- Gateway healthが成功する
- supervisor heartbeatが更新される
- active runのstateが一定時間以上停止していない
- GitHub APIへ必要なread/writeが可能

## 観測

```bash
journalctl --user -u llama-server.service -f
journalctl --user -u openclaw-gateway.service -f
journalctl --user -u openclaw-autonomous-worker.service -f
```

Dashboard / TUIは保守用です。

```bash
/root/.openclaw/bin/openclaw dashboard --no-open
/root/.openclaw/bin/openclaw tui
/root/.openclaw/bin/openclaw sessions --all-agents --limit 20
```

Dashboard URLに含まれる認証情報はIssue、README、log、screenshotへ貼りません。

## 完了条件

完全自律化の完了は、daemon登録だけではなくE2Eで判定します。

1. `llama-server` が再起動後も自動復帰する
2. OpenClaw Gatewayが再起動後も自動復帰する
3. autonomous supervisorが再起動後も自動復帰する
4. supervisorが人間操作なしでopen Issueを取得・選択する
5. Issue専用worktreeでOpenCodeを1回以上実行する
6. local test / lint / build結果を実測する
7. 成功した変更を自動commit / pushする
8. canonical PRを自動作成または更新する
9. exact PR head SHAのCI結果を自動確認する
10. merge条件を満たしたPRを自動mergeする
11. merge / close後にhead branchとworktreeを自動削除する
12. release pathが定義されたrepositoryではreleaseと直接verificationまで自動実行する
13. 失敗Issueがあってもdaemonが次のeligible Issueへ進む
14. coding sandboxから任意外部ネットワークへ到達できない
15. remote LLM fallbackが無効である

「processが起動した」「1件dispatchできた」「PRを作った」だけでは完全自律化完了とは扱いません。

## 現在の証拠境界

このrepositoryの文書更新だけでは、対象PC / WSL上のsystemd service、local supervisor、GitHub credential、実際のE2E runが稼働していることまでは証明しません。

runtime完成判定は上記15条件を対象host上で直接確認した時点で行います。repository-levelでは、この文書を以後の正準運用契約とします。
