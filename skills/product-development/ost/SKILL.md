---
name: ost
description: Use one Opportunity Solution Tree workflow to define outcomes, discover opportunities, generate solutions, expose assumptions, and design experiments without separate phase skills.
---

# Opportunity Solution Tree

Use this as the single product-development skill. Outcome, opportunity, solution, and assumption discovery are phases of one workflow, not independent skills.

## Flow

1. Define the measurable outcome and the user or business behavior that must change.
2. Discover opportunities from evidence about user needs, pain points, constraints, and observed behavior. Do not turn proposed features into opportunities.
3. Generate multiple solutions only after the opportunity is explicit. Compare alternatives rather than committing to the first idea.
4. Expose the assumptions that must be true for each solution to work.
5. Prioritize the riskiest assumptions and define the smallest experiment or observation that can falsify them.
6. Update the tree as evidence changes. Remove branches that are no longer supported.

## Storage and CLI

When a persistent tree is useful, use the lightweight graph store at `.agr/ost.db` through `scripts/ost.py`; do not edit the database manually. Use the existing workspace, outcome, opportunity, solution, assumption, and show commands. Never invent node identifiers.

Load `references/outcomes.md`, `references/opportunities.md`, `references/solutions.md`, or `references/assumptions.md` only when that phase needs more detail.

## Output

Keep the result decision-oriented: selected outcome, evidence-backed opportunities, candidate solutions, critical assumptions, experiment or next action. Do not create product-strategy documents merely to satisfy the workflow.
