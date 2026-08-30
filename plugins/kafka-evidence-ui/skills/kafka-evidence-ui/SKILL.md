---
name: kafka-evidence-ui
description: Audit and improve information-dense Web UI while preserving current data authority, semantics, production behavior, accessibility, and existing frontend architecture. Use for dashboards, public Web operations, documentation, catalogs, and monitoring interfaces.
---

# Web UI改善

現在のproductionとrepositoryを直接確認し、利用者が状態を理解し、必要な項目を見つけ、証拠を確認し、次の操作へ進むまでの負荷を下げます。

## 最初に確認するもの

1. current productionをdesktop / mobile幅で確認する。
2. READMEだけで判断せず、HTML、CSS、JavaScript、component、docs source、test、deploymentを確認する。
3. 表示値はcanonical production / real dataを使う。fixtureやsampleをproduction評価の代用にしない。
4. source、freshness、failure、unavailable、owner、evidence、primary actionの現在の意味を確認する。

## 変更方針

- 現在のdata schema、API、collector、backend、CIをdesign都合で作り直さない。
- 既存framework、theme、CSS、native HTMLを優先する。新frameworkやcomponent libraryを追加しない。
- `DELETE > MERGE > REPLACE > ADD` を優先し、古いCSS、重複style、不要な装飾を残さない。
- 一般的な用語で十分な場合、独自のmode、status分類、component分類、workflow名を作らない。
- 色だけで状態を伝えず、文字でも意味を示す。
- gradient、glow、particle、過剰なshadow、不要なanimationを標準にしない。
- responsive layoutとkeyboard操作を後付けにしない。

## Operations / Dashboard

利用者が短時間で次を判断できる順に情報を置きます。

1. 現在のscopeとfreshness
2. failure / waitingなど対応が必要な状態
3. owner repositoryと理由
4. evidence
5. primary action
6. 全件を比較する詳細view

大量比較にtableが適する場合はtableを残します。first viewportのすべてをcardへ変換しません。

## Documentation

Markdown等のcanonical本文とpresentationを分離します。

- command、URL、file path、version、number、warning、limitation、code sampleをvisual変更のために書き換えない。
- 本文幅、heading spacing、table、code block、note / warning、navigation、focus、printを既存theme / CSSで改善する。
- code blockはcommandを壊すwrapを避け、copy可能性を維持する。
- 長いpageでは既存themeの目次機能を優先する。

## Accessibility

- semantic HTMLとnative controlを優先する。
- interactive elementはkeyboardで到達可能にする。
- `:focus-visible` を明確にする。
- 状態変更に必要な既存の`aria-*` semanticsを維持する。
- `prefers-reduced-motion`を尊重する。
- mobileで主要操作がhorizontal scrollだけに依存しないようにする。

## 検証

変更前後を同じ実taskで比較します。

- 対応が必要な項目を見つける。
- ownerを特定する。
- waiting / failure理由を読む。
- evidenceへ移動する。
- primary actionを開く。
- freshness / unavailable / failureを区別する。
- mobile幅とkeyboardでも同じ操作を行う。

変更後はrepositoryの既存test / build / browser verificationを実行し、PRのexact head CI、merge後main、関係するdeployment / productionまで確認します。CI successだけでproduction successとしません。

## 完了時の報告

material deltaだけを残します。

- Before → After
- 変更したfile
- 削除 / 統合したstyleやauthority
- exact-head CI
- merge revision
- deployment / production verification
- 未確認のlayer
