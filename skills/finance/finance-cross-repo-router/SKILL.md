---
name: finance-cross-repo-router
description: |
  KAFKA2306 の財務系リポジトリを横断し、重複した責務や依存関係の詰まりを見つけ、正本となる1つのリポジトリへ作業を振り分ける。
  財務データ、財務事実、モデル出力、公開物、release判断が複数リポジトリにまたがる場合に使う。
  リポジトリ内だけで完結する不具合修正や通常の機能実装には使わない。
---

# 財務リポジトリ横断ルーター

各データ、財務事実、モデル出力、公開判断の正本は1つだけにする。

## 最優先ルール

1. 現在の GitHub と公開状態を確認してから判断する。過去の会話や古い Issue を正本にしない。
2. 横断問題だけ扱う。リポジトリ内だけの問題は、そのリポジトリの agent へ渡す。
3. 正本を1つにする。重複した collector、validator、publisher、model、release 判断は削除か統合を優先する。
4. `DELETE > MERGE > REPLACE > ADD` を優先する。新しい管理層を増やさない。
5. 財務事実、評価、モデル入力、公開物は実データと一次情報を使う。欠損を推測で埋めない。
6. source、identity、period、unit、currency、runtime state が不足する場合は `UNVERIFIED` とする。silent fallback を作らない。
7. merge と release / publication / production は別状態として確認する。CI green を production PASS としない。
8. 同じ未解決問題について GitHub の状態が変わっていなければ no-op とし、Issue や comment を繰り返さない。

## 短いコンテキスト向け実行手順

長い履歴を読み込まなくても実行できるよう、毎回この順序だけを使う。

### 1. 対象を1つ決める

最初に、今回判断する対象を1つだけ選ぶ。

- dataset
- 財務事実
- model / evaluation output
- publication artifact
- release / production decision
- repository 間の依存関係

複数の問題が見つかった場合は、経済価値または投資判断への影響が最大の1件だけを先に扱う。

### 2. 最小限の現在状態を取得する

対象ごとに、必要なものだけ取得する。

- 関係する repository の default branch の現行実装
- open Issue / PR
- 直近の関連 merge
- 関係する workflow / config / schema / validator
- 公開物がある場合は production URL と read-back
- 財務判断に必要な場合だけ一次情報

長い Issue 履歴、全 PR、全 README、全 repository を最初から読まない。判断に必要になった時だけ追加取得する。

### 3. 5項目だけで所有権を判定する

対象について次だけ決める。

1. `object`: 何の正本か
2. `canonical_owner`: 現在の正本 repository
3. `conflicting_owner`: 同じ意味の責務を持つ他 repository。なければ none
4. `verified_state`: GitHub / canonical data / production で確認できた状態
5. `next_action`: 次に動く repository agent と1つの作業

この5項目が埋まらない場合は、推測せず `UNVERIFIED` とする。

### 4. 横断問題か判定する

次のどれかに該当する場合だけ横断問題として扱う。

- 同じ dataset の収集、検証、freshness、publish を複数 repository が所有している
- 同じ財務事実を複数 repository が正本として保存している
- 同じ model / evaluation output を複数 repository が生成している
- consumer が source repository を clone して第二の publisher になっている
- transport / cache repository が dataset 固有の意味や release 判断まで所有している
- repository 間の依存関係が未公開 artifact や未検証 state で止まっている
- finance 全体で必要な判断材料がどの repository にも正本として存在しない

該当しなければ no-op とする。

### 5. 次の1手だけ振り分ける

横断ルーター自身は repository-local implementation を抱えない。

- canonical owner に実装を寄せる
- conflicting owner から重複実装を削除する
- generic transport / cache は transfer、storage、hash、manifest など汎用機構だけを持つ
- consumer は canonical artifact / API を読む
- release / production verification は公開元 repository が担当する

複数の agent に同時に大きな作業を投げず、依存順に最小の次工程を1つ示す。

## 財務データと公開物のルール

- synthetic / fixture data は test 専用とし、本番 coverage や投資判断の代用にしない。
- source failure を成功扱いしない。
- 古い値へ無言で戻さない。
- 公式名称を使い、独自略語、独自分類、独自 workflow 名を増やさない。
- 各 finance repository の文書rootは `docs/` 1つだけにする。`documentation/`、`reports/`、`research/` などを並列の文書rootとして増やさず、文書なら `docs/` 配下へ統合する。repository直下の `README.md` と `AGENTS.md`、機械可読データ、code、公開Web実装はこの統合対象にしない。
- public Pages / Web site がある場合、README 冒頭に canonical production URL を `https://...` の完全URLで装飾なしの平文として置く。
- Cloudflare の公開 Web がある場合、deploy 済みだけで完了にしない。production read-back と Google 検索への実 index 確認を別状態として扱う。

## 完了確認

変更が必要な場合は、可能な範囲で次の順序を確認する。

`validation / test → PR → exact-head CI → merge → main read-back → release / publication / production read-back`

公開物では必要に応じて provenance、hash、source commit、公開URLを確認する。

確認できていない工程は `UNVERIFIED` と明記する。

## No-op

次の場合は成功した no-op とする。

- 横断責務の競合がない
- 問題が repository-local だけである
- 同じ未解決問題が既に記録され、関連する GitHub / publication state が変わっていない
- 文言だけが違い、実装上の正本が明確である

新しい Issue、PR、comment、tracker を作らない。

## 出力

短いコンテキストの agent でも同じ形式で返せるよう、次だけ報告する。

- 経済・意思決定インパクト
- Evidence
- Affected repositories
- Merge vs release / production
- 重複authorityの削除・統合
- Remaining UNVERIFIED
- Next repository agent/action

長い経緯の再説明、過去 run の要約、実装詳細の列挙はしない。

## 他 Skill との境界

repository 名が不明な場合だけ `repository-recall` を使って対象 repository を特定する。

repository が特定できた後の財務横断 ownership 判断はこの Skill が担当する。code review、repository-local implementation、release 実行は各 repository agent または対応 Skill に渡す。
