# Dashboard agent contract

Dashboard変更では、長い過去会話を前提にしません。このファイルと変更対象だけを読み、現在のrepository / CI / production stateを直接確認してください。root `AGENTS.md` の一般規則も適用します。

## 最初に見るもの

変更理由に対応するファイルだけを読みます。

- 公開リンク: `config/public-links.json` → `collectors/public_links.py`
- live state: `live-core.js` / `../api/dashboard-live.js`
- browser overlay: `../docs/dashboard/live-overlay.js` / `../docs/dashboard/dashboard.js`
- Vercel route: `../vercel.json`
- 検証入口: `../scripts/validate_dashboard_contract.py` / `../.pre-commit-config.yaml`

履歴、closed Issue、過去PRは、現在stateだけでは判断不能な場合にだけ読みます。

## 壊してはいけない契約

1. GitHub Pagesで生成するsnapshotがbaselineです。Vercelでもbaselineを保持し、`/api/dashboard-live` は別経路のlive overlayです。
2. live stateでbaseline全体を置換しません。`publicLinks` などbaseline由来の情報を保持します。
3. 公開リンクの正準は `config/public-links.json` です。live APIやUIへ個別URLをhardcodeしません。
4. 同じ責務のfallback、config、snapshot、API、status authorityを増やしません。baselineが設計済みfallbackです。
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

- exact PR headでDashboard CIが成功
- 検証後にPR headが変わっていない状態でmerge
- merge SHAのVercel production deploymentがREADY
- `Verify Dashboard Release` が同じmerge SHAで成功
- 変更したproduction behaviorをbrowser E2Eが直接assertしている

この5点を満たさない場合は、どの層が未確認かを `UNVERIFIED` として残します。
