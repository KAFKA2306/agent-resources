# GitHub control-plane Terraform

This directory gives the Software Factory Control Tower one narrow Terraform responsibility: detect drift in its GitHub repository control plane.

It reads the live `KAFKA2306/agent-resources` repository through the OSS `integrations/github` Terraform provider and fails planning when core factory invariants are broken. Merge-policy fields that the provider cannot reliably expose with the ephemeral Actions token are read directly from GitHub REST and passed into Terraform as typed variables.

Checked invariants:

- repository remains public and active
- default branch remains `main`
- GitHub Issues remain enabled for work routing
- squash merge remains available
- required factory/security/event workflows remain present

The configuration is intentionally read-only. CI runs `terraform plan`, never `terraform apply`. It uses the ephemeral GitHub Actions `GITHUB_TOKEN`; no PAT, Terraform Cloud account, managed service, or additional paid contract is required.

Vercel remains configured by `vercel.json`. This Terraform boundary does not duplicate deployment-provider configuration.
