provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "k8s-on-aws"
      Layer     = "bootstrap"
      ManagedBy = "terraform"
    }
  }
}

# Authenticates with GITHUB_TOKEN, set only in the apply shell from `gh auth token`.
provider "github" {
  owner = var.github_owner
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.region

  # GitHub OIDC subject prefix; every CI role trust policy is scoped to this one repository.
  repo_subject = "repo:${var.github_owner}/${var.github_repo}"
}
