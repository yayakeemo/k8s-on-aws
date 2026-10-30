variable "github_owner" {
  description = "GitHub user or organisation that owns the repository."
  type        = string
  default     = "yayakeemo"
}

variable "github_repo" {
  description = "GitHub repository name (without the owner)."
  type        = string
  default     = "k8s-on-aws"
}

variable "alert_email" {
  description = "Email address that receives the AWS Budgets alerts. Set it in the git-ignored terraform.tfvars."
  type        = string
  # Kept out of plan output, which story 1.3 posts as a PR comment.
  sensitive = true

  validation {
    condition     = can(regex("^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$", var.alert_email))
    error_message = "The alert_email value must be a valid email address."
  }
}
