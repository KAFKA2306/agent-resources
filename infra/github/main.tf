terraform {
  required_version = ">= 1.16.0, < 1.17.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "6.13.0"
    }
  }
}

provider "github" {
  owner = "KAFKA2306"
}

data "github_repository" "control_tower" {
  full_name = "KAFKA2306/agent-resources"
}

locals {
  required_workflows = toset([
    "dashboard-validate.yml",
    "factory-autonomous-merge.yml",
    "mcp-events-emit.yml",
    "secret-guard.yml",
    "terraform-github.yml",
  ])

  workflow_files = setunion(
    fileset("${path.root}/../../.github/workflows", "*.yml"),
    fileset("${path.root}/../../.github/workflows", "*.yaml"),
  )

  missing_workflows = setsubtract(local.required_workflows, local.workflow_files)
}

resource "terraform_data" "github_contract" {
  input = {
    repository         = data.github_repository.control_tower.full_name
    visibility         = data.github_repository.control_tower.visibility
    default_branch     = data.github_repository.control_tower.default_branch
    issues_enabled     = data.github_repository.control_tower.has_issues
    squash_enabled     = data.github_repository.control_tower.allow_squash_merge
    archived           = data.github_repository.control_tower.archived
    required_workflows = sort(tolist(local.required_workflows))
  }

  lifecycle {
    precondition {
      condition     = data.github_repository.control_tower.visibility == "public"
      error_message = "agent-resources must remain public because the Control Tower is a public evidence surface."
    }

    precondition {
      condition     = data.github_repository.control_tower.default_branch == "main"
      error_message = "agent-resources default branch must remain main."
    }

    precondition {
      condition     = data.github_repository.control_tower.has_issues
      error_message = "GitHub Issues must stay enabled because factory work routing depends on them."
    }

    precondition {
      condition     = data.github_repository.control_tower.allow_squash_merge
      error_message = "Squash merge must stay enabled for the repository merge contract."
    }

    precondition {
      condition     = !data.github_repository.control_tower.archived
      error_message = "agent-resources must not be archived while it is the active factory control plane."
    }

    precondition {
      condition     = length(local.missing_workflows) == 0
      error_message = "Required factory workflows are missing: ${join(", ", sort(tolist(local.missing_workflows)))}"
    }
  }
}

output "github_contract" {
  value = terraform_data.github_contract.input
}
