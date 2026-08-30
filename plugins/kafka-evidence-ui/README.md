# Web UI改善Skill

KAFKA2306のDashboard、public Web、documentationを、現在のdata authorityとproduction behaviorを保ったまま改善するagent skillです。

正準手順は `skills/kafka-evidence-ui/SKILL.md` に置きます。plugin内のSkillは配布用コピーです。

## Contents

```text
.claude-plugin/plugin.json
.codex-plugin/plugin.json
skills/kafka-evidence-ui/SKILL.md
```

CSS token、component library、独自themeは配布しません。対象productの既存framework、theme、CSSを優先します。

## Claude Code

```text
/plugin marketplace add KAFKA2306/agent-resources
/plugin install kafka-evidence-ui@kafka-agent-tools
```

## Codex

対応surfaceではCodex / ChatGPT Plugin Directoryからpluginを導入します。

## agr

```bash
agr add KAFKA2306/agent-resources/kafka-evidence-ui
```

## Rule

current repositoryとproductionを直接確認し、実データ、状態の意味、evidence、accessibilityを維持します。visual変更のために新framework、独自UI分類、第二のCSS authorityを増やしません。
