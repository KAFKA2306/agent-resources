# Unity and VRChat verification evidence

Use this record when a repository claims that Unity or VRChat validation was performed. Record only observed execution facts. Do not infer success for a layer that did not run.

## Required record

```json
{
  "repository": "KAFKA2306/example",
  "commit_sha": "<40-character Git commit SHA>",
  "unity_version": "2022.3.22f1",
  "packages": [
    {
      "name": "com.vrchat.worlds",
      "version": "<observed version>"
    }
  ],
  "environment": {
    "runner": "<runner or machine>",
    "operating_system": "<observed OS>"
  },
  "started_at": "<ISO 8601 timestamp>",
  "completed_at": "<ISO 8601 timestamp>",
  "checks": [
    {
      "name": "<plain description of the check>",
      "result": "success",
      "command": "<exact command, when applicable>",
      "exit_code": 0,
      "artifacts": ["<NUnit XML, Editor log, workflow artifact, or runtime evidence URL/path>"],
      "reason": null
    },
    {
      "name": "Edit Mode tests",
      "result": "not run",
      "command": null,
      "exit_code": null,
      "artifacts": [],
      "reason": "<plain reason the check did not run>"
    }
  ]
}
```

`result` is limited to `success`, `failure`, or `not run`. A precondition failure must leave later checks as `not run`; it must not be promoted to either success or failure for an unexecuted layer.

## Evidence rules

- Record the exact Git commit SHA, Unity version, relevant VPM/package versions, execution environment, timestamps, exact command where applicable, process exit code, and evidence artifact paths or URLs.
- Source inspection, package inspection, and static checks are evidence only for those checks. They do not prove that the Unity Editor ran.
- For Unity Test Framework runs, preserve the NUnit XML and Editor log. Interpret the outcome from the executed tests and their reports; do not use a process exit code alone as proof of individual test success.
- Keep Edit Mode, Play Mode, ClientSim, VRChat Build & Test, multi-client/network behavior, upload, and real VRChat client/device evidence separate. Do not substitute one for another.
- When a check does not execute, use `not run` and state the reason in plain language.
- Do not add repository-specific maturity levels, named gates, or synthetic status codes.

## Current upstream boundaries

- VRChat currently requires Unity `2022.3.22f1`: https://creators.vrchat.com/sdk/upgrade/current-unity-version/
- Unity Test Framework supports command-line test execution and NUnit XML output: https://docs.unity.cn/Packages/com.unity.test-framework@1.4/manual/reference-command-line.html
- The Unity Pipeline package requires Unity Editor 6.0 or later, so it is not a prerequisite for current VRChat 2022.3.22f1 projects: https://docs.unity.com/en-us/unity-production-pipeline/local-tools-cli/unity-pipeline-package
- Unity Terms of Service, last updated June 30, 2026, restrict how AI agents, LLMs, MCP clients/servers, and other automated callers may interact with Unity Offerings. Verify the current terms before using agentic access to Unity services: https://unity.com/legal/terms-of-service

## Existing `vrmine` evidence example

The workflow run below proves installation of the specified Unity Editor and a licensing precondition failure. It does **not** prove Unity compilation or Edit Mode/Play Mode success.

- repository: `KAFKA2306/vrmine`
- workflow run: https://github.com/KAFKA2306/vrmine/actions/runs/32193029515
- commit SHA: `364287004748fee1a49b1c97d4d34ac93e927232`
- runner: `ubuntu-24.04`
- Unity Editor: `2022.3.22f1`, changeset `887be4894c44`
- Editor installation: `success`
- license precondition: `failure`
- Edit Mode tests: `not run`
- NUnit XML for Edit Mode tests: not produced because the tests did not execute

This example should be replaced or supplemented by an exact-commit record containing NUnit XML and Editor log evidence once a Unity Editor test run actually executes.
