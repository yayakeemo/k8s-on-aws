# GitHub guard rails. The provider authenticates with GITHUB_TOKEN from `gh auth token`.

# GitHub Actions app id; used for the ruleset bypass and as the status-check source.
locals {
  github_actions_app_id = 15368

  # Job display name in .github/workflows/pr-plan.yml. Rename both in the same PR.
  required_status_check = "components (NFR-6 explainability check)"
}

# ci-apply trusts only these environments; each deploys from main only, with no reviewers.
resource "github_repository_environment" "deploy" {
  for_each = toset(["persistent", "ephemeral"])

  repository  = var.github_repo
  environment = each.key

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "main" {
  for_each = github_repository_environment.deploy

  repository     = var.github_repo
  environment    = each.value.environment
  branch_pattern = "main"
}

resource "github_repository_ruleset" "main" {
  name        = "main"
  repository  = var.github_repo
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  # github-actions[bot] commits chore(bot): image-tag bumps and rebuild-log records (AD-25).
  bypass_actors {
    actor_id    = local.github_actions_app_id
    actor_type  = "Integration"
    bypass_mode = "always"
  }

  rules {
    deletion         = true
    non_fast_forward = true

    # Solo Operator: a PR is required, approvals are not.
    pull_request {
      required_approving_review_count = 0
    }

    required_status_checks {
      required_check {
        context        = local.required_status_check
        integration_id = local.github_actions_app_id
      }
    }
  }
}

# The ruleset bypass above covers every GITHUB_TOKEN, so the default token is read-only and cannot
# approve PRs. A workflow that declares `contents: write` can still push to main (ADR-0001).
resource "github_workflow_repository_permissions" "repo" {
  repository                       = var.github_repo
  default_workflow_permissions     = "read"
  can_approve_pull_request_reviews = false
}
