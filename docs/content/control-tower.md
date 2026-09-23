---
title: Software Factory Control Tower
---

# Software Factory Control Tower

Software Factory Control Tower は、自律ソフトウェア工場の **観測面** です。工場を手動操作するためのタスク一覧ではなく、閉ループ運転が成立しているかを人間が監査するために使います。

## Role

Control Tower が答えるべき質問は次の通りです。

- 今どの工程が動いているか
- どこで滞留しているか
- 失敗は自動修復されたか
- 人間介入が発生したか
- merge / deploy / production verificationまで完走したか
- その判断はどのcanonical evidenceに基づくか

## Factory flow

~~~text
Observe
  ↓
Discover Work
  ↓
Classify / Prioritize
  ↓
Route
  ↓
Execute
  ↓
Independent Verify
  ↓
Repair ───────┐
  ↓            │
Re-verify ◀────┘
  ↓
Merge
  ↓
Release / Deploy
  ↓
Production Probe
  ↓
Rollback / Fix-forward when needed
  ↓
Close / Learn
~~~

Dashboardという名前の内部ディレクトリやAPIは互換性のため残しますが、公開製品名は **Software Factory Control Tower** です。

## Authority model

Control Tower は中央status DBを新設しません。状態の正本は既存authorityです。

| Layer | Canonical evidence |
|---|---|
| Work | owner repository / Issue / PR |
| Verification | Actions / Checks / exact revision |
| Merge | GitHub merge state |
| Artifact | workflow run / checksum / provenance / attestation |
| Deploy | deployment provider |
| Runtime | canonical production / active probe |
| Cross-repo view | Control Tower |

Control Towerのsnapshotやlive overlayは、これらを観測して表示するread modelです。

## Evidence states

| State | Meaning |
|---|---|
| `LIVE` | live endpointから現在値を取得できた |
| `SNAPSHOT` | 生成済みbaselineを表示している |
| `STALE` | データは存在するがfreshness条件を満たさない |
| `UNVERIFIED` | 必要な証拠が不足し、成功を確認できない |
| `PASS` | 必須evidenceがexact revisionで成功 |
| `FAIL` | 必須evidenceが明示的に失敗 |

`UNVERIFIED` を `PASS` に昇格させません。

## North-star metrics

### Zero-human

- routine human intervention count / rate
- human wait time
- manual rerun / merge / deploy / restart
- manual model/provider replacement

routine human intervention が発生したら、それ自体を automation gap として次の改善workへ戻します。

### Yield

- first-pass yield
- final success rate
- complete E2E yield
- CI → artifact → deploy → production verification conversion

### Lead time

- discovery → start
- start → PR
- PR → merge
- merge → deploy
- deploy → production verified
- total p50 / p95

### Recovery

- self-heal success rate
- retry count
- failure recurrence
- provider failover success
- runner recovery success
- rollback / fix-forward success

## Failure handling

失敗を赤く表示して終わりにはしません。

~~~text
failure
→ fingerprint
→ known remediation ?
   yes → deterministic remediation
   no  → diagnosis / repair agent
→ independent verifier
→ bounded retry
→ success or terminal classification
~~~

CI、build、unsupported model、provider outage、runner unavailable、merge conflict、artifact failure、deployment failure、production probe failureなどは routine repair targetです。

法的判断、契約、初回外部認証、現実世界の不可逆操作など、機械側にauthorityがないものだけを human-only exception とします。

## Current public architecture

~~~text
GitHub repositories / Actions / PRs
          │
          ├─ snapshot collectors → generated baseline
          │
          └─ live API → live overlay
                         │
                         ▼
              Software Factory Control Tower
                         │
                         ▼
                 canonical evidence links
~~~

baseline は GitHub Pages でも利用できるfallbackです。live stateでbaseline全体を置換せず、liveで取得できた範囲だけをoverlayします。

## Boundaries

- public surfaceにprivate repositoryやsecretを出さない
- Control Towerからowner repositoryの実装ownershipを奪わない
- UI座標や表示都合をcanonical work stateへ逆流させない
- CI greenだけでproduction successとみなさない
- silent provider downgradeやinfinite retryを行わない

## Source

- [Repository](https://github.com/KAFKA2306/agent-resources)
- [Control Tower](https://agent-resources-one.vercel.app/)
- [Issue #381: Autonomous Factory](https://github.com/KAFKA2306/agent-resources/issues/381)
