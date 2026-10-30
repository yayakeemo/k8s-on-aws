terraform {
  required_version = "1.17.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.70.0"
    }
    github = {
      source  = "integrations/github"
      version = "6.13.0"
    }
  }

  # Partial configuration: `bucket` is supplied at init with
  # -backend-config="bucket=<state_bucket output>". The first apply runs on local state
  # through a git-ignored local_override.tf (see docs/runbooks/bootstrap.md).
  backend "s3" {
    key          = "infra/bootstrap/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
