# GitHub Actions reaches AWS only through OIDC (no access keys anywhere). Each role trusts
# exactly the subjects it needs, all scoped to repo:<owner>/<repo>.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  ci_subjects = {
    plan  = ["${local.repo_subject}:pull_request"]
    apply = ["${local.repo_subject}:environment:persistent", "${local.repo_subject}:environment:ephemeral"]
    image = ["${local.repo_subject}:ref:refs/heads/main"]
  }

  # Role ARNs are built from the names so the ci-apply deny policy can protect every CI role,
  # ci-apply included, without a dependency cycle.
  ci_role_names = {
    plan  = "k8s-on-aws-ci-plan"
    apply = "k8s-on-aws-ci-apply"
    image = "k8s-on-aws-ci-image"
  }
  ci_role_arns = [for name in values(local.ci_role_names) : "arn:${local.partition}:iam::${local.account_id}:role/${name}"]
}

data "aws_iam_policy_document" "ci_trust" {
  for_each = local.ci_subjects

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = each.value
    }
  }
}

# --- ci-plan: read-only, pull requests only -----------------------------------------------------

resource "aws_iam_role" "ci_plan" {
  name               = local.ci_role_names.plan
  description        = "GitHub Actions pr-plan: read-only Terraform plans on pull requests."
  assume_role_policy = data.aws_iam_policy_document.ci_trust["plan"].json
}

resource "aws_iam_role_policy_attachment" "ci_plan_readonly" {
  role       = aws_iam_role.ci_plan.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "ci_plan_lock" {
  statement {
    sid       = "StateLockFiles"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/*.tflock"]
  }
}

resource "aws_iam_role_policy" "ci_plan_lock" {
  name   = "state-lock"
  role   = aws_iam_role.ci_plan.id
  policy = data.aws_iam_policy_document.ci_plan_lock.json
}

# --- ci-apply: AdministratorAccess minus an explicit deny; environments persistent/ephemeral only

resource "aws_iam_role" "ci_apply" {
  name                 = local.ci_role_names.apply
  description          = "GitHub Actions persistent-apply and ephemeral-apply (environments persistent and ephemeral)."
  assume_role_policy   = data.aws_iam_policy_document.ci_trust["apply"].json
  max_session_duration = 7200
}

resource "aws_iam_role_policy_attachment" "ci_apply_admin" {
  role       = aws_iam_role.ci_apply.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AdministratorAccess"
}

data "aws_iam_policy_document" "ci_apply_deny" {
  statement {
    sid    = "NoIamUsersOrAccessKeys"
    effect = "Deny"
    actions = [
      "iam:CreateUser",
      "iam:CreateAccessKey",
      "iam:UpdateAccessKey",
      "iam:CreateLoginProfile",
      "iam:UpdateLoginProfile",
      "iam:CreateServiceSpecificCredential",
      "iam:UploadSSHPublicKey",
      "iam:UploadSigningCertificate",
    ]
    resources = ["*"]
  }

  statement {
    # The Operator's MFA-protected IAM user is the only human way in; ci-apply may not weaken it.
    sid    = "ProtectOperatorUsers"
    effect = "Deny"
    actions = [
      "iam:DeleteUser",
      "iam:DeactivateMFADevice",
      "iam:DeleteVirtualMFADevice",
      "iam:AttachUserPolicy",
      "iam:DetachUserPolicy",
      "iam:PutUserPolicy",
      "iam:DeleteUserPolicy",
      "iam:PutUserPermissionsBoundary",
      "iam:DeleteUserPermissionsBoundary",
      "iam:DeleteLoginProfile",
      "iam:UpdateUser",
      "iam:TagUser",
    ]
    resources = [
      "arn:${local.partition}:iam::${local.account_id}:user/*",
      "arn:${local.partition}:iam::${local.account_id}:mfa/*",
    ]
  }

  statement {
    # Group membership and group policies are authorised on the group ARN; changing them could
    # strip the Operator's admin rights.
    sid    = "ProtectGroups"
    effect = "Deny"
    actions = [
      "iam:AddUserToGroup",
      "iam:RemoveUserFromGroup",
      "iam:AttachGroupPolicy",
      "iam:DetachGroupPolicy",
      "iam:PutGroupPolicy",
      "iam:DeleteGroupPolicy",
      "iam:DeleteGroup",
    ]
    resources = ["arn:${local.partition}:iam::${local.account_id}:group/*"]
  }

  statement {
    sid    = "ProtectAccount"
    effect = "Deny"
    actions = [
      "account:CloseAccount",
      "account:PutAlternateContact",
      "account:DeleteAlternateContact",
      "account:PutContactInformation",
    ]
    resources = ["*"]
  }

  statement {
    # Everything except reads on the CI roles and the OIDC provider, including
    # iam:PassRole and sts:AssumeRole.
    sid         = "ProtectCiIdentities"
    effect      = "Deny"
    not_actions = ["iam:Get*", "iam:List*"]
    resources   = concat(local.ci_role_arns, [aws_iam_openid_connect_provider.github.arn])
  }

  statement {
    sid         = "ProtectBootstrapState"
    effect      = "Deny"
    not_actions = ["s3:GetObject", "s3:GetObjectVersion"]
    resources   = ["${aws_s3_bucket.state.arn}/infra/bootstrap/*"]
  }

  statement {
    # Bucket-level actions only. Reading and writing the other roots' state objects are
    # object-ARN actions and stay allowed.
    sid         = "ProtectStateBucketConfig"
    effect      = "Deny"
    not_actions = ["s3:Get*", "s3:List*"]
    resources   = [aws_s3_bucket.state.arn]
  }

  statement {
    sid         = "ProtectBootstrapParameters"
    effect      = "Deny"
    not_actions = ["ssm:Get*", "ssm:Describe*", "ssm:List*"]
    resources   = ["arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/k8s-on-aws/bootstrap/*"]
  }

  statement {
    sid    = "ProtectBudgets"
    effect = "Deny"
    actions = [
      "budgets:ModifyBudget",
      "budgets:CreateBudgetAction",
      "budgets:UpdateBudgetAction",
      "budgets:DeleteBudgetAction",
      "budgets:ExecuteBudgetAction",
      "budgets:TagResource",
      "budgets:UntagResource",
    ]
    resources = ["arn:${local.partition}:budgets::${local.account_id}:budget/*"]
  }

  statement {
    # The budget alert topic is part of the budgets: deleting or rewiring it silences them.
    sid         = "ProtectBudgetAlertTopic"
    effect      = "Deny"
    not_actions = ["sns:Get*", "sns:List*"]
    resources   = [aws_sns_topic.budget_alerts.arn, "${aws_sns_topic.budget_alerts.arn}:*"]
  }

  statement {
    # Subscription ARNs are <topic_arn>:<id>; removing the email subscription also silences the budgets.
    sid       = "ProtectBudgetAlertSubscriptions"
    effect    = "Deny"
    actions   = ["sns:Unsubscribe", "sns:SetSubscriptionAttributes"]
    resources = ["${aws_sns_topic.budget_alerts.arn}:*"]
  }
}

resource "aws_iam_role_policy" "ci_apply_deny" {
  name   = "bootstrap-guard-rails"
  role   = aws_iam_role.ci_apply.id
  policy = data.aws_iam_policy_document.ci_apply_deny.json
}

# --- ci-image: ECR push from main only ----------------------------------------------------------

resource "aws_iam_role" "ci_image" {
  name               = local.ci_role_names.image
  description        = "GitHub Actions image-build: push images to the k8s-on-aws/* ECR repositories from main."
  assume_role_policy = data.aws_iam_policy_document.ci_trust["image"].json
}

data "aws_iam_policy_document" "ci_image" {
  statement {
    sid       = "EcrLogin"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPush"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = ["arn:${local.partition}:ecr:${local.region}:${local.account_id}:repository/k8s-on-aws/*"]
  }
}

resource "aws_iam_role_policy" "ci_image" {
  name   = "ecr-push"
  role   = aws_iam_role.ci_image.id
  policy = data.aws_iam_policy_document.ci_image.json
}
