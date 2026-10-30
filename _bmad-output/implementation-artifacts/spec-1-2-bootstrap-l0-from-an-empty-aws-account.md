---
title: 'Story 1.2: Bootstrap L0 from an empty AWS account'
type: 'feature'
created: '2026-10-30'
status: 'done'
baseline_commit: '011d023f3bebdbfa3e9d394baf32eff9553f24de'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/docs/conventions.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The AWS account is empty. Later stories need a state backend, CI identities, cost alarms, Session state and GitHub guard rails, and none of these exist. Creating them by hand would add undocumented manual steps and long-lived keys.

**Approach:** One Terraform root, `infra/bootstrap` (L0), that the Operator applies once by hand with `aws login` credentials. It creates all of the above, then migrates its own local state into the bucket it made. `docs/runbooks/bootstrap.md` makes the process repeatable.

**Decisions (Operator, 2026-10-30):**
- The `integrations/github` provider authenticates with the Operator's `gh` CLI token (`GITHUB_TOKEN` from `gh auth token`), set only in the apply shell and never written to disk.
- The budget alert email comes from the git-ignored `infra/bootstrap/terraform.tfvars`. Only a `terraform.tfvars.example` is committed.
- The GitHub environments `persistent` and `ephemeral` allow deployments from `main` only, with no required reviewers.
- `ci-apply` = `AdministratorAccess` plus an explicit-deny policy (no IAM users or access keys; no changes to the CI roles, the OIDC provider, L0 state, the state bucket config, `/k8s-on-aws/bootstrap/*` or the budgets).
- (Review loop 1) The `main` ruleset keeps the GitHub Actions `always` bypass that AD-25 needs, and L0 hardens around it: the repository's default workflow token is read-only and cannot approve PRs (managed in Terraform). ADR-0001 states the residual risk plainly: any workflow that declares `contents: write` can still push to `main`. It does not claim the ruleset is a hard boundary. No GitHub App and no stored key.

## Boundaries & Constraints

**Always:**
- Pins: Terraform `1.17.0`, `hashicorp/aws` `6.70.0` and `integrations/github` `6.13.0`, all exact. Region `us-east-1`.
- `default_tags`: `Project=k8s-on-aws`, `Layer=bootstrap`, `ManagedBy=terraform`.
- Names use the prefix `k8s-on-aws-`. The OIDC subjects are scoped to `repo:<owner>/<repo>`, with owner and repo as variables (defaults `yayakeemo` and `k8s-on-aws`).
- The state backend uses partial S3 config (`key`, `region`, `use_lockfile = true`, `encrypt`). `bucket` is supplied at init. There is no DynamoDB table.
- The runbook lists exactly three manual steps: domain registration with email verification, confirming the email subscriptions, and the state migration. Prerequisites (the MFA IAM user, tool installs) are listed separately as preconditions.

**Never:**
- No IAM users, access keys, `terraform_remote_state`, or secrets in Git or outputs.
- Do not apply anything to AWS or GitHub from this build. The Operator applies by hand.
- No L1 resources (zone, Cognito, ECR, secrets).

</frozen-after-approval>

## Code Map

- `infra/bootstrap/`: currently only `.gitkeep`. All files are new.
- `.gitignore`: already ignores `*_override.tf`, which makes the local-backend override file work. Add `infra/bootstrap/terraform.tfvars` only. Committed tfvars stay allowed (triage #11).
- `docs/components.md`: append the `infra/bootstrap` row. Its link must resolve, or `scripts/check_components.py` fails.
- `docs/cost-model.md`: L0 rows (S3, Budgets, SNS, SSM) change status to `implemented (story 1.2)`.
- `.github/workflows/pr-plan.yml`: the job display name is `components (NFR-6 explainability check)`. Do not change it, because the ruleset requires it by that name.

## Tasks & Acceptance

**Execution:**
- [x] `infra/bootstrap/versions.tf` -- `required_version`, provider pins, and the partial `backend "s3"` with key `infra/bootstrap/terraform.tfstate`
- [x] `infra/bootstrap/providers.tf` -- aws with region and `default_tags`; github with `owner = var.github_owner`
- [x] `infra/bootstrap/variables.tf`, `terraform.tfvars.example` -- `github_owner`, `github_repo` and `alert_email` (validated as an email address)
- [x] `infra/bootstrap/state.tf` -- bucket `k8s-on-aws-tfstate-<account_id>` with versioning, SSE-S3, a full public-access block, BucketOwnerEnforced, a TLS-only bucket policy, and `prevent_destroy`
- [x] `infra/bootstrap/ci_roles.tf`
  - the OIDC provider for `token.actions.githubusercontent.com` (aud `sts.amazonaws.com`)
  - `k8s-on-aws-ci-plan`: sub `:pull_request`; `ReadOnlyAccess`, plus Put/Delete on `*.tflock` in the state bucket
  - `k8s-on-aws-ci-apply`: subs `:environment:persistent` and `:environment:ephemeral`; the Admin-plus-deny policy above; max session 2 h
  - `k8s-on-aws-ci-image`: sub `:ref:refs/heads/main`; `ecr:GetAuthorizationToken` plus push actions on `repository/k8s-on-aws/*`
- [x] `infra/bootstrap/budgets.tf`
  - SNS topic `k8s-on-aws-budget-alerts`, with a policy that lets `budgets.amazonaws.com` publish (condition on the source account), and an email subscription
  - a monthly COST budget of $30, notifying at ACTUAL > 100 % and at FORECASTED > $45 (absolute)
- [x] `infra/bootstrap/ssm.tf`
  - `/k8s-on-aws/session/state` = `none` and `/k8s-on-aws/session/id` = `none`, both with `ignore_changes = [value]` (Rebuild and Teardown write both)
  - `/k8s-on-aws/bootstrap/{state_bucket,ci_plan_role_arn,ci_apply_role_arn,ci_image_role_arn,budget_topic_arn}`
- [x] `infra/bootstrap/github.tf`
  - the environments `persistent` and `ephemeral`, each with a custom deployment-branch policy for `main`
  - ruleset `main`, targeting `~DEFAULT_BRANCH`, with these rules: pull request (0 approvals, because there is a solo Operator), required status check `components (NFR-6 explainability check)`, no deletion and no force push
  - bypass: GitHub Actions integration (actor_id 15368), mode `always`
- [x] `infra/bootstrap/outputs.tf` -- the bucket name and role ARNs. No secrets.
- [x] `docs/runbooks/bootstrap.md`
  - preconditions: the MFA admin user with no keys, Terraform 1.17.0, AWS CLI ≥ 2.32, `gh`
  - steps: `aws login`; `$env:GITHUB_TOKEN = gh auth token`; create `local_override.tf` (`backend "local" {}`); `init`, `plan`, `apply`; confirm the SNS email (manual step 2); delete the override file and run `init -migrate-state -backend-config="bucket=..."` (manual step 3); run the re-plan and the no-access-keys checks
  - teardown never touches L0
- [x] `docs/adr/0001-bootstrap-layer.md` -- MADR: why L0 exists, why it is applied only by humans, the credential choices, and the rejected alternatives
- [x] `docs/components.md`, `docs/cost-model.md`, `.gitignore` -- updates as in the Code Map

**Acceptance Criteria:**
- Given the root, when running `terraform fmt -check -recursive infra/bootstrap` and `terraform init -backend=false && terraform validate` with Terraform 1.17.0, then both succeed.
- Given the repo, when running `uv run --python 3.14 scripts/check_components.py`, then it exits 0 with 1 component discovered.
- Given the runbook, when it is read, then it lists exactly the three allowed manual steps, plus the verification commands for the no-changes re-plan and for no access keys (`aws iam list-users` / `list-access-keys`).
- Given `infra/bootstrap`, when it is searched, then it contains no `terraform_remote_state`, no hard-coded account ID, no `aws_iam_access_key` and no email address.

## Implementation Notes

## Spec Change Log

- **Loop 1 (2026-10-30)**
  - **Trigger:** an intent gap, triage #1. The ruleset's GitHub Actions `always` bypass lets any write-token workflow push to `main`, and ADR-0001 wrongly called the ruleset the boundary. The Operator chose "keep + harden" (see the frozen Decisions).
  - **Amended:** the frozen Decisions now include the bypass decision. The rebuild instructions follow.
  - **Known-bad state avoided:** an ADR claiming containment that does not exist, and a default write-capable workflow token.
  - **KEEP:** the loop-0 implementation passed fmt, validate and all checks, and is preserved at `C:/Users/YAHIA~1.HUS/AppData/Local/Temp/claude/C--Users-yahia-hussein-OneDrive-Projects-Personal-Kubernetes-on-AWS/e8b5c331-5a93-4627-8db2-6be018f56679/scratchpad/story-1-2-loop1-backup/` (paths mirror the repo). Copy every file back unchanged, including `infra/bootstrap/.terraform.lock.hcl`, which must be committed. Then apply only these changes:
    1. `github.tf`: add `github_workflow_repository_permissions` for `var.github_repo`, with `default_workflow_permissions = "read"` and `can_approve_pull_request_reviews = false`.
    2. `ci_roles.tf`, the `ci_apply_deny` policy:
       - add `iam:CreateServiceSpecificCredential`, `iam:UploadSSHPublicKey` and `iam:UploadSigningCertificate` to `NoIamUsersOrAccessKeys`
       - new statement `ProtectOperatorUsers`: Deny on `arn:…:iam::<acct>:user/*` and `arn:…:iam::<acct>:mfa/*` for `iam:DeleteUser`, `iam:DeactivateMFADevice`, `iam:DeleteVirtualMFADevice`, `iam:Attach/Detach/Put/DeleteUserPolicy`, `iam:AddUserToGroup`, `iam:DeleteLoginProfile`, `iam:UpdateUser` and `iam:TagUser`
       - new statement `ProtectAccount`: Deny `account:CloseAccount`, `account:PutAlternateContact`, `account:DeleteAlternateContact` and `account:PutContactInformation` on `*`
       - `ProtectBudgetAlertTopic`: add `"${topic_arn}:*"` to its resources, and add a statement denying `sns:Unsubscribe` and `sns:SetSubscriptionAttributes` on `"${topic_arn}:*"`
    3. `budgets.tf`: in the topic policy, also condition on `aws:SourceArn` matching `arn:${partition}:budgets::${account_id}:*` (ArnLike).
    4. `ci_roles.tf` / `budgets.tf`: add `lifecycle { prevent_destroy = true }` to the OIDC provider and to `aws_budgets_budget.monthly`.
    5. `docs/adr/0001-bootstrap-layer.md`, Consequences: replace the claim that the ruleset and environment policies are "the controls that keep untrusted code away from ci-apply". State instead that the Actions `always` bypass (needed for AD-25) means any workflow declaring `contents: write`, even on a branch, can push to `main` and reach `ci-apply`. The default token is read-only, forks get no write token or OIDC, and the practical risk is the Operator's own branches or account. Make the protected-items list match the deny policy exactly.
    6. `docs/runbooks/bootstrap.md`:
       - add `--region us-east-1` to every `aws` command
       - in step 7 and in the later-change path, set `$bucket = "k8s-on-aws-tfstate-$(aws sts get-caller-identity --query Account --output text)"`
       - after apply, delete `tfplan`, because it holds the email in plaintext
       - add a step-7 check: run `aws iam simulate-principal-policy --policy-source-arn <ci_apply_role_arn>` for `s3:PutObject` on `<bucket>/infra/bootstrap/terraform.tfstate`, `iam:CreateAccessKey`, `iam:AttachRolePolicy` on the ci-apply role ARN, `ssm:PutParameter` on `/k8s-on-aws/bootstrap/state_bucket` and `sns:DeleteTopic` on the topic, and require `explicitDeny` for each
       - make the "Teardown never touches L0" list match the ADR
    7. `docs/cost-model.md`: define `implemented` in the status sentence: "`implemented` (code merged, not yet applied), then `live` once applied and measured".
    8. New `scripts/tests/test_required_check_name.py` (stdlib unittest): use a regex to read the `components` job `name:` from `.github/workflows/pr-plan.yml` and `required_status_check` from `infra/bootstrap/github.tf`, and assert they are equal.

## Review Triage Log

| # | Source | Finding | Verdict | Evidence / route |
|---|--------|---------|---------|------------------|
| 1 | blind, edge | The Actions `always` bypass lets any write-token workflow push to `main`, and the ADR overclaims | medium | Real: the bypass covers every `GITHUB_TOKEN`, and a branch workflow can declare `contents: write`. The fix touched the AD-25-mandated bypass → **intent_gap**, resolved by the Operator ("keep + harden") |
| 2 | blind, edge | `ci-apply` can alter or delete the Operator user's MFA and policies, close the account, or create other credential types | medium | Real: the deny list covered only user and key creation → patch (KEEP 2) |
| 3 | edge | `sns:Unsubscribe` on the subscription ARN is not denied | medium | Real: the deny targets only the topic ARN, and subscription ARNs are `topic:*` → patch (KEEP 2) |
| 4 | vgap | Nothing verifies that the `ci-apply` denies actually deny | medium | Pre-verified: no simulate check exists → patch (KEEP 6) |
| 5 | vgap | The ruleset's required-check name is not pinned to the workflow job name | medium | Pre-verified: renaming the job blocks every human PR → patch (KEEP 8) |
| 6 | blind, edge | CI cannot plan L0: no `alert_email`, and the github provider token lacks permissions | medium | Real, but the CI L0 plan is built in story 1.3 (the spec's Design Notes deferred it) → **defer** |
| 7 | vgap | Terraform fmt/validate is not in CI | low | Pre-verified gap; the plan jobs land in 1.3 → **defer** |
| 8 | blind, vgap, edge | `.terraform.lock.hcl` is not committed | false | It exists, is not ignored, and was excluded only from the review diff; it is committed with this change (KEEP) |
| 9 | blind | `tfplan` is not ignored | false | `.gitignore` already has `tfplan` and `*.tfplan` (Story 1.1). Deleting the local file is a patch (KEEP 6) |
| 10 | blind | No noncurrent-version lifecycle on the state bucket | low | State objects are KB-sized; the fix adds a resource → rejected |
| 11 | blind | Cost-model status `implemented` is undefined | low | Real; one-line doc fix → patch (KEEP 7) |
| 12 | blind | The runbook's Teardown list differs from the ADR's | low | Real; doc fix → patch (KEEP 5, 6) |
| 13 | blind, edge | `$bucket` is unset in step 7 and in the later-change path | low | Real; direct fix → patch (KEEP 6) |
| 14 | blind | `prevent_destroy` is set only on the bucket | low | Real; direct addition for the OIDC provider and the budget → patch (KEEP 4) |
| 15 | blind | `ci-plan` ReadOnlyAccess can read state and SSM from PR workflows | low | Fork PRs get no OIDC token, so only the Operator's branches can do this; the architecture specifies read-only `ci-plan` → rejected |
| 16 | blind | The topic policy lacks `aws:SourceArn` | low | Real; direct addition → patch (KEEP 3) |
| 17 | edge | AWS CLI default region is not `us-east-1` | low | Real; direct fix → patch (KEEP 6) |
| 18 | edge | OIDC sub mismatch if a job declares an environment, or on owner/repo casing | low | Subjects follow the GitHub defaults; a job-level mistake surfaces as a loud AssumeRole failure → rejected |
| 19 | edge | `list-users` output of `None` | low | The admin user always exists → rejected |
| 20 | edge (loop 1) | `ProtectOperatorUsers` lacks Put/DeleteUserPermissionsBoundary | medium | Real: a deny-all boundary on the only admin user locks the Operator out → patch |
| 21 | edge (loop 1) | `iam:AddUserToGroup` authorizes on the group ARN, so its deny never applies, and group changes are unprotected; the ADR overclaims | medium | Real: the resource type is `group`, but the deny targets `user/*` and `mfa/*` → patch (new group statement plus ADR fix) |
| 22 | vgap, blind (loop 1) | The runbook's simulate check covers only 5 of the deny statements | medium | Pre-verified: dropping `ProtectBudgets` or mis-ARNing the subscription deny leaves all 5 checks green → patch |
| 23 | vgap (loop 1) | The pin test reads the local, not the ruleset's `context` | low | Pre-verified: `context = "x"` with an unchanged local passes → patch |
| 24 | blind, edge (loop 1) | The pin-test regex matches a nested `components:` key or a step `name:`, and truncates at `#` | low | Real: the lazy `(?:.*\n)*?` has no indent anchor; direct correction → patch |
| 25 | blind (loop 1) | The no-access-keys check misses root keys; `list-users` runs twice | medium | Real: the AC says "no IAM access key exists in the account", and root keys are not listed by `list-users` → patch |
| 26 | blind, edge (loop 1) | The later-change path runs a bare `init`; step 2's Copy-Item overwrites tfvars; step 7's init precondition is unstated | low | Real; doc correction → patch |
| 27 | blind (loop 1) | The cost-model Budgets basis and the SSM row's L1 status are wrong | low | Real; doc correction → patch |
| 28 | blind (loop 1) | `ProtectBudgetAlertSubscriptions` is redundant with the topic `:*` deny | low | True but harmless; the KEEP asked for it as an explicit backstop → rejected |
| 29 | blind (loop 1) | `.terraform.lock.hcl` is not in the diff | false | carried #8 |
| 30 | blind, edge (loop 1) | CI cannot plan L0 with the github provider | medium | carried #6 → deferred to 1.3 (already in `deferred-work.md`) |
| 31 | blind (loop 1) | No noncurrent-version lifecycle | low | carried #10 → rejected |
| 32 | blind (loop 1) | `alert_email` is plaintext in state readable by the CI roles; `ci-plan` reads every state | low | Variant of carried #15; the ADR's privacy claim is about Git, which still holds → rejected |
| 33 | blind (loop 1) | No detection of a bypass push to `main` | low | The ADR records the residual risk per the Operator's decision; detection is a new capability → rejected |
| 34 | edge (loop 1) | `ci-image` sub mismatch if an environment is declared | low | carried #18 → rejected |
| 35 | edge (loop 1) | The ruleset uses `~DEFAULT_BRANCH`, which may not be `main` | low | The repo's default branch is `main` (verified by the push) → rejected |

## Design Notes

**First apply.** A git-ignored `local_override.tf` that holds `terraform { backend "local" {} }` overrides the S3 backend, so the first apply works before the bucket exists. Deleting the file and running `init -migrate-state` moves the state into the bucket. The bucket name comes from `terraform output -raw state_bucket`.

**Status-check name.** The ruleset requires the status check by its job display name. If that job is ever renamed, the ruleset must be updated in the same PR.

**Bootstrap in CI.** Story 1.3 will plan L0 in CI. There the github provider has to read the environments and the ruleset with the workflow's token. Any permission gap belongs to 1.3, not to this story.

## Verification

**Commands:**
- `terraform -chdir=infra/bootstrap fmt -check` -- expected: exit 0
- `terraform -chdir=infra/bootstrap init -backend=false` then `terraform -chdir=infra/bootstrap validate` (Terraform 1.17.0; if the local version differs, download 1.17.0 to the scratch directory) -- expected: "Success"
- `uv run --python 3.14 -m unittest discover -s scripts/tests` and `uv run --python 3.14 scripts/check_components.py` -- expected: pass, exit 0
