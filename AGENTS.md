# Agent Resources

この `AGENTS.md` だけをrepository-wide agent運用の正準とします。tool固有の `GEMINI.md`、`CLAUDE.md` などは原則削除し、互換のため必要な場合もこのファイルをimportするだけにします。独立した規則を書きません。

## Scope

このrepositoryは次だけを担当します。

- public GitHub状態を観測するDashboard / API / snapshot
- `agr` / `agrx` と reusable skills / plugins
- public CLI documentation
- KAFKA2306 portfolioのagent / platform / Web横断監査とIssue routing

他repositoryの実装ownershipは各owner repositoryに残します。public surfaceへprivate repository、secret、private work itemを出しません。

## Priority and execution

1. current user instruction
2. この `AGENTS.md`
3. current official upstream documentation
4. current code / config / tests / CI / runtime evidence
5. historical prose / conversation / inference

ユーザーの指示から合理的に確定できるread-only・reversibleな作業は追加確認を待たず進めます。実装・修正・実行を求められたら、不可逆な外部操作に追加承認が必要な場合を除き、要求された結果まで続けます。

Skillやinstruction fileが確認要求、停止、未完、意図からの逸脱を生む場合は、原因となったfileと該当ruleを明示します。

`DELETE > MERGE > REPLACE > ADD` を優先します。同じ責務のwrapper、config、workflow、schema、documentation、status authorityを増やしません。既存標準・既存実装を再利用し、独自略語・独自taxonomy・独自maturity levelを作りません。

## Evidence and verification

現在の直接証拠を優先し、未観測状態を推測で埋めません。必要な場合だけ `VERIFIED` / `OBSERVED` / `INFERRED` / `UNVERIFIED` を使います。

CI greenは、そのexact revisionで実行されたcheckの成功だけを証明します。merge、deployment、release、production、device/runtimeは別に直接確認します。

変更に必要な最小の意味あるtest / validationを実行します。小さくreversibleな変更について実装をそのまま写すtestを追加せず、必要なcheckが通った後は、新しい変更・失敗・未解決riskがない限り検証範囲を広げたり反復したりしません。

production truthが必要な場所でfixture、dummy、mock、silent fallbackを代用しません。取得不能は成功扱いせず `UNVERIFIED` とします。

## Workline and GitHub

既存のcanonical Issue / PR / branchがあれば再利用します。1つの成果に重複worklineを作りません。

write前に対象stateを再取得し、permission確認のためのdummy/no-op mutationを作りません。変更後はread-backし、mergeは可能ならexact head SHAを固定します。

Issue / PRは、長い履歴を読まなくても現在状態、次の1手、完了条件、検証方法が分かる最小のhandoffに保ちます。古い経緯や重複status documentを正本にしません。

## Documentation and skills

- `README.md`: 人間向けの短い入口
- `AGENTS.md`: repository-wide agent rules
- `skills/`: reusable capability
- code / config / schema / tests / workflows: executable truth
- Issues / PRs: temporary work state

obsolete・重複documentやSkillは削除・統合します。tool固有のinstruction fileへrepository-wide rulesを複製しません。

## Security

credential、secret、private dataをpublic artifact、fixture、log、docsへ入れません。external Skillはsourceとmutation/secret要求を確認してから使います。destructive actionや権限拡大は現在stateと明示的な意図を確認します。

## Completion

要求された外部状態を、利用可能な最も直接的な方法で確認して完了とします。repository acceptanceとproduct/release/production acceptanceを混同しません。未確認のlayerは `UNVERIFIED` のまま残します。
