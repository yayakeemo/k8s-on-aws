# ADR-0001: A human-applied Bootstrap layer (L0)

- Status: accepted
- Date: 2026-10-30
- Deciders: Operator
- Story: 1.2 (Bootstrap L0 from an empty AWS account)

## Context and problem statement

The AWS account starts empty. Every later layer needs things that must exist before any pipeline
can run: a place to keep Terraform state, identities that let GitHub Actions reach AWS, cost
alarms, the Session state parameters, and GitHub guard rails (deployment environments and a
`main` ruleset). The pipeline cannot create the identities it runs as, and creating these by
hand would leave undocumented manual steps and, typically, long-lived access keys.

How should these first resources be created and changed, without long-lived credentials and
with only the three allowed manual steps?

## Decision drivers

- No long-lived credentials anywhere: no IAM users for CI, no access keys, no stored tokens.
- Exactly three manual steps: domain registration with email verification, confirming the email
  subscriptions, and the one-time state migration.
- Everything defined in Git and reproducible; re-planning an unchanged root shows no changes.
- CI must not be able to widen its own permissions or remove the guard rails that contain it.
- Teardown must never touch the foundations.

## Considered options

1. **A separate Terraform root, `infra/bootstrap`, applied only by a human** (chosen).
2. Click-ops in the console, documented in a runbook.
3. Put the bootstrap resources into L1 (`infra/persistent`) and let CI apply them.
4. A CloudFormation stack or `aws` CLI script for the chicken-and-egg resources, Terraform for the rest.
5. CI authenticated with an IAM user's access keys stored as GitHub secrets.

## Decision outcome

Chosen option 1. `infra/bootstrap` is one Terraform root that creates the state bucket, the
GitHub OIDC provider, the three CI roles, the budget and its SNS topic, the Session and
`/k8s-on-aws/bootstrap/*` SSM parameters, and, through the `integrations/github` provider, the
`persistent` and `ephemeral` environments and the `main` ruleset. It is applied once by hand,
starts on local state, and then migrates its own state into the bucket it created. CI plans it
on every PR but never applies it. The procedure is `docs/runbooks/bootstrap.md`.

### Why only a human applies it

L0 defines the identities and limits that CI runs under. If CI could apply L0, a merged PR could
widen `ci-apply`, change which subjects may assume it, or delete the budgets, so any compromise of
the pipeline would become a compromise of the account. Keeping L0 human-applied makes those
changes require the Operator's MFA session. `ci-apply` enforces this with an explicit deny
(see [Protected items](#protected-items)).

### Protected items

The `bootstrap-guard-rails` policy on `ci-apply` (`infra/bootstrap/ci_roles.tf`) denies exactly:

- **New long-lived credentials:** creating IAM users, creating or updating access keys, creating or
  updating login profiles, creating service-specific credentials, and uploading SSH public keys or
  signing certificates.
- **The Operator's IAM users and MFA devices** (`user/*`, `mfa/*`): deleting a user, deactivating
  or deleting MFA devices, attaching, detaching, putting or deleting user policies, putting or
  deleting a user's permissions boundary, deleting a login profile, and updating or tagging a user.
- **IAM groups** (`group/*`): adding users to or removing users from a group, attaching,
  detaching, putting or deleting group policies, and deleting a group.
- **The account:** closing it, and changing or deleting its alternate or primary contacts.
- **The CI roles and the OIDC provider:** every action except `iam:Get*` and `iam:List*`,
  including `iam:PassRole` and `sts:AssumeRole`.
- **L0's state** (`infra/bootstrap/*` in the state bucket): every action except reading objects.
- **The state bucket's configuration:** every bucket-level action except `s3:Get*` and `s3:List*`.
  The other roots' state objects stay readable and writable.
- **`/k8s-on-aws/bootstrap/*` SSM parameters:** every action except `Get*`, `Describe*` and `List*`.
- **The budgets:** modifying or deleting them (`budgets:ModifyBudget`), budget actions, and tags.
- **The budget alert topic and its subscriptions:** every action except `sns:Get*` and `sns:List*`
  on the topic and on `<topic>:*`, plus `sns:Unsubscribe` and `sns:SetSubscriptionAttributes` on
  the subscriptions.

### Credential choices

- **Operator:** `aws login` sessions from an MFA-protected IAM admin user with no access keys.
  Credentials are short-lived and never written to the repository.
- **GitHub provider:** the Operator's `gh` CLI token (`$env:GITHUB_TOKEN = gh auth token`), set
  only in the apply shell. No GitHub App or personal access token is stored anywhere.
- **CI:** GitHub OIDC only. Each role trusts exactly the subjects it needs, all scoped to
  `repo:<owner>/<repo>`: `ci-plan` the `pull_request` subject, `ci-apply` the `persistent` and
  `ephemeral` environments (which deploy from `main` only), `ci-image` `refs/heads/main`.
- **`ci-apply` = `AdministratorAccess` plus an explicit deny.** Later layers create EKS, VPC,
  RDS, IAM roles for workloads and more; a hand-maintained allow list would churn with every story
  and fail mid-Rebuild. The deny list protects what matters instead.
- **Budget alert email** comes from a git-ignored `terraform.tfvars`, so no address is in Git, and
  the variable is marked sensitive so it never appears in a plan posted to a PR.

### Consequences

- Good: no long-lived credentials; the pipeline cannot loosen its own containment; one documented
  bootstrap procedure with exactly the allowed manual steps.
- Good: the state bucket is versioned, encrypted, private, TLS-only and `prevent_destroy`, and
  it uses S3 native locking, so there is no DynamoDB table to pay for or manage.
- Bad: L0 changes need the Operator at a terminal; CI only shows the plan.
- Bad: admin-plus-deny is weaker than least privilege. `ci-apply` can still create a new role
  and pass or assume it, so the deny list is a guard rail against mistakes and casual abuse, not a
  hard boundary.
- Bad: the `main` ruleset is not a hard boundary either. Its GitHub Actions bypass (mode
  `always`) is needed for the `chore(bot): …` commits (AD-25), and it covers every
  `GITHUB_TOKEN`, not just the bot's commits. Any workflow that declares `contents: write`, even
  one on a branch, can push straight to `main` without a PR, and from `main` it reaches the
  `persistent` and `ephemeral` environments and so `ci-apply`. L0 hardens around this: the
  repository's default workflow token is read-only and cannot approve PRs (managed in
  `infra/bootstrap/github.tf`), and workflows from forks get neither a write token nor an OIDC
  token. The practical risk is therefore the Operator's own branches or a compromise of the
  Operator's GitHub account; the environment branch policies (`main` only) do not reduce it.
- Neutral: the ruleset requires the `components (NFR-6 explainability check)` status check by its
  job display name; renaming that job requires changing `infra/bootstrap/github.tf` in the same PR.

## Pros and cons of the rejected options

- **Click-ops.** Fast, but invisible to Git: it cannot be re-planned, reviewed or reproduced,
  and it adds manual steps beyond the allowed three.
- **Bootstrap inside L1, applied by CI.** Circular: CI needs the roles and the state bucket
  before it can apply anything, and it would be able to rewrite its own permissions.
- **CloudFormation or a CLI script for the first resources.** A second tool and a second source
  of truth for a handful of resources, with drift that Terraform cannot see. Terraform's local
  backend followed by `init -migrate-state` solves the chicken-and-egg problem with one tool.
- **CI with IAM user access keys.** Long-lived secrets in GitHub, which the project forbids, and a
  credential that works from anywhere until someone rotates it.
