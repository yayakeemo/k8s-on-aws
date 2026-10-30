# Epic 1 Context: Bootstrap the account and make every Persistent change go through a PR

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The Operator runs Bootstrap once against an empty AWS account (us-east-1, single account, single environment), using short-lived credentials and only three allowed manual steps, and gets the Persistent Footprint: state bucket, GitHub OIDC CI roles, budgets, Session state parameters, the domain and its hosted zone, Cognito, ECR and persistent secrets. From then on that footprint changes only through the pipeline: every PR shows a Terraform plan, merges to the Persistent layer (L1) apply automatically, and the Bootstrap layer (L0) is planned by CI but applied only by a human. The epic also lays down the repo skeleton (there is no starter template), the written conventions and the explainability CI check. Everything later epics build sits on this footprint and must survive every Teardown.

## Stories

- Story 1.1: Repo skeleton, conventions and explainability check
- Story 1.2: Bootstrap L0 from an empty AWS account
- Story 1.3: Plan every PR and apply Persistent changes on merge
- Story 1.4: Register the domain and adopt its hosted zone
- Story 1.5: Cognito user pool with App and Probe clients and users
- Story 1.6: Image registry and persistent secrets

## Requirements & Constraints

- **No long-lived credentials anywhere.** No IAM access keys, no static passwords or tokens, nothing secret in Git or in Terraform outputs. Bootstrap uses `aws login` sessions from an MFA-protected IAM admin user that has no access keys. CI reaches AWS only through GitHub OIDC. IAM is least-privilege for each identity.
- **Allowed manual steps (exactly these, and the runbook lists no others):** domain registration plus contact-email verification; confirming the budget/SNS email subscriptions; the one-time migration of L0's local state into the state bucket.
- **Idempotent:** re-planning an unchanged L0 or L1 shows no changes.
- **Teardown must never touch L0/L1.** App Users created in L1 keep the same Cognito `sub` across every Teardown and Rebuild. A Rebuild never builds or pushes images.
- **Secrets are never defined in the Ephemeral layers.** All persistent secrets live in L1 so the Secrets Manager name-reservation window (7 to 30 days after deletion) can never block a Rebuild.
- **Cost:** under $30/month actual, $50 hard cap. Budgets alert at $30 actual and $45 forecast. `docs/cost-model.md` has one row per Persistent Footprint item with its expected monthly cost, filled in as items are added (zone, domain, ECR, Secrets Manager, ...).
- **Explainability:** `docs/components.md` maps every Terraform root and Argo CD app to an ADR or runbook. CI fails, naming the component, when a root under `infra/` or an Argo CD Application under `gitops/` is unlisted.
- **Reproducibility:** all state is defined in Git. Drift is fixed in code, never by hand.

## Technical Decisions

- **Layers:** L0 Bootstrap (`infra/bootstrap`, human-applied) and L1 Persistent (`infra/persistent`, CI-applied) are the only layers that survive Teardown. A layer reads only from layers below it. There are exactly four Terraform roots (the other two are `infra/ephemeral/core` and `infra/ephemeral/gitops`). Shared code goes in `infra/modules/`, and a root never calls another root.
- **State:** one S3 bucket, versioned with `prevent_destroy`. Each root's key is `<root-path>/terraform.tfstate`, and locking uses S3 native locking (`use_lockfile = true`) with no DynamoDB table. L0's first apply uses local state and then migrates into the bucket.
- **Cross-root handoff:** only through SSM parameters `/k8s-on-aws/<bootstrap|persistent|core|session>/<name>`, read with `aws_ssm_parameter`. `terraform_remote_state` is forbidden, and a CI check enforces this. L0 publishes the bucket name and role ARNs. L1 publishes `domain`, `zone_id`, `cognito_issuer`, `oauth2_client_id` and `probe_client_id`.
- **What L0 creates:** the state bucket; the GitHub OIDC provider; the CI roles `ci-plan` (read-only, `pull_request` subject), `ci-apply` (only the `environment:persistent` and `environment:ephemeral` subjects) and `ci-image` (ECR push, `main` only); budgets with SNS email; and the SSM parameters `/k8s-on-aws/session/state` (initial value `none`, `ignore_changes` on the value) and `/k8s-on-aws/session/id`. Through the `integrations/github` provider it also creates the GitHub environments `persistent` and `ephemeral` with protection rules, plus a `main` ruleset that requires a PR for every change, with a bypass only for `github-actions[bot]`.
- **Bot commits:** titled `chore(bot): …`. They may touch only image-tag bumps under `gitops/workloads/` and `docs/rebuild-log/`, and they must not trigger `pr-plan`, `persistent-apply` or `ephemeral-apply`.
- **Workflows in this epic:**
  - `pr-plan` assumes `ci-plan` and posts the plan for each affected root as a PR comment. It includes L0 but never applies it.
  - `persistent-apply` runs on merges to `main` that touch `infra/persistent`, in the `persistent` environment as `ci-apply`.
  - Runners are `ubuntu-24.04`.
- **L1 starting point:** a minimal root (backend, providers, `default_tags` with `Layer=persistent`, SSM reads from L0). It later grows the zone, Cognito, ECR and secrets. The architecture also places AMP, the log group and the alert SNS topic in L1, but those belong to later epics.
- **DNS:** the domain is `yahiahussein.dev` (HSTS-preloaded, so HTTPS only). L1 adopts the zone that registration created through a data source, never creates a second zone, and sets the SOA negative-caching TTL to 60 s.
- **Cognito:**
  - One user pool with `prevent_destroy` and a hosted-UI domain.
  - An `oauth2-proxy` client: confidential, authorization-code flow, callback `https://app.<domain>/oauth2/callback`.
  - A `probe` client with `ALLOW_USER_PASSWORD_AUTH`.
  - Users come from an `app_users` variable as `aws_cognito_user` resources with verified emails and `random_password` passwords. Passwords are stored in `k8s-on-aws/probe/credentials` and `k8s-on-aws/app-users/<username>`. The runbook notes that they also exist in the private, encrypted state bucket.
- **ECR:** repositories `k8s-on-aws/app` and `k8s-on-aws/probe`, with tag immutability, `prevent_destroy` and a lifecycle policy that keeps the 20 newest images. `ci-image` can push to them and `ci-plan` cannot.
- **Secrets:** named `k8s-on-aws/<consumer>/<name>`. This epic creates `k8s-on-aws/oauth2-proxy/client-secret` and `k8s-on-aws/oauth2-proxy/cookie-secret` (a generated value).
- **Tags:** applied through `default_tags`: `Project=k8s-on-aws`, `Layer=bootstrap|persistent`, `ManagedBy=terraform`.
- **Naming and versions:** names use the prefix `k8s-on-aws-`. Every provider and module is pinned exactly: Terraform 1.17.0, AWS provider 6.70.0, AWS CLI ≥ 2.32.
- **Conventions doc:** `docs/conventions.md` must state:
  - naming prefixes
  - the `session_id` format (`s` + UTC `YYYYMMDD-HHMM`, lowercase)
  - tags, namespaces and the `app.kubernetes.io/*` labels
  - the exact version-pinning rule
  - JSON log fields (`ts`, `level`, `msg`, `session_id`)
  - commit conventions (Conventional Commits, `fault(<incident>)`, `fix(pm-<n>)`)
  - the rule that every real problem on the live Platform is logged in `docs/writeups/_journal.md`
- **Repo skeleton:**
  - `infra/{bootstrap,persistent,ephemeral/core,ephemeral/gitops,modules}`
  - `infra/workload-identities.yaml`: an empty registry with its `{namespace, serviceAccount, policy}` schema documented
  - `gitops/{root,platform,workloads}`, `app/`, `probe/`, `faults/`, `scripts/`
  - `docs/{adr,runbooks,postmortems,writeups,rebuild-log}`
  - `.github/workflows/`
- **Docs layout:** ADRs go in `docs/adr/NNNN-<slug>.md` (MADR format). Runbooks go in `docs/runbooks/`, including `bootstrap.md`.

## Cross-Story Dependencies

- Story 1.1 comes first. Every later story places files in its tree and must update `docs/components.md` and `docs/cost-model.md`.
- Story 1.2 must run before 1.3: the CI roles, GitHub environments, ruleset and state bucket must exist. Story 1.3 must run before 1.4 to 1.6, because they are L1 changes applied by `persistent-apply`.
- Story 1.5's callback URL and the Story 1.4 domain must agree. Story 1.6's ECR feeds `ci-image` (from 1.2) for Epic 3's image builds.
- **What later epics depend on:**
  - Epic 2 reads the L0 Session parameters and the `ephemeral` environment.
  - Epic 3 consumes the Cognito outputs, oauth2-proxy secrets, ECR and the zone.
  - Epic 4 uses the Probe client and user.
  - `scripts/teardown-check/allowlist.yaml` (Epic 2) must list everything this epic creates.
