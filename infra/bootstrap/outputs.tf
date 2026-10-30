# Non-secret identifiers only. Other roots read these from /k8s-on-aws/bootstrap/* in SSM.

output "state_bucket" {
  description = "Terraform state bucket for every root."
  value       = aws_s3_bucket.state.bucket
}

output "ci_plan_role_arn" {
  description = "Role assumed by pr-plan."
  value       = aws_iam_role.ci_plan.arn
}

output "ci_apply_role_arn" {
  description = "Role assumed by persistent-apply and ephemeral-apply."
  value       = aws_iam_role.ci_apply.arn
}

output "ci_image_role_arn" {
  description = "Role assumed by image-build."
  value       = aws_iam_role.ci_image.arn
}

output "budget_topic_arn" {
  description = "SNS topic that receives the budget alerts."
  value       = aws_sns_topic.budget_alerts.arn
}
