---
status: final
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-Kubernetes-on-AWS-2026-10-27/prd.md
  - _bmad-output/planning-artifacts/prds/prd-Kubernetes-on-AWS-2026-10-27/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-Kubernetes-on-AWS-2026-10-28/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-Kubernetes-on-AWS-2026-10-28/README-architecture.md
---

# Kubernetes-on-AWS - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Kubernetes-on-AWS, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Bootstrap and Persistent Footprint**

- FR-1: The Operator creates the entire Persistent Footprint by running Bootstrap once against an empty AWS account, using a Terraform configuration separate from the Ephemeral Stack. Bootstrap uses short-lived admin credentials and never creates or stores long-lived access keys. After Bootstrap, the pipeline runs Rebuild and Teardown with no further human credentials. Teardown never destroys or changes a Persistent Footprint resource. Re-applying the Persistent Footprint on an unchanged account produces no diff. The Bootstrap runbook lists its manual steps, and only these are allowed: domain registration and contact-email verification; confirming the budget and alert email subscriptions; the one-time migration of Bootstrap's local state into the state bucket.
- FR-2: The Operator registers a domain, and a hosted zone for it gives the App a public HTTPS hostname. The App is reachable at a stable hostname after every Rebuild with no manual DNS edits. Teardown removes the DNS records the Rebuild created and leaves the hosted zone. TLS certificates are issued and validated automatically, during Rebuild (AD-11).
- FR-3: The Cognito user pool, the container image registry and persistent secrets survive Teardown. An App User created before a Teardown can sign in after the next Rebuild. A Rebuild does not rebuild or push container images.

**Network**

- FR-4: The Rebuild creates a VPC across at least two AZs in us-east-1, with public and private subnets, a cost-optimized NAT path, and free gateway endpoints for S3 and DynamoDB. Nodes and RDS run only in private subnets. Traffic from private subnets to S3 does not pass through NAT. An ADR records the network design (CIDR plan, subnet layout, NAT choice).
- FR-5: Network policies are enforced in the cluster, and the App namespace defaults to deny. A pod without an explicit allow rule cannot reach the App pods or the RDS endpoint.
- FR-6: The Operator documents the path of a request from the internet through DNS, the load balancer and Gateway API ingress to the App pod, with commands and outputs from the live Platform showing each hop.

**Cluster and Identity**

- FR-7: The Rebuild creates an EKS cluster on a version in standard support, with a small Spot managed node group. A version entering extended support fails a pre-flight check.
- FR-8: The Operator performs at least one EKS minor version upgrade and one node rotation, and documents each: plan, steps, and observed impact on the App's SLIs.
- FR-9: Pods get AWS permissions through EKS Pod Identity, with an ADR comparing Pod Identity and IRSA. Humans get cluster access through EKS access entries, with no shared kubeconfig credential. CI reaches AWS through GitHub Actions OIDC federation using roles created by Bootstrap. No long-lived AWS keys exist anywhere.
- FR-10: The App authenticates to RDS with IAM database authentication, and no static database password exists. Any remaining secret (such as the SSO proxy's cookie secret) is a persistent secret in AWS Secrets Manager and never committed to Git. No Rebuild fails because of how a secret was deleted or named in an earlier Session.
- FR-11: Every workload declares CPU and memory requests and limits. The Operator documents how the node group is sized against those requests.
- FR-33: The Operator writes up at least two real troubleshooting cases from the live Platform, each covering the symptom, commands used, findings and fix.

**Delivery Pipeline**

- FR-12: A PR to the infrastructure code triggers a plan whose output is visible on the PR. Pipeline jobs authenticate to AWS only through OIDC. A merged change to the Persistent Footprint is applied automatically, except the Bootstrap layer (state backend, CI trust roles, budgets), which CI only plans and the Operator applies. A merged change to the Ephemeral Stack is applied only while a Session is active. Outside a Session, a merge runs a plan only and never creates billable resources.
- FR-13: Argo CD owns every in-cluster resource, App included, and syncs it from Git after a Rebuild with no manual `kubectl apply`. Reverting a commit restores the previous App version within one sync cycle.
- FR-14: Public traffic reaches the App through a Gateway API implementation. An ADR records the ingress choice.

**App and Data**

- FR-15: Only App Users authenticated through Cognito SSO at the edge can log a workout or list their own workouts. An unauthenticated request is redirected to sign-in and never reaches App code. An App User sees only their own workouts.
- FR-16: Teardown takes a final RDS snapshot with a unique identifier. Rebuild restores the RDS instance from the most recent snapshot. When no snapshot exists, Rebuild creates an empty database and runs schema setup instead of failing. Workouts logged before a Teardown appear after the next Rebuild (RPO = 0 for a planned Teardown). Only the 5 most recent final snapshots are kept; older ones are deleted automatically. Applying a change during a Session never replaces the live RDS instance.

**Observability and SLOs**

- FR-17: The Platform collects metrics and logs from the edge, the App and the cluster, and alerts on SLO burn rate and on node or pod failure.
- FR-32: The Synthetic Probe runs throughout every Session from M2 onward and generates enough authenticated traffic that each Session's Error Budget allows at least 5 failed requests. When sign-in is broken, the Probe fails and the sign-in SLI drops even though App code never runs.
- FR-18: The App has three SLOs, measured at the edge and evaluated per Session: sign-in ≥ 99% success; availability ≥ 99% of requests succeed; latency ≥ 95% of requests < 500 ms. When the Error Budget is exhausted, the change that exhausted it is reverted rather than patched forward. A dashboard shows current SLI values, remaining Error Budget and burn rate. At least one ship-or-revert decision recorded in the repo cites the Error Budget.
- FR-19: SLI and SLO results from past Sessions stay queryable after Teardown, so trends span Sessions. The store is part of the Persistent Footprint (AMP, per AD-13).

**Session Lifecycle and DR Drills**

- FR-30: The Operator starts a Rebuild and a Teardown as separate, manually triggered pipeline runs. Neither runs automatically on a merge.
- FR-20: Once Bootstrap has run, a Rebuild takes the account from only the Persistent Footprint to a complete Rebuild with zero manual steps. Any manual step in Drills 1–5 is recorded in the Rebuild Log as a defect and removed in code. From the end of M2, every Drill has zero manual steps.
- FR-31: Teardown leaves no billable Ephemeral Stack resource behind, including controller-created load balancers, volumes and DNS records. A post-Teardown check lists the account's billable resources, finds only Persistent Footprint resources, and fails loudly otherwise.
- FR-21: Every Drill appends a Rebuild Log entry; the pipeline records the RTO, not a stopwatch. RTO is baselined over the first 5 Drills. A Drill whose RTO exceeds 45 minutes is a failed Drill and gets a cause recorded. At the end of M2, the median RTO of the last 5 Drills is lower than the baseline median, with each improvement logged with its cause. Platform RTO and Service RTO are logged separately.
- FR-22: At least once, the Operator recovers the database from automated backups without a fresh final snapshot and records the resulting RPO. Automated backups must survive destruction of the RDS instance.

**Hardening**

- FR-23: A CIS EKS benchmark scan runs against the cluster, and its results and accepted exceptions are documented. Pod Security Standards are enforced on App namespaces.
- FR-24: Admission policies (Kyverno) are introduced only as Postmortem Action Items, and each policy links to the Postmortem that motivated it.

**Incident Drills**

- FR-25: The Operator can inject each fault type repeatably: bad deploy, auth outage (identity provider or SSO proxy path broken), node failure, network fault. Bad-deploy, auth and network faults are injected as merged Git changes. A node failure may be injected by a scripted command kept in the repo.
- FR-26: Exactly three committed Incidents are run: a bad deploy, an auth outage, and a node or network failure. Each has a declared commander, a timestamped timeline, and status communications written as they would be sent.
- FR-27: Each Incident has a blameless Postmortem that records what monitoring caught and what it missed, at least one Action Item merged as a PR, and a re-test in which the same fault is injected again after the Action Item ships, with the result recorded.

**Evidence and Documentation**

- FR-28: The README links, within one screen, to the architecture diagram, the ADR index, the Rebuild Log, the Postmortems, the packet-path write-up and the troubleshooting write-ups.
- FR-29: At least 4 ADRs exist by the end of M2: network design, Pod Identity versus IRSA, ingress, and RDS. Together they cover what was deliberately left out (full service mesh, multi-environment promotion).

### NonFunctional Requirements

- NFR-1 Cost: actual AWS spend stays under $30/month, with a hard cap of $50/month. The billing alarm alerts before the cap. Teardown at the end of each Session is the default; an Ephemeral Stack left running overnight is a cost defect. The Persistent Footprint's monthly cost is tracked in the cost model.
- NFR-2 Security: no long-lived credentials anywhere (AWS keys, database passwords, kubeconfig tokens) and no credentials in Git. Bootstrap uses short-lived credentials only. Least-privilege IAM for each identity. Private subnets for nodes and data.
- NFR-3 Reproducibility: all Platform state is defined in Git. Any drift found during a Drill is fixed in code, not by hand.
- NFR-4 Region and tenancy: single AWS account, single environment, us-east-1.
- NFR-5 Rebuild duration: RTO ≤ 45 minutes per Drill, with a falling median (FR-21). Stretch: Service RTO ≤ 30 minutes.
- NFR-6 Explainability: every Platform component is covered by an ADR, runbook or write-up the Operator can explain without notes. A component that can't be explained is removed or documented before M3.

### Additional Requirements

**Starter template:** none. The architecture specifies no starter or greenfield template. Epic 1 Story 1 should instead set up the repo skeleton from the architecture's source tree (`infra/{bootstrap,persistent,ephemeral/core,ephemeral/gitops,modules}`, `infra/workload-identities.yaml`, `gitops/{root,platform,workloads}`, `app/`, `probe/`, `faults/`, `scripts/`, `docs/`, `.github/workflows/`) along with Bootstrap.

**Layering and Terraform structure**

- AD-1: Five layers (L0 Bootstrap, L1 Persistent, L2 Ephemeral core, L3 GitOps handoff, L4 In-cluster). Every resource belongs to exactly one layer, and a layer reads only from layers below it. Only L0/L1 survive Teardown.
- AD-2: Exactly four Terraform roots, each with its own key `<root-path>/terraform.tfstate` in one S3 state bucket. S3 native locking (`use_lockfile = true`), no DynamoDB lock table. Kubernetes/Helm providers only in `infra/ephemeral/gitops`. Shared code in `infra/modules/`; a root never calls another root.
- AD-3: Cross-root handoff only through SSM parameters `/k8s-on-aws/<bootstrap|persistent|core|session>/<name>`, read via `aws_ssm_parameter`. `terraform_remote_state` is forbidden.
- AD-4 (GitOps Bridge): Terraform owns every AWS-side resource (including controller IAM roles and Pod Identity associations); Argo CD owns every Kubernetes object, except L3 installs Argo CD and the root app-of-apps. L3 passes values to L4 only as annotations on the Argo CD in-cluster cluster Secret, from a closed set: `cluster_name`, `region`, `account_id`, `vpc_id`, `session_id`, `phase`, `domain`, `app_hostname`, `cert_arn`, `cognito_issuer`, `oauth2_client_id`, `probe_client_id`, `amp_remote_write_url`, `amp_query_url`, `log_group`, `rds_endpoint`, `rds_master_secret_arn`. ApplicationSets template Helm values only from these. CI rejects AWS account IDs and `arn:` literals under `gitops/`. Argo CD reads the public repo over anonymous HTTPS. No `kubectl apply` and no `kubernetes_*` resources outside L3.

**Session lifecycle and Teardown**

- AD-5: SSM `/k8s-on-aws/session/state` (created in L0, `ignore_changes` on value) holds `none | building | active | tearing-down | failed`; `/k8s-on-aws/session/id` holds the current `session_id`. Only `rebuild` and `teardown` write the state. `ephemeral-apply` applies only in `active`; otherwise CI does a full L2 plan, `validate` for L3, render + lint for `gitops/`. Rebuild rejects a `session_id` whose snapshot or log already exists. All L2–L4 workflows share concurrency group `ephemeral` with `cancel-in-progress: false`. A watchdog emails the Operator if state is `active` for > 4 hours.
- AD-6: Every resource is tagged `Project=k8s-on-aws`, `Layer=bootstrap|persistent|ephemeral`, plus `Session=<session_id>` on ephemeral resources, and `ManagedBy=terraform|lbc|external-dns`. Terraform uses `default_tags`; LBC uses `--default-tags` from bridge annotations. RDS `copy_tags_to_snapshot = false`; Teardown retags the final snapshot and retained automated backup `Layer=persistent`. No per-Session KMS keys. The post-Teardown check runs a Tagging API query for `Layer=ephemeral` plus a sweep of billable types (EC2, EBS, ELBv2, EIP/public IPv4, RDS instances, ENI) against `scripts/teardown-check/allowlist.yaml`, confirms hits with describe calls, ignores resources pending deletion, and retries before failing loudly.
- AD-7: Fixed Teardown order: state = tearing-down → apply L3 with `phase=draining` (ApplicationSets for workloads and the Gateway select `phase=active`, so Argo CD cascade-deletes them) → poll until the ALB and app DNS records are gone → destroy L3 → destroy L2 (final snapshot `k8s-on-aws-final-{session_id}`) → retag survivors and prune snapshots/backups → write the Rebuild Log → post-Teardown check → state = none. Teardown never mutates the cluster with `kubectl` or `argocd`.
- AD-8: The cluster is stateless: no PVCs, no EBS CSI driver. Durable state only in RDS, AMP, CloudWatch Logs, S3 (state bucket and `evidence/`) and Git.

**Data**

- AD-9: Rebuild (not Terraform) finds the newest final snapshot and passes it to L2 as `restore_snapshot_id` (empty = fresh database); `restore_mode=pitr` restores from the retained automated backup. `snapshot_identifier` is under `ignore_changes`. Automated backups: 1-day retention, `delete_automated_backups = false`. Teardown keeps the 5 newest final snapshots and the newest retained backup. RDS restore and EKS creation have no Terraform dependency, so they run in parallel.
- AD-10: The master password is RDS-managed; Rebuild runs `modify-db-instance --manage-master-user-password` after every restore. `db-init` (PreSync wave -2, idempotent: waits for the secret to be `active`, creates role `app`, grants `rds_iam`) and `migrate` (PreSync wave -1, schema migrations owned by `app/`) are Argo CD hooks. The App and `migrate` connect only as `app` via IAM database authentication.

**Edge, App contract and identity**

- AD-11: The only public path is Route 53 → ALB → oauth2-proxy → App. The LBC Gateway API creates the ALB from one Gateway `public` in namespace `gateway`. The ALB terminates TLS with an ACM certificate issued by L2 on each Rebuild (L2 waits for `ISSUED` and passes the ARN to `LoadBalancerConfiguration.defaultCertificate`). oauth2-proxy uses Cognito OIDC. The App identifies users only by Cognito `sub` in `X-Forwarded-User` and returns 401 when missing. `app.<domain>` is the only public hostname; Operator UIs use `kubectl port-forward`.
- AD-23: `POST /api/workouts` `{type, duration_min, performed_at}` → `201` with the created workout; `GET /api/workouts` → `200` `{items:[{id, type, duration_min, performed_at}]}` with only the caller's workouts; `GET /healthz` → `200`, kubelet only, not publicly routed. Errors are `{error:{code, message}}`, 401 when there is no identity. IDs are UUIDv7; timestamps RFC 3339 UTC. The schema belongs to `app/`.
- AD-17: Secrets live in L1 Secrets Manager as `k8s-on-aws/<consumer>/<name>` and reach pods only through `ExternalSecret` read by a namespace-scoped `SecretStore` assuming a per-consumer role limited to `k8s-on-aws/<consumer>/*`. `ClusterSecretStore` is forbidden. The only exception is the RDS-managed master secret (ARN via the bridge), readable only by the `app` namespace store used by `db-init`.
- AD-18: L0 creates three GitHub-OIDC CI roles: `ci-plan` (read-only, `pull_request`), `ci-apply` (only `environment:persistent` and `environment:ephemeral` subjects), `ci-image` (ECR push, `main` only). The Operator uses an MFA-protected IAM admin user with no access keys, with CLI sessions from `aws login`. The Operator and `ci-apply` get cluster access via EKS access entries; the API endpoint is public + private. Only a human applies L0. (This supersedes the PRD addendum's IAM Identity Center / `aws sso login` suggestion.)
- AD-19: The hosted zone is the one Route 53 registration creates. L1 references it via a data source and sets its SOA negative TTL to 60 s. L2 owns ACM validation records. ExternalDNS owns the `app.<domain>` records with `--policy=sync`, `--txt-owner-id=k8s-on-aws`, `--txt-prefix=_extdns-%{record_type}.`, `--domain-filter=app.<domain>`, `--source=gateway-httproute`, `--gateway-namespace=gateway`. No manual edits.
- AD-21: `infra/workload-identities.yaml` is the only list of `{namespace, serviceAccount, policy}`. L2 creates Pod Identity associations and roles (prefix `k8s-on-aws-eph-`) from it. Charts render exactly those service account names, and CI checks rendered `gitops/` against the registry.
- AD-22: VPC CNI add-on with `enableNetworkPolicy=true`. Every first-party namespace has default-deny for ingress and egress, with explicit allows for DNS, control plane → webhooks, ALB → oauth2-proxy, oauth2-proxy → App, App/`db-init`/`migrate` → RDS:5432, and workloads → AWS APIs and the public hostname where needed. Pod Security: `restricted` on `app` and `probe`; `privileged` only on `observability` and `security`; `baseline` elsewhere. Every container sets CPU and memory requests and limits.

**Observability**

- AD-12: The in-cluster Probe signs in fresh every 10 s with Cognito `InitiateAuth` (own client, test user with verified email), then calls `POST` and `GET /api/workouts` on the public hostname with the ID token as Bearer (≥ 500 cycles per 2-hour Session). oauth2-proxy accepts the token via `--skip-jwt-bearer-tokens` and `--extra-jwt-issuers=<issuer>=<probe_client_id>`. The SLIs are exactly `probe_signin_total{result}`, `probe_requests_total{feature="log|list",result}`, and histogram `probe_request_duration_seconds{feature}` with a `0.5` bucket. Every series carries `session_id` (Alloy external label). SLOs, burn-rate alerts, the Service ready point and the Session summary derive only from these. The hosted-UI redirect is a documented monitoring gap.
- AD-13: Alloy remote-writes to one L1 AMP workspace (365-day retention) via SigV4/Pod Identity; no in-cluster Prometheus. Alert rules live in AMP (Terraform, L1) and alert via SNS email; no rule may fire when no Session series exists (no unguarded `absent()` / `up == 0`). Logs go over OTLP/HTTP with SigV4 to one L1 CloudWatch log group (14-day retention), falling back to the CloudWatch Observability add-on if the M1 spike fails. Grafana is ephemeral (L4) with dashboards from Git, querying AMP. Ingest budget ≤ 40M samples/month via an Alloy allowlist and a 60 s scrape interval.

**Delivery and build**

- AD-14: Bad-deploy, auth and network faults are PRs applying a patch from `faults/<incident>/` and creating `faults/ACTIVE`; recovery is `git revert`. Node failure uses `scripts/faults/node-terminate.sh`. Auth faults change only L4 (oauth2-proxy issuer, JWKS or client config), never L1 Cognito. The Rebuild pre-flight fails while `faults/ACTIVE` exists on `main`. A re-test re-applies the same patch. No chaos framework in v1.
- AD-15: arm64 everywhere: Graviton Spot `t4g.*` nodes, fck-nat on `t4g.nano`, first-party images built only for `linux/arm64` on `ubuntu-24.04-arm`, and every third-party image must publish arm64.
- AD-16: On a merge touching `app/` or `probe/`, CI (`ci-image`) pushes `sha-<git-sha>` to ECR (tag immutability on). The deploy is a separate bot commit bumping the tag under `gitops/workloads/`. Rollback is `git revert` of the bump commit.
- AD-25: The bot (`github-actions[bot]`, via a ruleset bypass) may commit only image-tag bumps under `gitops/workloads/` and `docs/rebuild-log/`, titled `chore(bot): …` and excluded from `pr-plan` and `ephemeral-apply` triggers. Rebuild writes timings to `s3://<state-bucket>/evidence/<session_id>/rebuild.json`; Teardown is the only writer of the Rebuild Log record and writes one even when the Rebuild failed.
- Workflows: `pr-plan`, `persistent-apply`, `ephemeral-apply`, `image-build`, `rebuild` (dispatch), `teardown` (dispatch), `session-watchdog` (schedule).

**Bootstrap and guards**

- AD-24: Bootstrap runs once with `aws login` credentials. The first L0 apply uses local state, then migrates into the bucket it created. Bootstrap creates GitHub environments and their protection via the `integrations/github` provider, and AWS Budgets at $30 actual and $45 forecast, alerting via SNS email.
- AD-26: `prevent_destroy` on the state bucket, Cognito pool, AMP workspace and ECR. ECR lifecycle policy keeps the 20 newest images. `scripts/teardown-check/allowlist.yaml` is the closed list of what may persist; adding to it requires an ADR.

**Rebuild Log**

- AD-20: One file per Drill, `docs/rebuild-log/<session_id>.json`, with `session_id`, `started_at`, `platform_ready_at`, `service_ready_at`, `platform_rto_s`, `service_rto_s`, `rpo_s`, `restore_mode`, `snapshot_id`, `manual_steps[]`, `failures[]`, `slo_summary{signin,availability,latency,budget_remaining}`, `notes`. Platform ready = nodes Ready and RDS `available`. Service ready = first `probe_requests_total{result="success"}` sample for the `session_id` in AMP. `docs/rebuild-log.md` is generated from these files, never hand-edited.

**Conventions**

- Naming: prefix `k8s-on-aws-` (ephemeral IAM `k8s-on-aws-eph-`); EKS cluster name is the constant `k8s-on-aws`. `session_id` = `s` + UTC `YYYYMMDD-HHMM`, lowercase, valid as an RDS suffix, Kubernetes label and Prometheus label.
- Namespaces: `argocd`, `gateway`, `app` (App, oauth2-proxy, DB Jobs), `probe`, `observability`, `security`, `external-dns`, `external-secrets`, `kyverno`; AWS add-ons and LBC in `kube-system`. Labels `app.kubernetes.io/{name,part-of,component}` with `part-of=k8s-on-aws`.
- Versions: every provider, module, chart and image pinned exactly (Stack table: Terraform 1.17.0, AWS provider 6.70.0, EKS module 21.29.0, VPC module 6.7.3, fck-nat module 1.6.1, EKS 1.36, VPC CNI 1.23.2, LBC 3.6.2, Gateway API CRDs 1.6.3, ExternalDNS 0.24.0, ESO 2.14.0, Argo CD 3.5.6, oauth2-proxy 7.15.5, Alloy 1.21.2, k8s-monitoring chart 4.5.5, Grafana 13.3.0, Kyverno 1.19.2, RDS PostgreSQL 17.11 on `db.t4g.micro`, Python 3.14, FastAPI 0.162.0, psycopg 3.3.6, uv 0.13.6). The EKS version is one variable, and the Rebuild pre-flight requires `describe-cluster-versions` to report `STANDARD_SUPPORT`.
- Logs: JSON lines to stdout with `ts`, `level`, `msg`, `session_id`.
- Docs: `docs/adr/NNNN-<slug>.md` (MADR); `docs/runbooks/`; `docs/postmortems/YYYY-MM-DD-<slug>.md`; `docs/writeups/`; `docs/components.md` maps every Terraform root and Argo CD app to its ADR or runbook, and CI fails on any unlisted component (NFR-6).
- Commits: Conventional Commits; `fault(<incident>): …` for fault injections; `fix(pm-<n>): …` for Action Items, linking the Postmortem.

**Spikes, constraints and open items**

- M1 smoke-test spikes: Alloy logs over OTLP to CloudWatch with Pod Identity SigV4; ExternalDNS creating an alias record for an LBC Gateway; Terraform behavior of `manage_master_user_password` after a restore. Each has a fallback per AD-13 / AD-10.
- Deferred to epics: CIDR plan, subnet sizes, node instance mix and count (minimum 2 nodes across 2 AZs), recorded in ADRs; SLO window maths and burn-rate thresholds (must use AD-12 series); remaining oauth2-proxy flags (within AD-11/AD-12).
- Domain: `yahiahussein.dev` (decided 2026-10-28; the `.dev` registry showed it unregistered that day; Route 53 availability still to be confirmed at registration). `.dev` is HSTS-preloaded, so every hostname must serve HTTPS, which the ALB/ACM design already does.
- Known pitfalls (PRD addendum): use a snapshot lookup that tolerates an empty result; Secrets Manager names stay reserved 7–30 days after deletion; controller-created resources must be deleted and confirmed gone before VPC destroy; RDS restore adds ~10–20 minutes to a Rebuild.
- Effort constraints: App capped at 8–10 hours (extras go on a "someday" list); 75–90 usable hours total over 6–8 weeks; de-scope order is M3 stretch → FR-33 to one case → FR-8 moved to M3; Incident work (FR-25–FR-27) is never cut.
- Milestones: M1 Foundation (FR-1–5, 7, 9, 10, 11, 16, 20, 30, 31; FR-21 with Platform RTO); M2 Delivery and visibility (FR-6, 8, 12–15, 17–19, 23, 28, 29, 32, 33; FR-21 switches to Service RTO); M3 Incidents (FR-22, 24–27); M3 stretch: service-mesh ADR plus minimal mTLS demo.

### UX Design Requirements

N/A. No UX design contract exists, and none is needed: the App has no frontend beyond its two API features behind edge SSO (PRD §7). Sign-in uses the Cognito hosted UI via oauth2-proxy.

### FR Coverage Map

Several FRs are delivered incrementally across epics; each line names the part each epic delivers.

- FR-1: Epic 1 - Bootstrap creates the Persistent Footprint from code
- FR-2: Epic 1 - domain registration and hosted zone; Epic 3 - stable `app.<domain>` hostname, per-Rebuild ACM certificate, ExternalDNS records removed at Teardown
- FR-3: Epic 1 - Cognito pool, ECR and Secrets Manager in L1; Epic 3 - App User signs in after a Rebuild, Rebuild never builds or pushes images
- FR-4: Epic 2 - hand-designed multi-AZ VPC with fck-nat and gateway endpoints, plus network ADR
- FR-5: Epic 3 - default-deny network policies (enforcement switched on in Epic 2's VPC CNI add-on)
- FR-6: Epic 5 - packet-path write-up from the live Platform
- FR-7: Epic 2 - EKS on standard support with Spot node group and pre-flight version check
- FR-8: Epic 5 - EKS minor upgrade and node rotation with observed SLI impact
- FR-9: Epic 1 - GitHub OIDC CI roles; Epic 2 - Pod Identity (registry, associations, ADR) and EKS access entries
- FR-10: Epic 2 - RDS-managed master secret after restore; Epic 3 - IAM database authentication and ESO-delivered persistent secrets
- FR-11: Epic 2 - requests/limits convention and node-group sizing doc (every later workload follows it)
- FR-12: Epic 1 - `pr-plan`, `persistent-apply`, L0 plan-only; Epic 2 - `ephemeral-apply` gated on an active Session
- FR-13: Epic 2 - Argo CD installed by the L3 bridge and syncing from Git; Epic 3 - revert restores the previous App version within one sync
- FR-14: Epic 3 - Gateway API ingress via LBC, plus ingress ADR
- FR-15: Epic 3 - authenticated App; unauthenticated requests never reach App code; users see only their own workouts
- FR-16: Epic 2 - final snapshot, restore-or-fresh, retention of 5, no mid-Session replacement; Epic 3 - workouts survive Teardown (RPO = 0)
- FR-17: Epic 4 - metrics, logs, burn-rate and node/pod alerts
- FR-18: Epic 4 - three per-Session SLOs, Error Budget dashboard, recorded ship-or-revert decision
- FR-19: Epic 4 - SLO history in L1 AMP, queryable across Sessions
- FR-20: Epic 2 - zero-touch Rebuild, manual steps logged as defects; Epic 4 - zero manual steps on every Drill from end of M2
- FR-21: Epic 2 - Rebuild Log with Platform RTO and baseline; Epic 4 - Service RTO and falling median
- FR-22: Epic 6 - unplanned data-loss exercise (PITR from retained automated backup)
- FR-23: Epic 5 - CIS kube-bench scan with exceptions, Pod Security Standards
- FR-24: Epic 6 - Kyverno policies introduced as Postmortem Action Items
- FR-25: Epic 6 - repeatable fault injection through Git, plus node-terminate script
- FR-26: Epic 6 - three Incidents run end to end
- FR-27: Epic 6 - Postmortems with shipped, re-tested Action Items
- FR-28: Epic 5 - scannable README
- FR-29: Epic 2 - network, Pod Identity and RDS ADRs; Epic 3 - ingress ADR; Epic 5 - ADR index and deliberately-left-out coverage
- FR-30: Epic 2 - Operator-triggered `rebuild` and `teardown` workflows
- FR-31: Epic 2 - fixed Teardown order and post-Teardown check; Epic 3 - draining of controller-created ALB and DNS records
- FR-32: Epic 4 - Synthetic Probe

NFRs are cross-cutting and appear as acceptance criteria in the relevant stories: NFR-1 (Epics 1, 2, 4), NFR-2 (Epics 1–3), NFR-3 (all), NFR-4 (all), NFR-5 (Epics 2, 4), NFR-6 (every epic, via `docs/components.md`).

## Epic List

### Epic 1: Bootstrap the account and make every Persistent change go through a PR
The Operator runs Bootstrap once against an empty account, with short-lived credentials and only the three allowed manual steps, and gets a Persistent Footprint (state bucket, CI OIDC roles, budgets, domain and zone, Cognito, ECR, Secrets Manager) that from then on changes only through the pipeline. PRs show a plan; merges to L1 apply automatically. Includes the repo skeleton (no starter template) and the `docs/components.md` CI check.
**FRs covered:** FR-1, FR-2 (domain and zone), FR-3 (persistent stores), FR-9 (CI OIDC), FR-12 (`pr-plan`, `persistent-apply`, L0 plan-only)

### Epic 2: Run a Session: Rebuild the platform from nothing and tear it down with nothing billable left
The Operator triggers `rebuild` and gets the hand-built multi-AZ VPC with fck-nat, EKS on standard support with Spot nodes, Pod Identity and access entries, RDS restored from the latest snapshot (or fresh on the first run), and Argo CD installed through the L3 bridge. They trigger `teardown` and get the final snapshot, the fixed-order destroy, snapshot pruning and a passing post-Teardown check. Includes the Session state machine and watchdog, Platform RTO in the Rebuild Log, `ephemeral-apply` gating, and the network, Pod Identity and RDS ADRs. Core of M1. The LBC and ExternalDNS are deliberately not installed here (Epic 3).
**FRs covered:** FR-4, FR-7, FR-9 (Pod Identity, access entries), FR-10 (RDS-managed master secret), FR-11, FR-12 (`ephemeral-apply` gating), FR-13 (Argo CD handoff), FR-16 (snapshot, restore, retention), FR-20, FR-21 (Platform RTO), FR-30, FR-31, FR-29 (network, Pod Identity, RDS ADRs)

### Epic 3: App Users sign in and log workouts at `app.<domain>`, and their data survives every Teardown
The full edge chain Route 53 → ALB (Gateway API) → oauth2-proxy + Cognito → App; the FastAPI App built to the AD-23 contract; IAM database auth with the `db-init` and `migrate` hooks; ESO secrets; default-deny network policies; ExternalDNS and a per-Rebuild ACM certificate; arm64 image builds with tag-bump deploys and revert as rollback. Teardown gains the `phase=draining` step so the ALB and DNS records are cleaned up. Planned-Teardown RPO = 0 is proven with real workouts. Includes the ingress ADR and the ExternalDNS spike.
**FRs covered:** FR-2 (hostname, TLS), FR-3 (sign-in survives Rebuild, no image rebuild), FR-5, FR-10 (IAM DB auth, ESO), FR-13 (revert within one sync), FR-14, FR-15, FR-16 (RPO = 0 with real data), FR-31 (controller-created resources), FR-29 (ingress ADR)

### Epic 4: The Operator sees users' pain before they complain: SLOs, Error Budgets and Service RTO
The Synthetic Probe (sign-in every 10 s); Alloy sending metrics to AMP and logs to CloudWatch; three per-Session SLOs with burn-rate and node/pod alerts that stay silent when no Session exists; Grafana dashboards from Git; the per-Session SLO summary in the Rebuild Log. RTO switches to Service RTO, and Drills meet the falling-median and zero-manual-step targets by the end of M2. Includes the first ship-or-revert decision citing the Error Budget.
**FRs covered:** FR-17, FR-18, FR-19, FR-32, FR-20 (zero-touch from M2), FR-21 (Service RTO, falling median)

### Epic 5: Harden, upgrade and explain the platform so a reviewer gets it in 5 minutes
CIS kube-bench scan with documented exceptions and Pod Security Standards; one EKS minor upgrade and one node rotation with observed SLI impact; the packet-path write-up; two troubleshooting write-ups; the ADR index closing FR-29 (including what was deliberately left out); the scannable README.
**FRs covered:** FR-6, FR-8, FR-23, FR-28, FR-29 (index and completion), FR-33

### Epic 6: Lead three real Incidents end to end and prove each fix holds
Git-delivered fault injection (`faults/`, the `faults/ACTIVE` leak guard) plus the node-terminate script; three Incidents (bad deploy, auth outage, node or network failure) each with a commander, timeline and status comms; blameless Postmortems that record what monitoring missed; Action Items merged as `fix(pm-n)` PRs, including Kyverno policies; re-tests. Also the unplanned data-loss (PITR) exercise with recorded RPO. M3, never cut.
**FRs covered:** FR-22, FR-24, FR-25, FR-26, FR-27

**Dependencies:** forward only, 1 → 2 → 3 → 4 → {5, 6}. Epic 5 (FR-8 SLI impact) and Epic 6 (detection) need Epic 4's SLIs; Epics 5 and 6 are independent of each other. The M3 stretch (service-mesh ADR and mTLS demo) is not an epic.

## Epic 1: Bootstrap the account and make every Persistent change go through a PR

The Operator runs Bootstrap once against an empty account, and from then on the Persistent Footprint changes only through the pipeline. PRs show a plan, merges to L1 apply automatically, and L0 is planned by CI but applied only by a human.

### Story 1.1: Repo skeleton, conventions and explainability check

As the Operator,
I want the repo laid out to match the architecture's source tree, with its conventions written down and enforced,
So that every later story has a fixed place to go and no component can ship without an explanation.

**Acceptance Criteria:**

**Given** an empty repo
**When** the skeleton story is merged
**Then** the directories exist: `infra/{bootstrap,persistent,ephemeral/core,ephemeral/gitops,modules}`, `gitops/{root,platform,workloads}`, `app/`, `probe/`, `faults/`, `scripts/`, `docs/{adr,runbooks,postmortems,writeups,rebuild-log}`, `.github/workflows/`
**And** `infra/workload-identities.yaml` exists as an empty registry with its schema (`{namespace, serviceAccount, policy}`) documented

**Given** `docs/components.md` maps every Terraform root and Argo CD app to its ADR or runbook
**When** a PR adds a root under `infra/` or an Argo CD Application under `gitops/` that is not listed
**Then** a CI check fails and names the missing component (NFR-6)

**Given** `docs/conventions.md`
**When** it is read
**Then** it states the naming prefixes, `session_id` format, tags, namespaces and labels, version-pinning rule, JSON log fields, and commit conventions (Conventional Commits, `fault(<incident>)`, `fix(pm-<n>)`)
**And** `docs/cost-model.md` exists with one row per Persistent Footprint item and its expected monthly cost (NFR-1)
**And** the conventions require logging every real problem met on the live Platform (date, `session_id`, symptom, first commands) in `docs/writeups/_journal.md` as it happens, as raw material for FR-33

### Story 1.2: Bootstrap L0 from an empty AWS account

As the Operator,
I want one Terraform root that I apply once, by hand, with short-lived credentials,
So that the account has a state backend, CI identities, budgets and Session state without any long-lived keys.

**Acceptance Criteria:**

**Given** an empty AWS account and an MFA-protected IAM admin user with no access keys
**When** the Operator follows `docs/runbooks/bootstrap.md` and applies `infra/bootstrap` with `aws login` credentials
**Then** it creates the S3 state bucket (versioned, `prevent_destroy`); the GitHub OIDC provider; roles `ci-plan` (read-only, `pull_request`), `ci-apply` (only `environment:persistent` and `environment:ephemeral` subjects) and `ci-image` (ECR push, `main` only); AWS Budgets at $30 actual and $45 forecast alerting through SNS email; and SSM `/k8s-on-aws/session/state` (value `none`, `ignore_changes`) and `/k8s-on-aws/session/id`
**And** it creates the GitHub environments `persistent` and `ephemeral` with protection rules through the `integrations/github` provider
**And** it creates a `main` branch ruleset through the same provider that requires a PR for every change, with a bypass only for `github-actions[bot]` (used for `chore(bot):` commits under `gitops/workloads/` and `docs/rebuild-log/`, per AD-25)
**And** every resource carries `Project=k8s-on-aws`, `Layer=bootstrap`, `ManagedBy=terraform` through `default_tags`
**And** values needed upstream (bucket name, role ARNs) are published as `/k8s-on-aws/bootstrap/<name>` SSM parameters

**Given** the first apply used local state
**When** the Operator runs the documented one-time migration
**Then** the state lives at `infra/bootstrap/terraform.tfstate` in the bucket with `use_lockfile = true` and no DynamoDB table

**Given** a bootstrapped, unchanged account
**When** `infra/bootstrap` is planned again
**Then** the plan shows no changes
**And** the runbook lists exactly the allowed manual steps (state migration, email subscription confirmations, domain registration) and no others (FR-1)
**And** no IAM access key exists in the account (NFR-2)

### Story 1.3: Plan every PR and apply Persistent changes on merge

As the Operator,
I want PRs to show a Terraform plan and merged L1 changes to be applied by CI,
So that the Persistent Footprint changes only through reviewed code and the Bootstrap layer is never changed by CI.

**Acceptance Criteria:**

**Given** a PR touching `infra/`
**When** the `pr-plan` workflow runs
**Then** it assumes `ci-plan` through OIDC and posts the plan for each affected root as a PR comment
**And** it plans `infra/bootstrap` but never applies it (AD-18)

**Given** a merge to `main` touching `infra/persistent`
**When** the `persistent-apply` workflow runs in the `persistent` environment
**Then** it assumes `ci-apply` through OIDC and applies L1
**And** L1 starts as a minimal root (backend, providers, `default_tags` with `Layer=persistent`, SSM reads from L0) that applies cleanly

**Given** a bot commit titled `chore(bot): …`
**When** it lands on `main`
**Then** neither `pr-plan` nor `persistent-apply` is triggered (AD-25)
**And** no workflow contains AWS keys; every job reaches AWS only through OIDC (FR-9, FR-12)
**And** a CI check fails if `terraform_remote_state` appears anywhere under `infra/` (AD-3)

### Story 1.4: Register the domain and adopt its hosted zone

As the Operator,
I want the registered domain's hosted zone referenced from L1 with negative caching tuned,
So that every Rebuild can publish `app.yahiahussein.dev` with no manual DNS edits and no slow negative-cache delays.

**Acceptance Criteria:**

**Given** the Operator has registered `yahiahussein.dev` through Route 53 and verified the contact email, as the runbook documents
**When** L1 is applied with the `domain` variable set
**Then** L1 reads the hosted zone created by registration through a data source and creates no second zone (AD-19)
**And** the zone's SOA negative-caching TTL is 60 s
**And** `/k8s-on-aws/persistent/domain` and `/k8s-on-aws/persistent/zone_id` are published

**Given** an unchanged L1
**When** it is planned again
**Then** there are no changes
**And** the hosted zone and domain registration costs are in `docs/cost-model.md`

### Story 1.5: Cognito user pool with App and Probe clients and users

As an App User,
I want my account to live in a user pool that survives every Teardown,
So that I can sign in after any Rebuild without signing up again.

**Acceptance Criteria:**

**Given** L1 is applied
**When** the Cognito resources are created
**Then** there is one user pool with `prevent_destroy`, a hosted-UI domain, an `oauth2-proxy` app client (authorization code flow, confidential, callback `https://app.<domain>/oauth2/callback`) and a `probe` app client with `ALLOW_USER_PASSWORD_AUTH`
**And** `/k8s-on-aws/persistent/cognito_issuer`, `oauth2_client_id` and `probe_client_id` are published
**And** the oauth2-proxy client secret is stored as `k8s-on-aws/oauth2-proxy/client-secret`

**Given** an `app_users` variable listing App Users and the Probe test user
**When** L1 is applied
**Then** each user exists as an `aws_cognito_user` with a verified email and a `random_password`-generated password
**And** each password is stored in Secrets Manager (`k8s-on-aws/probe/credentials` for the Probe, `k8s-on-aws/app-users/<username>` for App Users) and never in Git or Terraform outputs
**And** the runbook notes that these passwords also exist in the encrypted, private state bucket

**Given** an App User defined in L1
**When** any later Teardown and Rebuild happen
**Then** that user still exists with the same `sub`, because Teardown never touches L1 (FR-3)

### Story 1.6: Image registry and persistent secrets

As the Operator,
I want immutable image repositories with a size cap, and the remaining persistent secrets in place,
So that a Rebuild never rebuilds images and no Rebuild fails because of how a secret was named or deleted.

**Acceptance Criteria:**

**Given** L1 is applied
**When** the ECR resources are created
**Then** repositories `k8s-on-aws/app` and `k8s-on-aws/probe` exist with tag immutability, `prevent_destroy`, and a lifecycle policy keeping the 20 newest images (AD-26)
**And** `ci-image` can push to them and `ci-plan` cannot

**Given** L1 is applied
**When** the secrets are created
**Then** `k8s-on-aws/oauth2-proxy/cookie-secret` exists with a generated value never committed to Git
**And** every persistent secret follows `k8s-on-aws/<consumer>/<name>` (AD-17)
**And** no secret is defined in L2–L4, so the Secrets Manager recovery window can never block a Rebuild (FR-10)

**Given** an unchanged L1
**When** it is planned again
**Then** there are no changes, and ECR and Secrets Manager rows in `docs/cost-model.md` are filled in

## Epic 2: Run a Session: Rebuild the platform from nothing and tear it down with nothing billable left

The Operator triggers `rebuild` and gets the network, an EKS cluster, RDS (restored or fresh) and Argo CD; they trigger `teardown` and get a final snapshot, a fixed-order destroy and a passing post-Teardown check. Platform RTO is recorded for every Drill. Until Epic 3 adds controllers, the Teardown order is: state `tearing-down` → destroy L3 → destroy L2 (final snapshot) → retag survivors and prune → write Rebuild Log → post-Teardown check → state `none`.

### Story 2.1: Design the multi-AZ network

As the Operator,
I want a hand-designed VPC in L2 that I can explain route by route,
So that the cluster and database sit in private subnets and NAT stays cheap.

**Acceptance Criteria:**

**Given** `infra/ephemeral/core` with the VPC module (6.7.3) and the fck-nat module (1.6.1, `t4g.nano`)
**When** `pr-plan` runs while no Session is active
**Then** the plan shows a VPC across 2 AZs in us-east-1 with public and private subnets, fck-nat as the private subnets' default route, and S3 and DynamoDB gateway endpoints on the private route tables (FR-4)
**And** every resource is tagged `Layer=ephemeral` and `Session=<session_id>` (`session_id` is an input variable)
**And** `docs/adr/0001-network-design.md` records the CIDR plan, subnet layout, and the fck-nat versus managed NAT Gateway choice with its trade-off (~$3 vs ~$32/month, ~5 min failover)
**And** `docs/components.md` lists the L2 root

### Story 2.2: Rebuild and tear down through the Session state machine

As the Operator,
I want manually triggered `rebuild` and `teardown` workflows that enforce the Session state,
So that every Session starts and ends on purpose and never overlaps another.

**Acceptance Criteria:**

**Given** state `none`
**When** the Operator dispatches `rebuild`
**Then** it generates `session_id` (`s` + UTC `YYYYMMDD-HHMM`), rejects it if a snapshot or Rebuild Log entry for it exists, and writes state `building` and the id to SSM
**And** it applies L2 with `ci-apply` in the `ephemeral` environment, then sets state `active`, or `failed` on any error

**Given** state `building` or `tearing-down`
**When** `rebuild` is dispatched
**Then** it refuses to start (AD-5)

**Given** state `active` or `failed`
**When** the Operator dispatches `teardown`
**Then** it sets state `tearing-down`, destroys L2, and sets state `none`
**And** both workflows share concurrency group `ephemeral` with `cancel-in-progress: false`, and neither runs on a merge (FR-30)
**And** the Rebuild pre-flight fails while `faults/ACTIVE` exists on `main` (AD-14)

### Story 2.3: Post-Teardown check and session watchdog

As the Operator,
I want Teardown to prove nothing billable is left, and an alert when a Session is left running,
So that I never pay for something I forgot.

**Acceptance Criteria:**

**Given** `scripts/teardown-check/allowlist.yaml` lists the Persistent Footprint
**When** Teardown reaches its check
**Then** it runs a Tagging API query for `Layer=ephemeral` and sweeps EC2, EBS, ELBv2, EIP/public IPv4, RDS instances and ENIs against the allowlist
**And** it confirms each hit with the service's describe call, ignores resources pending deletion, and retries before failing

**Given** a leftover billable resource (e.g., a test EIP created by the Operator)
**When** the check runs
**Then** Teardown fails loudly naming the resource and leaves state `failed`, not `none` (FR-31)

**Given** state `active` for more than 4 hours
**When** the scheduled `session-watchdog` runs
**Then** it emails the Operator through SNS and never destroys anything (NFR-1)

### Story 2.4: EKS on standard support with Graviton Spot nodes

As the Operator,
I want each Rebuild to create a pinned EKS cluster on standard support with a small Spot node group,
So that the cluster is cheap and never drifts into extended-support pricing.

**Acceptance Criteria:**

**Given** the EKS version is one variable set to 1.36
**When** the Rebuild pre-flight runs
**Then** it fails unless `describe-cluster-versions` reports that version as `STANDARD_SUPPORT` (FR-7)

**Given** a Rebuild
**When** L2 applies
**Then** EKS `k8s-on-aws` (module 21.29.0) exists with a public + private endpoint and a managed Spot node group of `t4g.*` instances in private subnets, at least 2 nodes across 2 AZs
**And** the VPC CNI add-on (1.23.2) runs with `enableNetworkPolicy=true`, and the Pod Identity agent add-on is installed
**And** the Operator's IAM user and `ci-apply` get cluster access only through EKS access entries; no shared kubeconfig credential exists (FR-9)
**And** `docs/runbooks/capacity.md` explains node-group sizing against declared requests, and the conventions doc requires CPU and memory requests and limits on every container (FR-11)

### Story 2.5: Pod Identity from the workload identity registry

As the Operator,
I want every pod's AWS permissions generated from one registry,
So that Terraform associations and chart service accounts can never disagree.

**Acceptance Criteria:**

**Given** an entry in `infra/workload-identities.yaml`
**When** L2 applies
**Then** a role `k8s-on-aws-eph-<namespace>-<sa>` and its Pod Identity association are created with the declared policy (AD-21)

**Given** rendered manifests under `gitops/`
**When** CI runs
**Then** it fails if an AWS-calling ServiceAccount is missing from the registry, or a registry entry has no matching ServiceAccount
**And** `docs/adr/0002-pod-identity-vs-irsa.md` compares Pod Identity with IRSA and records the decision (FR-9, FR-29)

### Story 2.6: RDS restored from the latest snapshot, or fresh on first Rebuild

As the Operator,
I want every Rebuild to restore the database from the newest final snapshot and every Teardown to take a uniquely named one,
So that data survives Sessions and the first Rebuild doesn't fail.

**Acceptance Criteria:**

**Given** no `k8s-on-aws-final-*` snapshot exists
**When** Rebuild runs
**Then** it passes an empty `restore_snapshot_id` to L2, and a fresh PostgreSQL 17.11 `db.t4g.micro` is created in private subnets with IAM database authentication enabled (FR-16)

**Given** final snapshots exist
**When** Rebuild runs
**Then** the workflow (not Terraform) selects the newest and L2 restores from it
**And** Rebuild runs `modify-db-instance --manage-master-user-password` after restore, and the master secret ARN is published to SSM (AD-10)
**And** `snapshot_identifier` is under `ignore_changes`, and the final snapshot is named `k8s-on-aws-final-<session_id>`
**And** automated backups have 1-day retention, `delete_automated_backups = false`, `copy_tags_to_snapshot = false`
**And** RDS has no Terraform dependency on EKS, so they are created in parallel (AD-9)
**And** re-planning during an active Session never shows RDS replacement
**And** the `manage_master_user_password`-after-restore spike result is recorded in the RDS runbook

### Story 2.7: Snapshot retention and survivor tagging

As the Operator,
I want Teardown to keep only recent snapshots and tag survivors as Persistent,
So that snapshot cost stays bounded and the post-Teardown check passes.

**Acceptance Criteria:**

**Given** L2 has been destroyed with its final snapshot
**When** Teardown continues
**Then** it tags the new final snapshot and the newest retained automated backup `Layer=persistent`
**And** it deletes all but the 5 newest final snapshots and all but the newest retained backup (FR-16, AD-9)
**And** the post-Teardown check passes with those survivors present
**And** `docs/adr/0003-rds.md` records RDS versus in-cluster Postgres or DynamoDB and the snapshot design (FR-29)

### Story 2.8: Argo CD through the L3 GitOps bridge

As the Operator,
I want each Rebuild to install Argo CD and hand it per-Session values through cluster annotations,
So that everything in the cluster comes from Git with no hard-coded IDs.

**Acceptance Criteria:**

**Given** L2 is up
**When** Rebuild applies `infra/ephemeral/gitops`
**Then** Argo CD 3.5.6 (chart 10.11.6) is installed and the in-cluster cluster Secret carries the bridge annotations available so far: `cluster_name`, `region`, `account_id`, `vpc_id`, `session_id`, `phase=active`, `rds_endpoint`, `rds_master_secret_arn` (the rest of the AD-4 closed set arrives with later epics)
**And** the root app-of-apps syncs `gitops/root` from the public repo over anonymous HTTPS, with no repo credential and no `kubectl apply` (FR-13)
**And** Kubernetes and Helm providers appear only in this root (AD-2)

**Given** a PR adding an AWS account ID or `arn:` literal under `gitops/`
**When** CI runs
**Then** it fails (AD-4)

**Given** Teardown
**When** it runs
**Then** it destroys L3 before L2

### Story 2.9: Apply Ephemeral changes on merge only during a Session

As the Operator,
I want merged L2, L3 and `gitops/` changes applied only while a Session is active,
So that a merge never creates billable resources overnight or races a Teardown.

**Acceptance Criteria:**

**Given** state `active`
**When** a merge touches `infra/ephemeral/**`
**Then** `ephemeral-apply` applies the changed roots in concurrency group `ephemeral`

**Given** any other state
**When** the same merge lands
**Then** CI runs a full L2 plan, `validate` only for L3, and render + lint for `gitops/`, and creates nothing (FR-12, AD-5)
**And** `chore(bot): …` commits do not trigger `ephemeral-apply` (AD-25)

### Story 2.10: Rebuild Log with Platform RTO

As the Operator,
I want every Drill recorded by the pipeline with its Platform RTO,
So that I can show a measured recovery-time trend, not a stopwatch reading.

**Acceptance Criteria:**

**Given** a Rebuild
**When** nodes are Ready and RDS is `available`
**Then** Rebuild writes `started_at`, `platform_ready_at`, `platform_rto_s`, `restore_mode`, `snapshot_id` to `s3://<state-bucket>/evidence/<session_id>/rebuild.json` (AD-25)

**Given** the Operator dispatches `teardown` with optional inputs `manual_steps`, `failure_cause` and `notes`
**When** Teardown finishes, including after a failed Rebuild
**Then** it commits `docs/rebuild-log/<session_id>.json` with the AD-20 fields (including `rpo_s`, `manual_steps[]` and `failures[]` taken from those inputs and from the workflow's own errors) as a `chore(bot):` commit; Teardown stays the only writer (AD-25)
**And** `docs/rebuild-log.md` is regenerated from those files, never hand-edited, and shows the baseline median over the first 5 Drills
**And** a Drill with `platform_rto_s` > 2700 is marked failed; with no `failure_cause` it is written with "cause pending" and the rendered table flags it as open (FR-21)
**And** any manual step recorded in Drills 1–5 is listed as a defect (FR-20)

## Epic 3: App Users sign in and log workouts at `app.yahiahussein.dev`, and their data survives every Teardown

The full edge chain Route 53 → ALB (Gateway API) → oauth2-proxy + Cognito → App, with IAM database auth, ESO secrets, default-deny network policies and Git-driven deploys. oauth2-proxy (3.5) lands before the public hostname (3.6), so an unauthenticated request can never reach the App. Story 3.1 is the only story counted against the App's 8–10 hour cap.

### Story 3.1: The fitness App

As an App User,
I want to log a workout and list my own workouts through a small API,
So that there is real data for Drills to protect.

**Acceptance Criteria:**

**Given** a request with `X-Forwarded-User: <sub>`
**When** it sends `POST /api/workouts` with `{type, duration_min, performed_at}`
**Then** the App returns `201` with the created workout, a UUIDv7 `id`, and RFC 3339 UTC `performed_at` (AD-23)

**Given** two users with workouts
**When** either calls `GET /api/workouts`
**Then** the App returns `200` with `{items:[…]}` containing only that caller's workouts (FR-15)

**Given** a request with no `X-Forwarded-User`, or an invalid body
**When** it reaches the App
**Then** the App returns `401` or `400` with `{error:{code, message}}`
**And** `GET /healthz` returns `200`
**And** the App connects as role `app` with an IAM database authentication token and no password (FR-10)
**And** schema migrations live in `app/` and run as a separate `migrate` command
**And** logs are JSON lines with `ts`, `level`, `msg`, `session_id`
**And** tests run locally against a Postgres container, on Python 3.14, FastAPI 0.162.0, psycopg 3.3.6 and uv 0.13.6

### Story 3.2: arm64 image builds with deploys through Git

As the Operator,
I want each merge to `app/` or `probe/` to produce an immutable arm64 image and a separate bot commit that deploys it,
So that every running version is in Git and rollback is a revert.

**Acceptance Criteria:**

**Given** a merge touching `app/`
**When** `image-build` runs on `ubuntu-24.04-arm` with `ci-image`
**Then** it pushes `k8s-on-aws/app:sha-<git-sha>` built for `linux/arm64` only (AD-15, AD-16)
**And** it commits a `chore(bot):` tag bump under `gitops/workloads/app/` that triggers neither `pr-plan` nor `ephemeral-apply` (AD-25)

**Given** an attempt to push an existing tag again
**When** the push runs
**Then** ECR rejects it (tag immutability)
**And** `rebuild` never builds or pushes an image (FR-3)
**And** the same workflow already handles `probe/`, ready for Epic 4

### Story 3.3: External Secrets with namespace-scoped stores

As the Operator,
I want secrets delivered to pods only through namespace-scoped stores,
So that no namespace can read another's secrets and no secret ever sits in Git.

**Acceptance Criteria:**

**Given** External Secrets Operator 2.14.0 deployed by Argo CD in `external-secrets`
**When** a namespace needs a secret
**Then** it uses a `SecretStore` in that namespace, assuming a per-consumer role (in the workload identity registry) limited to `k8s-on-aws/<consumer>/*` (AD-17)

**Given** a manifest under `gitops/` using `ClusterSecretStore`
**When** CI runs
**Then** it fails
**And** only the `app` namespace's store can read the RDS master secret, whose ARN comes from the `rds_master_secret_arn` annotation
**And** `docs/components.md` lists ESO

### Story 3.4: Deploy the App with database hooks

As the Operator,
I want Argo CD to prepare the database role and schema before every App sync,
So that both a fresh and a restored database reach a working App with no manual steps.

**Acceptance Criteria:**

**Given** a Rebuild with a fresh or restored database
**When** Argo CD syncs the `app` Application
**Then** the `db-init` PreSync hook (wave -2) waits for the master secret to be `active`, then idempotently creates role `app` and grants `rds_iam` (AD-10)
**And** the `migrate` PreSync hook (wave -1) runs the App migrations as role `app`
**And** the App Deployment becomes Ready with at least 2 replicas spread across AZs by a topology spread constraint

**Given** `db-init` runs again against a database where the role exists
**When** it completes
**Then** it succeeds without error
**And** the `app` namespace enforces Pod Security `restricted`, and every container sets requests and limits (FR-11, AD-22)
**And** a workout posted through `kubectl port-forward` is stored in RDS

### Story 3.5: Single sign-on at the edge with oauth2-proxy

As an App User,
I want to sign in once through Cognito before any App code runs,
So that only authenticated users reach the App and the App never handles credentials.

**Acceptance Criteria:**

**Given** oauth2-proxy 7.15.5 (chart 10.7.1) in `app`, configured from the `cognito_issuer` and `oauth2_client_id` annotations, with client and cookie secrets delivered by ESO
**When** an unauthenticated request arrives
**Then** it is redirected to the Cognito hosted UI and the App receives nothing (FR-15)

**Given** a signed-in user
**When** they call the API
**Then** oauth2-proxy forwards the request with `X-Forwarded-User` set to their Cognito `sub` (AD-11)
**And** the bridge annotations grow by `cognito_issuer`, `oauth2_client_id`, `domain`, `app_hostname`, staying within the AD-4 closed set
**And** the remaining oauth2-proxy flags (cookie, session, upstream) are recorded in the edge runbook
**And** oauth2-proxy runs at least 2 replicas spread across AZs by a topology spread constraint
**And** the Probe's bearer-token flags are deferred to Story 4.1

### Story 3.6: Public HTTPS edge at `app.yahiahussein.dev`

As an App User,
I want a stable HTTPS address after every Rebuild,
So that I can always find the App without anyone editing DNS.

**Acceptance Criteria:**

**Given** a Rebuild
**When** L2 applies
**Then** an ACM certificate for `app.<domain>` is issued with L2-owned DNS validation records, L2 waits for `ISSUED`, and the ARN is passed as the `cert_arn` annotation (AD-11, AD-19)

**Given** Argo CD syncs LBC 3.6.2 with Gateway API CRDs 1.6.3, Gateway `public` in `gateway` with an HTTPRoute to oauth2-proxy, and ExternalDNS 0.24.0 with the AD-19 flags (each with a registry Pod Identity entry)
**When** the sync completes
**Then** an internet-facing ALB terminates TLS with that certificate and serves `https://app.yahiahussein.dev` with no manual DNS edits (FR-2, FR-14)
**And** the LBC tags what it creates with `Project`, `Layer=ephemeral`, `Session`, `ManagedBy=lbc` via `--default-tags`, and ExternalDNS records carry its owner TXT records (AD-6)
**And** `/healthz` is not publicly reachable
**And** the ExternalDNS-alias-for-Gateway spike result is recorded; if it fails, a course correction is raised before this story closes
**And** `docs/adr/0004-ingress.md` records the LBC Gateway API choice and alternatives (FR-14, FR-29)

### Story 3.7: Teardown drains the edge before destroying the cluster

As the Operator,
I want Teardown to remove the ALB and DNS records through Git-shaped state before any destroy,
So that the VPC destroy never hangs and no load balancer keeps billing.

**Acceptance Criteria:**

**Given** an active Session with the edge up
**When** `teardown` runs
**Then** it re-applies L3 with `phase=draining`, and the ApplicationSets selecting `phase=active` (workloads and Gateway) are cascade-deleted while controllers still run (AD-7)
**And** the workflow polls until the ALB and `app.<domain>` records are gone, failing clearly on timeout
**And** only then does it destroy L3 and L2
**And** it never mutates the cluster with `kubectl` or `argocd`
**And** the post-Teardown check passes with no ELBv2, EIP or ENI left (FR-31)

### Story 3.8: Default-deny network policies

As the Operator,
I want every first-party namespace to deny traffic by default, allowing only the flows the architecture names,
So that a stray pod cannot reach the App or the database.

**Acceptance Criteria:**

**Given** default-deny ingress and egress in every first-party namespace
**When** the AD-22 allows are applied
**Then** only DNS, control plane → webhooks, ALB → oauth2-proxy, oauth2-proxy → App, App/`db-init`/`migrate` → RDS:5432, and workloads → AWS APIs and the public hostname (where needed) work

**Given** a test pod in `app` with no allow rule
**When** it tries to reach the App pods or the RDS endpoint
**Then** both connections fail (FR-5)
**And** the full sign-in and API path still works afterwards

**Given** any first-party namespace under `gitops/`, including ones added by later stories
**When** CI runs
**Then** it fails unless the namespace has a default-deny ingress and egress policy and its allows are documented in `docs/runbooks/network-policy.md`

### Story 3.9: Prove the App User journey across a Teardown, and rollback by revert

As an App User,
I want my workouts to still be there after the platform is torn down and rebuilt,
So that the Operator can show RPO = 0 with real data.

**Acceptance Criteria:**

**Given** an App User signs in at `https://app.yahiahussein.dev` and logs a workout
**When** the Operator runs Teardown and then Rebuild
**Then** the same user signs in again (same `sub`) and sees the workout (FR-3, FR-16)
**And** the Rebuild Log entry records `rpo_s = 0`

**Given** a deploy commit bumping the App to a new tag
**When** it is reverted on `main` during a Session
**Then** the previous App version runs within one Argo CD sync cycle, and the elapsed time is recorded (FR-13)
**And** `docs/components.md` lists every Argo CD application added in this epic

## Epic 4: The Operator sees users' pain before they complain: SLOs, Error Budgets and Service RTO

The Synthetic Probe becomes the single SLI source; metrics flow to L1 AMP and logs to CloudWatch; three per-Session SLOs drive burn-rate alerts and a Git-provisioned dashboard; Rebuild completion switches to Service RTO; and the Error Budget drives at least one recorded ship-or-revert decision. ALB CloudWatch metrics are collected for diagnosis only and never feed an SLI.

### Story 4.1: The Synthetic Probe

As the Operator,
I want an in-cluster client that signs in and uses both App features every 10 seconds,
So that the SLIs measure what a real user experiences, including sign-in.

**Acceptance Criteria:**

**Given** the Probe deployed in `probe` (Pod Security `restricted`, credentials from ESO `k8s-on-aws/probe/credentials`, client id from the `probe_client_id` annotation)
**When** a cycle runs
**Then** it signs in fresh with Cognito `InitiateAuth`, then calls `POST` and `GET /api/workouts` on `https://app.yahiahussein.dev` with the ID token as Bearer (AD-12)
**And** oauth2-proxy accepts the token through `--skip-jwt-bearer-tokens` and `--extra-jwt-issuers=<issuer>=<probe_client_id>`
**And** the Probe exposes exactly `probe_signin_total{result}`, `probe_requests_total{feature="log|list",result}`, and `probe_request_duration_seconds{feature}` with a `0.5` bucket
**And** at a 10 s interval a 2-hour Session yields at least 500 cycles, enough for an Error Budget of at least 5 failed requests (FR-32)

**Given** sign-in is broken (e.g., wrong Probe client config)
**When** the Probe runs
**Then** `probe_signin_total{result="failure"}` rises even though App code never runs
**And** the Probe image is built by the Story 3.2 `image-build` workflow
**And** the bridge annotations grow by `probe_client_id`, within the AD-4 closed set
**And** the `probe` namespace has default-deny with documented allows for DNS, Cognito and the public hostname only, passing the Story 3.8 CI check

### Story 4.2: Metrics from the edge, App and cluster into AMP

As the Operator,
I want metrics stored in a workspace that survives Teardown,
So that SLO history spans Sessions and I can diagnose problems at every hop.

**Acceptance Criteria:**

**Given** L1 is applied
**When** the AMP workspace is created
**Then** it has 365-day retention and `prevent_destroy`, its remote-write and query URLs are published to SSM and then as the `amp_remote_write_url` and `amp_query_url` annotations, and its cost is in `docs/cost-model.md` (FR-19)

**Given** Alloy 1.21.2 in `observability` through the k8s-monitoring chart 4.5.5
**When** it scrapes
**Then** it remote-writes Probe, App and cluster metrics to AMP with SigV4 through Pod Identity
**And** every series carries the `session_id` external label
**And** it uses a 60 s scrape interval and a metric allowlist keeping projected ingest at or below 40M samples/month, with the projection written down (AD-13)

**Given** the Session's ALB exists
**When** Alloy's CloudWatch exporter runs (Pod Identity with only `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics` and `tag:GetResources`)
**Then** a small allowlist of ALB metrics (request count, ELB and target 5XX counts, target response time, healthy host count), filtered by the Session tag, is in AMP with the `session_id` label
**And** these ALB metrics are documented as diagnostic only and are never used in an SLI, SLO, burn-rate alert or the Service ready point (AD-12)
**And** the CloudWatch API cost of the exporter is in `docs/cost-model.md`
**And** no in-cluster Prometheus is deployed, and a past Session's series remain queryable in AMP after Teardown
**And** the `observability` namespace has default-deny with documented allows for DNS, scrape targets, the Kubernetes API and the AMP and CloudWatch endpoints, passing the Story 3.8 CI check

### Story 4.3: Logs into CloudWatch

As the Operator,
I want App and cluster logs kept outside the cluster,
So that I can investigate an Incident after the Session has ended.

**Acceptance Criteria:**

**Given** an L1 CloudWatch log group with 14-day retention, published through the `log_group` annotation
**When** Alloy ships logs over OTLP/HTTP with SigV4 through Pod Identity
**Then** App and Probe JSON log lines are queryable in CloudWatch Logs Insights by `session_id` (FR-17)
**And** the OTLP-to-CloudWatch spike result is recorded; if it fails, this story switches to the CloudWatch Observability add-on as AD-13 states, and the decision is written down

### Story 4.4: SLOs, burn-rate alerts and failure alerts

As the Operator,
I want alerts when the Error Budget is burning or a node or pod fails, and never when no Session exists,
So that I learn about user pain before anyone complains.

**Acceptance Criteria:**

**Given** AMP recording and alert rules managed in L1 Terraform
**When** they are applied
**Then** they define the three per-Session SLOs from the AD-12 metrics only: sign-in ≥ 99%, availability ≥ 99%, latency ≥ 95% of requests < 500 ms
**And** they compute remaining Error Budget and burn rate per `session_id` (FR-18)
**And** they alert on node NotReady and on pods crash-looping or unschedulable (FR-17)
**And** window maths and burn-rate thresholds are recorded in `docs/runbooks/slo.md`

**Given** alerts routed through an L1 SNS topic to email
**When** no Session series exist
**Then** no rule fires, and there is no unguarded `absent()` or `up == 0` (AD-13)

**Given** a forced sign-in failure during a Session
**When** the burn rate crosses its threshold
**Then** the Operator receives the alert email

### Story 4.5: Grafana dashboards from Git

As the Operator,
I want a dashboard of current SLIs, remaining Error Budget and burn rate across Sessions,
So that I can make ship-or-revert calls and show SLO trends spanning Sessions.

**Acceptance Criteria:**

**Given** Grafana 13.3.0 in `observability` with the AMP datasource (SigV4 through Pod Identity)
**When** the Operator opens it through `kubectl port-forward`
**Then** a Git-provisioned dashboard shows, per SLO, the current SLI, remaining Error Budget and burn rate for the current `session_id` (FR-18)
**And** a cross-Session panel shows SLO results for past Sessions (FR-19)
**And** a separate diagnostic panel shows the ALB metrics, labelled as not part of any SLI
**And** Grafana has no public route, and its dashboards exist only as JSON in `gitops/`
**And** the `observability` allows are extended for Grafana's egress to the AMP query endpoint only

### Story 4.6: Service RTO and the per-Session SLO summary

As the Operator,
I want "Rebuild complete" to mean the first authenticated probe succeeded, and every Drill to record its SLO results,
So that the recovery time I report is when real users could be served.

**Acceptance Criteria:**

**Given** a Rebuild
**When** the first `probe_requests_total{result="success"}` sample for the `session_id` appears in AMP
**Then** Rebuild records `service_ready_at` and `service_rto_s` in the evidence file and only then sets state `active` (AD-20)

**Given** Teardown
**When** it writes the Rebuild Log record
**Then** it fills `slo_summary{signin,availability,latency,budget_remaining}` by querying AMP for that `session_id`
**And** `docs/rebuild-log.md` shows Platform RTO and Service RTO as separate series, marks any Drill with `service_rto_s` > 2700 as failed, and reports the median of the last 5 Drills against the baseline median (FR-21)
**And** from the end of M2, the rendered table flags any Drill with a non-empty `manual_steps[]` as a violation (FR-20)
**And** any Drill whose RTO beats the previous Drill's must carry its cause in `notes`, and the rendered table flags an improvement with no cause
**And** the rendered table states whether the end-of-M2 target is met: median RTO of the last 5 Drills lower than the baseline median (FR-21)

### Story 4.7: Error Budget policy and the first ship-or-revert decision

As the Operator,
I want a written Error Budget policy and at least one real decision made under it,
So that the Error Budget actually drives what I do.

**Acceptance Criteria:**

**Given** `docs/runbooks/error-budget-policy.md`
**When** it is read
**Then** it states that a change exhausting the budget is reverted, not patched forward, and who decides, when, and from which dashboard panel (FR-18)

**Given** a real change during a Session
**When** the Operator decides to ship or revert it
**Then** a decision record in `docs/decisions/` cites the remaining Error Budget and burn rate at that moment and links the commit

## Epic 5: Harden, upgrade and explain the platform so a reviewer gets it in 5 minutes

CIS scanning and Pod Security everywhere; a live EKS minor upgrade (1.35 → 1.36) and node rotation with measured SLI impact; the packet-path and troubleshooting write-ups; the ADR index including what was deliberately left out; and the scannable README. Per the de-scope order, FR-33 may drop to one case and FR-8 (Stories 5.2, 5.3) may move to M3.

### Story 5.1: CIS benchmark scan and Pod Security everywhere

As the Operator,
I want a repeatable CIS scan of the cluster and Pod Security enforced on every namespace,
So that I can show how the cluster is hardened, with the exceptions I accept and why.

**Acceptance Criteria:**

**Given** an arm64 kube-bench Job in `gitops/platform/`, running in `security` (`privileged`)
**When** the Operator runs it during a Session
**Then** results are saved to `s3://<state-bucket>/evidence/<session_id>/kube-bench.json`
**And** `docs/writeups/cis-benchmark.md` summarizes failures, lists fixes, and records every accepted exception with its reason (FR-23)

**Given** any namespace under `gitops/`
**When** CI runs
**Then** it fails unless the namespace has a Pod Security enforce label: `restricted` for `app` and `probe`, `privileged` only for `observability` and `security`, `baseline` for all others (AD-22)
**And** the `security` namespace has default-deny with documented allows for DNS, the Kubernetes API and S3 (evidence upload) only, passing the Story 3.8 CI check

### Story 5.2: EKS minor version upgrade during a live Session

As the Operator,
I want to upgrade the cluster by one minor version while the Probe is running,
So that I can explain an upgrade from real evidence: plan, steps and user impact.

**Acceptance Criteria:**

**Given** a Session rebuilt on EKS 1.35, with the pre-flight confirming 1.35 is in `STANDARD_SUPPORT` (if it is not, this story falls back to 1.36 → 1.37 once 1.37 is in standard support)
**When** the Operator merges a PR setting the EKS version variable to 1.36 and `ephemeral-apply` runs
**Then** the control plane, add-ons and node group reach 1.36, and the pre-flight accepts 1.36 (FR-7)
**And** `docs/writeups/eks-upgrade.md` records the plan (deprecated-API and add-on compatibility checks), steps, timings, and SLI impact observed on the dashboard (FR-8)
**And** the variable stays at the pinned 1.36, so the next Rebuild creates 1.36 directly with no manual steps

### Story 5.3: Node rotation with no user-facing breach

As the Operator,
I want to replace every node during a Session,
So that I can show workloads survive losing the nodes under them.

**Acceptance Criteria:**

**Given** an active Session with PodDisruptionBudgets on oauth2-proxy and the App
**When** the Operator rotates the node group through a merged change (e.g., a new AMI release version)
**Then** every original node is replaced and pods are rescheduled within PDB limits
**And** `docs/writeups/node-rotation.md` records plan, steps, timings and SLI impact (FR-8)

### Story 5.4: Packet-path write-up

As a Reviewer,
I want to follow one request from the internet to the App pod,
So that I can see the Operator understands every hop.

**Acceptance Criteria:**

**Given** a live Session
**When** the Operator traces one request
**Then** `docs/writeups/packet-path.md` shows each hop with real commands and outputs: DNS resolution of `app.yahiahussein.dev`, the ALB listener, certificate and target group, the Gateway and HTTPRoute, oauth2-proxy, the App pod, and the App's connection to RDS
**And** it explains which security group, network policy and route table allow each hop (FR-6)

### Story 5.5: Two troubleshooting write-ups

As a Reviewer,
I want real troubleshooting cases from the live Platform,
So that I can judge how the Operator debugs, not only how they build.

**Acceptance Criteria:**

**Given** at least two real problems recorded in `docs/writeups/_journal.md` during Epics 2–5
**When** the Operator writes them up
**Then** each `docs/writeups/troubleshooting-<slug>.md` covers the symptom, commands used with output, findings and fix, and links the fixing commit (FR-33)
**And** one case is acceptable if the schedule slips, per the de-scope order

### Story 5.6: ADR index, with what was deliberately left out

As a Reviewer,
I want one index of every decision, including what was left out on purpose,
So that I can see the trade-offs at a glance.

**Acceptance Criteria:**

**Given** `docs/adr/README.md`
**When** it is read
**Then** it lists every ADR with status and a one-line summary, including at least network design, Pod Identity versus IRSA, RDS and ingress (FR-29)
**And** ADRs exist for the deliberately excluded options (full service mesh, multi-environment promotion, Karpenter, EKS Auto Mode and Fargate, multiple accounts and AWS Organizations), each recording why it was left out and what would trigger revisiting it
**And** every component in `docs/components.md` points to an existing ADR, runbook or write-up (NFR-6 met before M3)

### Story 5.7: Scannable README

As a Reviewer,
I want the README to put the evidence of operations within one screen,
So that I can judge the project in 2–5 minutes.

**Acceptance Criteria:**

**Given** `README.md`, built from the architecture README's diagram, Session walkthrough and decision table
**When** it is opened on GitHub
**Then** links to the architecture diagram, ADR index, Rebuild Log (with RTO trend), Postmortems, packet-path write-up and troubleshooting write-ups all appear above the first scroll
**And** a CI link check fails if any of those targets is missing (FR-28)
**And** the Postmortems link points to `docs/postmortems/`, which Epic 6 fills

## Epic 6: Lead three real Incidents end to end and prove each fix holds

Faults arrive through Git and are recovered by `git revert` (node failure and RDS loss by scripts in the repo). Exactly three Incidents are run, each with a commander, timeline, status comms, a blameless Postmortem, a merged Action Item and a re-test. Admission policies appear only as Action Items. Includes the unplanned data-loss exercise. This epic is never cut.

### Story 6.1: Fault injection and Incident tooling

As the Operator,
I want every fault type injectable the same way each time, with templates for running and reviewing an Incident,
So that each Incident is realistic, repeatable and re-testable.

**Acceptance Criteria:**

**Given** `faults/<incident>/` holding a patch and a README describing the fault and the signal it should trip
**When** the Operator runs `scripts/faults/inject.sh <incident>`
**Then** it opens a `fault(<incident>): …` PR that applies the patch and creates `faults/ACTIVE` (FR-25, AD-14)
**And** merging it during a Session makes the fault live through the normal pipeline, and `git revert` of that merge removes both the fault and `faults/ACTIVE`

**Given** `scripts/faults/node-terminate.sh`
**When** it runs during a Session
**Then** it terminates exactly one node selected by `Session=<session_id>`, after confirmation, and logs what it terminated

**Given** the four fault types (bad deploy, auth outage, node failure, network fault)
**When** this story closes
**Then** each has a ready fault asset (`faults/bad-deploy/`, `faults/auth-outage/`, `faults/network/`, and `node-terminate.sh`), and each has been dry-run once in a Session with the effect observed and the recovery confirmed (FR-25)
**And** the Rebuild pre-flight still refuses to start while `faults/ACTIVE` is on `main` (Story 2.2)
**And** `docs/runbooks/incident.md` (declaring, commander role, timeline keeping, status comms cadence) and `docs/postmortems/TEMPLATE.md` (blameless: timeline, cause, caught, missed, Action Items, re-test) exist

### Story 6.2: Incident 1, a bad deploy

As the Operator,
I want to lead a real Incident caused by a bad deploy,
So that I can tell the whole story from alert to a proven fix.

**Acceptance Criteria:**

**Given** a fault patch deploying a broken App version (e.g., `POST /api/workouts` returns 5XX)
**When** it is merged during a Session
**Then** the availability SLI drops and a burn-rate alert fires, or the Postmortem explains why it did not
**And** the Operator declares the Incident, acts as commander, and keeps a timestamped timeline and status communications written as they would be sent (FR-26)
**And** service is restored by `git revert`
**And** `docs/postmortems/<date>-bad-deploy.md` is blameless and records what monitoring caught and missed; a claim that nothing was missed must be justified (SM-C3)
**And** at least one Action Item merges as a `fix(pm-1): …` PR linking the Postmortem
**And** the same patch is re-injected after the Action Item ships, and the re-test result is recorded in the Postmortem (FR-27)

### Story 6.3: Kyverno admission policies as Postmortem Action Items

As the Operator,
I want admission policies added only because an Incident proved they were needed,
So that each policy traces to a real failure.

**Acceptance Criteria:**

**Given** a Postmortem whose Action Item calls for an admission control (e.g., reject non-`sha-` image tags, or pods without probes)
**When** the Action Item PR merges
**Then** Kyverno 1.19.2 (chart 3.9.2) is deployed by Argo CD in `kyverno` if not already present, together with the policy (FR-24)
**And** each policy carries an annotation linking its motivating Postmortem, and CI fails for any policy without one
**And** `docs/components.md` lists Kyverno pointing to that Postmortem
**And** the `kyverno` namespace has default-deny with documented allows for DNS, the Kubernetes API and control plane → webhook traffic, passing the Story 3.8 CI check

**Given** none of the three Postmortems produces an admission-control Action Item
**When** Epic 6 closes
**Then** this story closes with no policy introduced, and the Epic 6 summary records why; no Incident is staged to manufacture one (SM-C2)

### Story 6.4: Incident 2, an auth outage

As the Operator,
I want to lead an Incident where sign-in breaks while the App itself is healthy,
So that I can show edge monitoring catches what App metrics never see.

**Acceptance Criteria:**

**Given** a fault patch changing only L4 oauth2-proxy config (issuer, JWKS or client), never L1 Cognito (AD-14)
**When** it is merged during a Session
**Then** `probe_signin_total{result="failure"}` rises and the sign-in SLI drops while App code never runs (FR-32)
**And** the Incident is run end to end as in Story 6.2 (FR-26)
**And** the Postmortem names the hosted-UI redirect gap as a monitoring miss, or explains why it did not matter here (AD-12)
**And** at least one Action Item merges as `fix(pm-2): …`, and the re-test with the same patch is recorded (FR-27)

### Story 6.5: Incident 3, a node or network failure

As the Operator,
I want to lead an Incident where infrastructure fails beneath healthy code,
So that I can show what the platform tolerates and where it breaks.

**Acceptance Criteria:**

**Given** either `scripts/faults/node-terminate.sh` or a network fault patch (e.g., a NetworkPolicy change breaking oauth2-proxy → App)
**When** the fault is injected during a Session
**Then** the SLI impact and the node/pod alerts are captured, and recovery is by `git revert` (network) or node-group replacement (node)
**And** the Incident is run end to end as in Story 6.2 (FR-26)
**And** the Postmortem records what was caught and missed, at least one Action Item merges as `fix(pm-3): …`, and the re-test result is recorded (FR-27)

### Story 6.6: Unplanned data-loss exercise

As the Operator,
I want to recover the database once without a fresh final snapshot,
So that I can report an honest RPO for an unplanned failure.

**Acceptance Criteria:**

**Given** an active Session with workouts logged before and after the latest automated backup
**When** the Operator runs `scripts/faults/rds-loss.sh` (deletes the RDS instance with no final snapshot, keeping automated backups) and then Teardown
**Then** the script writes the deletion timestamp to `s3://<state-bucket>/evidence/<session_id>/rds-loss.json` before deleting
**And** Teardown completes despite the missing instance and final snapshot, records the failure, and the post-Teardown check passes

**Given** the next Rebuild dispatched with `restore_mode=pitr`
**When** it restores from the retained automated backup
**Then** the App serves the workouts from before the backup, and those logged after it are gone
**And** the `pitr` Rebuild computes `rpo_s` as the deletion timestamp from `rds-loss.json` minus the restore point it used, and the Rebuild Log records `restore_mode=pitr` and that `rpo_s` (FR-22)
**And** `docs/writeups/unplanned-data-loss.md` explains what happened, the measured RPO, and what would shorten it
