# Runbook: Bootstrap (L0)

Creates the Bootstrap layer, `infra/bootstrap`, in an empty AWS account: the Terraform state
bucket, the GitHub OIDC provider, the CI roles `k8s-on-aws-ci-plan`, `k8s-on-aws-ci-apply` and
`k8s-on-aws-ci-image`, the budget and its SNS email topic, the Session state parameters, the
`/k8s-on-aws/bootstrap/*` handoff parameters, and the GitHub environments and `main` ruleset.
Why L0 exists and why only a human applies it: [ADR-0001](../adr/0001-bootstrap-layer.md).

The Operator runs this once, by hand. After that, CI plans L0 on every PR but never applies it.
Any later change to L0 is applied by hand against the S3 backend, without the override file or
the migration: run steps 1 and 2, then this sequence instead of steps 3 to 6, then step 7:

```powershell
$bucket = "k8s-on-aws-tfstate-$(aws sts get-caller-identity --region us-east-1 --query Account --output text)"
terraform -chdir=infra/bootstrap init -backend-config="bucket=$bucket"
terraform -chdir=infra/bootstrap plan -out=tfplan
terraform -chdir=infra/bootstrap apply tfplan
Remove-Item infra/bootstrap/tfplan   # the saved plan holds alert_email in plaintext
```

## Manual steps

The whole Platform has exactly three manual steps. This runbook is where they are listed:

1. **Register the domain and verify the contact email.** Register `yahiahussein.dev` in the
   Route 53 console and click the verification link that AWS sends to the registrant contact.
   This is independent of the L0 apply; it only has to be done before story 1.4, which adopts the
   hosted zone that registration creates.
2. **Confirm the budget email subscription.** See step 5 below.
3. **Migrate L0's local state into the state bucket.** See step 6 below.

Everything else is Terraform.

## Preconditions

These are prerequisites, not manual steps of the Platform:

- An IAM admin user, protected by MFA, with **no access keys**. It is used only through
  `aws login` sessions.
- Terraform `1.17.0` exactly (`terraform version`).
- AWS CLI `>= 2.32` (`aws --version`), which provides `aws login`.
- GitHub CLI `gh`, logged in as the repository owner with admin rights on the repository
  (`gh auth status`).
- The repository exists on GitHub as `<github_owner>/<github_repo>` (defaults `yayakeemo/k8s-on-aws`).

All commands are PowerShell, run from the repository root.

## Steps

### 1. Short-lived credentials

```powershell
aws login --region us-east-1     # browser sign-in with MFA; short-lived session, no keys
aws sts get-caller-identity --region us-east-1   # must show the admin user in the intended account

# GitHub provider token: lives only in this shell, never on disk.
$env:GITHUB_TOKEN = gh auth token
```

If Terraform cannot read the `aws login` session, export it into this shell only (still
short-lived): `aws configure export-credentials --region us-east-1 --format powershell | Invoke-Expression`.

### 2. Inputs

```powershell
if (-not (Test-Path infra/bootstrap/terraform.tfvars)) {
  Copy-Item infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
}
# Edit infra/bootstrap/terraform.tfvars and set alert_email. The file is git-ignored.
```

### 3. Local backend for the first apply

The state bucket does not exist yet, so the first apply uses local state. Create the git-ignored
override file `infra/bootstrap/local_override.tf`:

```powershell
# WriteAllText writes UTF-8 without a byte-order mark.
[IO.File]::WriteAllText("$PWD/infra/bootstrap/local_override.tf", 'terraform { backend "local" {} }')
```

### 4. Init, plan, apply

```powershell
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap plan -out=tfplan
terraform -chdir=infra/bootstrap apply tfplan
Remove-Item infra/bootstrap/tfplan   # the saved plan holds alert_email in plaintext
```

Read the plan before applying. On an empty account it only creates resources.

### 5. Confirm the email subscription (manual step 2)

AWS sends "AWS Notification - Subscription Confirmation" to `alert_email`. Click
**Confirm subscription**. Check it:

```powershell
$topic = terraform -chdir=infra/bootstrap output -raw budget_topic_arn
aws sns list-subscriptions-by-topic --region us-east-1 --topic-arn $topic --query "Subscriptions[].SubscriptionArn"
# Must show an ARN, not "PendingConfirmation".
```

### 6. Migrate the state into the bucket (manual step 3)

```powershell
$bucket = terraform -chdir=infra/bootstrap output -raw state_bucket
Remove-Item infra/bootstrap/local_override.tf
terraform -chdir=infra/bootstrap init -migrate-state -backend-config="bucket=$bucket"
# Answer "yes" to copy the local state to S3.
```

Then remove the leftover local state files (they are git-ignored, but they hold the same
content as the bucket):

```powershell
Remove-Item infra/bootstrap/terraform.tfstate, infra/bootstrap/terraform.tfstate.backup -ErrorAction SilentlyContinue
```

### 7. Verify

Run this in a shell where `terraform -chdir=infra/bootstrap init` against the S3 backend has
already run (step 6, or the later-change sequence above); otherwise Terraform has no state to plan
or read outputs from.

Re-planning against the bucket shows no changes (exit code 0; 2 would mean changes):

```powershell
$bucket = "k8s-on-aws-tfstate-$(aws sts get-caller-identity --region us-east-1 --query Account --output text)"
terraform -chdir=infra/bootstrap plan -detailed-exitcode
$LASTEXITCODE   # must be 0
aws s3 ls --region us-east-1 "s3://$bucket/infra/bootstrap/"   # terraform.tfstate is there
```

No IAM access keys exist anywhere in the account, the root user included:

```powershell
aws iam get-account-summary --region us-east-1 --query SummaryMap.AccountAccessKeysPresent   # must be 0
foreach ($u in (aws iam list-users --region us-east-1 --query "Users[].UserName" --output text).Split()) {
  aws iam list-access-keys --region us-east-1 --user-name $u --query "AccessKeyMetadata[].AccessKeyId" --output text
}
# Every list-access-keys result is empty.
```

The `ci-apply` guard rails actually deny. Every result must be `explicitDeny`:

```powershell
$applyRole = terraform -chdir=infra/bootstrap output -raw ci_apply_role_arn
$topic     = terraform -chdir=infra/bootstrap output -raw budget_topic_arn
$account   = aws sts get-caller-identity --region us-east-1 --query Account --output text
$checks = @(
  @("s3:PutObject",                     "arn:aws:s3:::$bucket/infra/bootstrap/terraform.tfstate"),
  @("iam:CreateAccessKey",              "*"),
  @("iam:AttachRolePolicy",             $applyRole),
  @("ssm:PutParameter",                 "arn:aws:ssm:us-east-1:${account}:parameter/k8s-on-aws/bootstrap/state_bucket"),
  @("sns:DeleteTopic",                  $topic),
  @("iam:DeactivateMFADevice",          "arn:aws:iam::${account}:user/any-user"),
  @("iam:PutUserPermissionsBoundary",   "arn:aws:iam::${account}:user/any-user"),
  @("iam:RemoveUserFromGroup",          "arn:aws:iam::${account}:group/any-group"),
  @("account:CloseAccount",             "*"),
  @("budgets:ModifyBudget",             "arn:aws:budgets::${account}:budget/k8s-on-aws-monthly"),
  @("sns:Unsubscribe",                  "${topic}:00000000-0000-0000-0000-000000000000"),
  @("s3:PutBucketPolicy",               "arn:aws:s3:::$bucket"),
  @("iam:DeleteOpenIDConnectProvider",  "arn:aws:iam::${account}:oidc-provider/token.actions.githubusercontent.com")
)
foreach ($c in $checks) {
  aws iam simulate-principal-policy --region us-east-1 --policy-source-arn $applyRole `
    --action-names $c[0] --resource-arns $c[1] `
    --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output text
}
# Thirteen lines, each ending in explicitDeny.
```

The handoff parameters exist:

```powershell
aws ssm get-parameters-by-path --region us-east-1 --path /k8s-on-aws/bootstrap --query "Parameters[].Name"
aws ssm get-parameters-by-path --region us-east-1 --path /k8s-on-aws/session --query "Parameters[].[Name,Value]"
```

Finally, close the shell (or `Remove-Item Env:GITHUB_TOKEN`) so the token does not outlive the apply.

## Teardown never touches L0

Teardown destroys only the Ephemeral layers. It never plans, applies or destroys
`infra/bootstrap`. `ci-apply`, the role Teardown runs as, is explicitly denied the items in
[ADR-0001, Protected items](../adr/0001-bootstrap-layer.md#protected-items):

- creating IAM users, access keys, login profiles, service-specific credentials, SSH public keys
  or signing certificates;
- weakening the Operator's IAM users and MFA devices, including their permissions boundaries;
- changing IAM group membership or group policies, or deleting a group;
- closing the account or changing its contacts;
- any change to the CI roles or the OIDC provider;
- any change to L0's state (`infra/bootstrap/*` in the state bucket);
- any change to the state bucket's configuration;
- any change to `/k8s-on-aws/bootstrap/*`;
- modifying or deleting the budgets;
- any change to the budget alert topic or its subscriptions.

The state bucket, the OIDC provider and the budget also have `prevent_destroy`. Removing L0 is a
deliberate, by-hand act outside every workflow and is not part of this Platform.

## Changing the required status check

The `main` ruleset requires the status check `components (NFR-6 explainability check)` by its job
display name in `.github/workflows/pr-plan.yml`. If that job is renamed, change
`infra/bootstrap/github.tf` in the same PR and re-apply L0 by hand.
