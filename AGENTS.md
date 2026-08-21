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

## Evidence scope

証拠は、それが実際に観測したclaimと実行layerにだけ適用します。

- 実機・editor・device・production環境が手元にないこと自体を、PR merge不可の理由にしません。実機が必要なclaimは `UNVERIFIED` のまま残し、repository-levelに安全に統合できるかを別に判断します。
- ただし変更対象そのものの安全性を、そのruntimeを実行しないと判断できず、誤りがmainを壊す可能性が高い場合は、その不確実性をPR merge blockerとして扱えます。単なる「環境がない」ではなく、変更surfaceに対する具体的riskを根拠にします。
- CI greenは、そのexact SHAで実際に走ったtest / build / lint / type check等が成功した証拠だけです。CIが実行していないeditor、device、browser、external API、production、release artifactの成功へ拡張しません。
- preview、deployment、runtime、production、release artifactの各claimは、該当する直接観測がある場合だけPASSとします。前段の成功から後段を推定しません。

したがって、次の2つを禁止します。

1. **「実機環境がないからコードをmergeできない」** — 実機未検証は対応するruntime claimを未確認にするだけで、無関係なrepository-level merge判定へ自動的に昇格させません。
2. **「CIが緑だから製品完成」** — CI successをrelease、production-ready、device-ready、user-readyの証拠として扱いません。

## Merge and release conditions

PR mergeとproduct releaseは別の判定です。

### PR merge

PR merge条件は、exact PR headに対して**変更したsurfaceをmainへ統合してよいこと**を示す証拠です。

- scopeと意図したcontractが明確である。
- 変更surfaceに対応する実行可能なdeterministic test / build / lint / type check / schema/data validationが成功している。
- exact PR headが検証後に変わっていない。
- secret、destructive operation、source/data integrity、重大なbackward compatibility defectを導入しない。
- 実行できなかったruntime / production / device claimは `UNVERIFIED` と明示され、release-readyと誤表示されない。

現在productionの状態、post-deploy smoke、release artifactの公開結果、手元にない実機の存在を、変更surfaceと無関係ならmerge条件にしません。

### Product release

Product release条件は、merge済みまたはtagged revisionから作られた**具体的なrelease対象**について、その製品claimを直接実証することです。

- release対象のexact revision / artifact identityが分かる。
- target environmentへ実際にdeploy / install / publishされている。
- releaseで謳うruntime / browser / device / integration / package behaviorを直接確認している。
- 必要なlicense、provenance、configuration、rollback/recovery boundaryを満たす。

PRがmerge済みでもproduct release完了とは扱いません。deployment成功だけでもproduction verificationが未実行ならrelease完了とは扱いません。production/runtime verificationの失敗はreleaseを未完了にしますが、その失敗が変更surfaceのrepository-level correctnessと無関係なら、過去のPR merge判定へ逆流させません。

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
4. mergeはexact PR headでPR merge条件を満たすことを確認し、可能ならexpected head SHAを固定する。product release条件をmerge判定へ混ぜない。
5. CI結果は、そのworkflowがexact SHAで実行したcheckの範囲だけに使う。CI greenを製品完成の代用にしない。
6. 実機/productionが利用不能なら対応claimを `UNVERIFIED` とし、利用不能そのものを自動merge blockerにしない。
7. host-side rejectionを認証失敗と決めつけず、stateを再取得して同じcanonical actionを1回だけ再試行する。2回目も拒否されたらそのrunのmutationを止める。
8. merge後はmain / PR / Issue / branchを再確認してからcleanupする。未完了branchを削除しない。
9. 未実行・未観測のtest、deployment、runtime layerをPASSと報告しない。

## Security

- credentialをbrowser bundle、public snapshot、fixture、log、docsへ入れない。
- external skillを実行する前にsource、`SKILL.md`、shell/network/file mutation、secret要求、helper dependencyを確認する。
- destructive actionや権限拡大は現在stateと明示的な意図を確認する。

## Primary references

- Agent Skills: https://agentskills.io/
- AGENTS.md: https://agents.md/

各tool固有仕様は必要時にそのtoolの現行公式documentationを参照し、このファイルへコピーしません。
