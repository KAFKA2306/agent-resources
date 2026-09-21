---
title: Home
---

# Software Factory Control Tower

KAFKA2306 のソフトウェア運用を、自律的に work を発見し、修復し、検証し、production まで流す **software factory** として管理するための公開ドキュメントです。

公開UIは [Software Factory Control Tower](https://agent-resources-one.vercel.app/) です。

## 何を変えるのか

従来の運用は、人が Issue を選び、ログを読み、rerunし、mergeし、deployする流れでした。Software Factory は、その routine operation を閉ループ化します。

~~~text
observe
→ discover work
→ classify / prioritize / route
→ execute
→ verify
→ repair / re-verify
→ merge
→ release / deploy
→ production probe
→ rollback or fix-forward
→ close
→ learn
~~~

成功条件は「agentが何体動いたか」ではありません。中心指標は **routine human intervention = 0** です。

## 2つの公開面

### Control Tower

工場全体の状態を監査する画面です。Issue、PR、Actions、deployment、production evidence を横断し、どこが動いていて、どこが止まり、どの証拠に基づくかを確認します。

[Control Tower の設計を読む](control-tower.md)

### AGR CLI / Skills

`agr` / `agrx` は AI agent skills を導入・共有・一時実行するためのCLIです。

~~~bash
uv tool install git+https://github.com/KAFKA2306/agent-resources.git
agr add anthropics/skills/frontend-design
agrx anthropics/skills/pdf
~~~

[AGR CLI を使う](cli.md)

## 原則

- Control Tower 自体を第二の正本にしない
- canonical evidenceへ戻れることを優先する
- missing / unknown evidenceを成功扱いしない
- routine failureを人間待ちにせず修復ループへ戻す
- retryはboundedにし、同じ失敗を無限再実行しない
- private stateやsecretを公開面へ出さない

## 次に読む

- [Software Factory Control Tower](control-tower.md)
- [AGR CLI](cli.md)
- [Creating Skills](creating.md)
- [CLI Reference](reference.md)
