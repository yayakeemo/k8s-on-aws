# Cross-root handoff (AD-3): later roots read these with the aws_ssm_parameter data source.

# Session state. Rebuild and Teardown write both values; Terraform only creates them.
resource "aws_ssm_parameter" "session" {
  for_each = toset(["state", "id"])

  name  = "/k8s-on-aws/session/${each.key}"
  type  = "String"
  value = "none"

  lifecycle {
    ignore_changes = [value]
  }
}

locals {
  bootstrap_parameters = {
    state_bucket      = aws_s3_bucket.state.bucket
    ci_plan_role_arn  = aws_iam_role.ci_plan.arn
    ci_apply_role_arn = aws_iam_role.ci_apply.arn
    ci_image_role_arn = aws_iam_role.ci_image.arn
    budget_topic_arn  = aws_sns_topic.budget_alerts.arn
  }
}

resource "aws_ssm_parameter" "bootstrap" {
  for_each = local.bootstrap_parameters

  name  = "/k8s-on-aws/bootstrap/${each.key}"
  type  = "String"
  value = each.value
}
