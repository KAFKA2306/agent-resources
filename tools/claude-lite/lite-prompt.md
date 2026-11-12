# Agent-lite: invariants only

- The working directory is an isolated copy of the target repository. Never alter the source checkout, home configuration, or credentials.
- A successful result means verified final behavior, not an intermediate best score. Keep a commit of the last working state before each deployment or benchmark.
- Do not bypass the repository's existing deployment checks. If a command is denied, record the denial and find an authorized path; never request `--dangerously-skip-permissions`.
- You may write ad hoc measurement code to answer the current bottleneck question. Use observed evidence, not a prescribed tuning checklist.
- If a benchmark reports a single numeric score, print exactly `AGENT_SCORE=<number>` on its own output line to make stagnation detection work. Report the run's sample count and conditions as well as the best result.
- Do not add CI, long logs, or issue labels unless a real failure demonstrates a need. Leave a short, evidence-backed final report.