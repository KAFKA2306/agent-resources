# GitHub control-plane Terraform

This directory gives the Software Factory Control Tower one narrow Terraform responsibility: detect drift in its GitHub repository control plane.

It reads the live `KAFKA2306/agent-resources` repository through the OSS `integrations/github` Terraform provider and fails planning when core factory invariants are broken.

Checked invariants:

- repository remains public and active
- default branch remains `main`
- GitHub Issues remain enabled for work routing
- required factory/security/event workflows remain present

The configuration is intentionally read-only. CI runs `terraform plan`, never `terraform apply`. It uses the ephemeral GitHub Actions `GITHUB_TOKEN`; no PAT, Terraform Cloud account, managed service, or additional paid contract is required. Merge-method availability is left to GitHub's merge-time enforcement because low-privilege workflow tokens do not expose that field reliably.

Vercel remains configured by `vercel.json`. This Terraform boundary does not duplicate deployment-provider configuration.
