# Software Factory Control Tower agent contract

Control Tower変更では、長い過去会話を前提にしません。このファイルと変更対象だけを読み、現在のrepository / CI / production stateを直接確認してください。root `AGENTS.md` の一般規則も適用します。

## 最初に見るもの

変更理由に対応するファイルだけを読みます。

- 公開リンク: `config/public-links.json` → `collectors/public_links.py`
- static Dashboard data: `../docs/dashboard/dashboard.js` / `../docs/dashboard/factory-evidence.js`
- static snapshot generation: `collectors/` / `../docs/dashboard/*.json`
- Vercel route: `../vercel.json`
- 検証入口: `../scripts/validate_dashboard_contract.py` / `../.pre-commit-config.yaml`

履歴、closed Issue、過去PRは、現在stateだけでは判断不能な場合にだけ読みます。

## 壊してはいけない契約

1. `dashboard.json` と `factory-state.json` はPagesのworkflowが生成する静的machine snapshotです。VercelもPagesの同じsnapshotを表示します。
2. snapshotの値・`generatedAt`・`sourceRevision` をそのまま示し、表示時のcurrent stateと混同しません。current read-backのない値は `UNVERIFIED` です。
3. 公開リンクの正準は `config/public-links.json` です。各UIへ個別URLをhardcodeしません。
4. 同じ責務のsnapshot、API、status authorityを増やしません。Pages上の静的machine snapshotが公開stateの正本です。
5. CI successだけでproduction successとしません。merge後のVercel deploymentとproduction browser verificationを別に確認します。

## 検証

変更後はまず1コマンドでcontractを確認します。

```bash
python scripts/validate_dashboard_contract.py
```

commit前の全検証:

```bash
uvx pre-commit run --all-files --hook-stage pre-commit
```

push前のbrowser contract:

```bash
uvx pre-commit run --all-files --hook-stage pre-push
```

失敗をskip・mock・別fallbackで隠さず、失敗した正準経路を直します。

## 完了条件

- exact SHAのDashboard checksが成功
- mainへの反映後、PagesとVercel productionが同じ変更を配布
- Pages/Vercelのbrowser表示で静的snapshotの値・時刻・provenanceを確認
- current mainやproductionへの別途read-backがない限り、画面上のcurrent stateは `UNVERIFIED`

preview / non-production deploymentの`Verify Dashboard Release`成功はproduction完了の証拠にしません。

この条件を満たさない層は `UNVERIFIED` として残します。
