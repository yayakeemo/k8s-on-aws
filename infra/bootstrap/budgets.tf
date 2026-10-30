# NFR-1: alert at $30 actual and $45 forecast. The Operator confirms the email subscription
# once after the first apply (manual step 2).

resource "aws_sns_topic" "budget_alerts" {
  name = "k8s-on-aws-budget-alerts"
}

data "aws_iam_policy_document" "budget_alerts" {
  statement {
    sid     = "AllowBudgetsPublish"
    effect  = "Allow"
    actions = ["SNS:Publish"]

    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }

    resources = [aws_sns_topic.budget_alerts.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:budgets::${local.account_id}:*"]
    }
  }
}

resource "aws_sns_topic_policy" "budget_alerts" {
  arn    = aws_sns_topic.budget_alerts.arn
  policy = data.aws_iam_policy_document.budget_alerts.json
}

resource "aws_sns_topic_subscription" "budget_alerts_email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_budgets_budget" "monthly" {
  name         = "k8s-on-aws-monthly"
  budget_type  = "COST"
  limit_amount = "30.0"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    notification_type         = "ACTUAL"
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  notification {
    notification_type         = "FORECASTED"
    comparison_operator       = "GREATER_THAN"
    threshold                 = 45
    threshold_type            = "ABSOLUTE_VALUE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Budgets validates that it may publish to the topic when the notification is created.
  depends_on = [aws_sns_topic_policy.budget_alerts]

  lifecycle {
    prevent_destroy = true
  }
}
