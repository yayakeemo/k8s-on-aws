---
title: 'Review: reconcile spine against PRD + addendum'
reviewed: architecture/architecture-Kubernetes-on-AWS-2026-10-28/ARCHITECTURE-SPINE.md
inputs:
  - prds/prd-Kubernetes-on-AWS-2026-10-27/prd.md
  - prds/prd-Kubernetes-on-AWS-2026-10-27/addendum.md
date: 2026-10-28
---

# Reconcile Review: Spine vs PRD Inputs

**Verdict:** The spine is solid. It covers every decision the addendum handed to architecture: SLO store = AMP, fault tool = Git patches plus a script, Gateway = LBC Gateway API, certificates issued in L2, and the Route 53 zone adopted. It also covers every addendum pitfall except Probe sizing. Five gaps still let epics diverge or break a PRD acceptance criterion:

- the post-Teardown check will fail on the Persistent snapshots it is meant to keep
- FR-5's RDS isolation is not enforced
- Bootstrap needs more manual steps than FR-1 allows
- the sign-in SLI can't be measured with the Probe cadence left open
- ephemeral plans can't run outside a Session

Severity scale: **critical** means a PRD requirement is violated by construction. **high** means two epics will diverge or a PRD acceptance criterion fails. **medium** means a likely defect or a gap in a quiet requirement. **low** means wording or a verification item.

---

## Coverage check: handed-off decisions, assumptions and pitfalls

| Input item | Source | Spine | Status |
| --- | --- | --- | --- |
| SLO history store | PRD FR-19, §10 Q2; addendum | AD-13 (AMP, 365 days) | Covered |
| Fault-injection tool | PRD FR-25, §10 Q3; addendum | AD-14 (Git patches + node script; Chaos Mesh deferred) | Covered |
| Gateway API implementation | PRD FR-14; addendum | AD-11 (LBC Gateway API) | Covered |
| Where TLS certificates live [ASSUMPTION] | PRD FR-2, §11 | AD-11 (ACM issued per Rebuild in L2) | Covered |
| Registrar / Route 53 [ASSUMPTION] | PRD §10 Q1, §11 | AD-19 (adopt the registration zone) | Covered. The domain name is still open (Deferred) |
| Unique final snapshot identifier | addendum: RDS mechanics | AD-9 | Covered |
| Restore lookup tolerates no snapshot | addendum | AD-9 (the workflow does the lookup) | Covered |
| Retain 5 snapshots | PRD FR-16; addendum | AD-7, AD-9 | Covered |
| `delete_automated_backups = false` | PRD FR-22; addendum | AD-9 | Covered. Cost side-effect not covered (F-9) |
| Controller-created resources | addendum pitfalls; FR-31 | AD-6, AD-7, AD-8 | Covered. Sweep gaps (F-7) |
| Secrets Manager recovery window | addendum; FR-10 | AD-17 | Covered |
| Route 53 registration zone | addendum | AD-19 | Covered. The import mechanism is a manual-step risk (F-3) |
| Bootstrap credentials via Identity Center | addendum; NFR-2 | AD-18 | Covered, but conflicts with "AWS Organizations out of scope" (F-3) |
| **Synthetic Probe sizing (≥500 requests/Session, dedicated user)** | addendum; FR-32 | AD-12 names the user; **cadence is not fixed** | **Gap (F-4)** |
| Cost ceiling, billing alarm | NFR-1 | Alarm placed in L0; **threshold, mechanism and overnight detection missing** | **Gap (F-8)** |
| Explainability | NFR-6 | **no rule** | **Gap (F-11)** |
| SM-C1: don't grow the Persistent Footprint to cut RTO | PRD §8 | AD-1 has no closed list | **Gap (F-10)** |
| RTO budget ≤ 45 min | FR-21, NFR-5 | Measurement in AD-20; **no critical-path decisions** | **Gap (F-6)** |
| Bootstrap manual-step limit | FR-1 | AD-18 | **Contradicted in effect (F-3)** |

---

## Findings

### F-1: Post-Teardown check conflicts with the Persistent artifacts that ephemeral RDS produces (high)
- **Source:** PRD FR-31, FR-16, FR-22, §3 (Persistent Footprint includes "RDS snapshots"). Spine AD-6(a), AD-9.
- **Problem 1: tags.** The final snapshot `k8s-on-aws-final-<session_id>` is created by destroying an L2 instance. With `copy_tags_to_snapshot` (the terraform-aws-modules default is often true), the snapshot inherits `Layer=ephemeral` and `Session=…`. Retained automated backups behave the same way. Check (a), "Tagging API for `Layer=ephemeral` returns nothing", then fails on every Teardown. The likely result is that someone weakens the check.
  - The Tagging API can also return recently deleted resources for a short time, which adds false positives.
- **Problem 2: encryption keys.** Nothing says which KMS key encrypts RDS storage. If an L2 epic creates a customer-managed key, the snapshots become unrestorable once that key is deleted. The same applies to the EKS module's default `create_kms_key`, which also adds a per-Rebuild key, alias and cost.
- **Fix:** add a rule to AD-9 and AD-6:
  - RDS storage uses the `aws/rds` managed key, or a CMK created in L1.
  - Set `copy_tags_to_snapshot = false`, and have the workflow tag final snapshots `Layer=persistent`. Alternatively, exclude `rds:snapshot` and `rds:auto-backup` from query (a) and list them in `allowlist.yaml` by name pattern.
  - Check (a) retries or tolerates stale entries for a bounded window.

### F-2: FR-5 "cannot reach the RDS endpoint" is not enforced (high)
- **Source:** PRD FR-5 ("A pod without an explicit allow rule cannot reach the App pods **or the RDS endpoint**"). Spine Conventions › Network policy says "default-deny **ingress**".
- **Problem:** RDS is outside the cluster, so ingress policies never restrict traffic to it. The RDS security group will allow the node (or cluster) security group, which means every pod on every node can reach it.
- **Fix:** extend the convention to default-deny ingress **and egress** in `app`, `probe` and the other first-party namespaces. Allow egress explicitly:
  - DNS for all
  - RDS (private subnet CIDRs, port 5432) only for App, migrate and db-init
  - HTTPS egress for the Probe, oauth2-proxy and the controllers

  Alternatively, mandate Security Groups for Pods. Either way, put the decision in the spine so the Network epic and the App epic agree.

### F-3: Bootstrap needs more manual steps than FR-1 allows, and contradicts §7 (high)
- **Source:** PRD FR-1 ("The only manual steps allowed are domain registration and its contact-email verification"), §7 (AWS Organizations deferred), NFR-1 (billing alarm). Spine AD-18, AD-13, AD-19, AD-2.
- **Problem:** these steps are manual and not allowed by FR-1:
  - **Identity Center for account access.** `aws sso login` with permission sets needs an **organization instance** of IAM Identity Center, which means enabling AWS Organizations. The spine lists Organizations as out of scope, and enabling Identity Center and creating the admin user from an empty account are manual console steps.
  - **CloudWatch billing alarm.** It needs the account-level "Receive Billing Alerts" preference, which is set by hand.
  - **SNS email subscriptions** (AMP alerts and the billing alarm) need a confirmation click.
  - **Hosted-zone import.** Adopting the zone with an `import` block needs the zone ID typed in, unless it is looked up.
  - **State bucket.** L0 stores its own state in the bucket it creates, which forces a local-state-then-migrate step.
  - **GitHub setup.** The repo environments `persistent`/`ephemeral` and the branch rules that AD-18's OIDC subjects depend on are created by hand.
- **Fix:** add one Bootstrap AD that:
  - lists the allowed prerequisite steps
  - records an explicit [ASSUMPTION] or PRD amendment: "account prerequisites (Organizations + Identity Center enablement) are pre-Bootstrap and not counted", or uses another short-lived credential path
  - uses AWS Budgets (`aws_budgets_budget`, emails directly, supports forecasts) instead of a CloudWatch billing alarm
  - manages GitHub environments with the `integrations/github` provider in L0
  - documents the L0 state-migration step
  - looks up the zone ID by domain name

### F-4: Probe cadence is left open, so the sign-in SLI and the FR-32 budget can't be met consistently (high)
- **Source:** PRD FR-32 (≥5 failed requests of budget per Session), FR-18 (sign-in ≥ 99%). Addendum › Probe sizing (≥500 requests per Session, one every 10–15 s).
- **Problem:** AD-12 fixes the metric names but not the cadence or how often the Probe signs in. If the Probe reuses its ID token for its 1-hour life, a 2-hour Session has about 2 sign-in attempts. The sign-in SLO then has no budget at all (99% of 2), and the UJ-2 auth outage may not show up until the token expires.
  - The cadence also drives AD-13's 40M-sample budget, so the Probe and Observability epics will choose different values.
- **Fix:** add to AD-12:
  - Each Probe cycle = a fresh `InitiateAuth` + log + list, every 10 s, which gives about 720 sign-ins and 1,440 requests per 2 hours.
  - The SLO evaluation needs at least 500 events. If a Session is too short to reach that, it is marked "insufficient data" instead of passing or failing.

### F-5: Ephemeral roots can't be planned outside a Session (high)
- **Source:** PRD FR-12 ("Outside a Session, a merge runs a plan only"). Spine AD-2, AD-3, AD-5.
- **Problem:** outside a Session:
  - `infra/ephemeral/gitops` configures its Kubernetes and Helm providers from a cluster that doesn't exist.
  - The `/k8s-on-aws/core/*` SSM parameters that the gitops root reads are destroyed with L2.
  - `pr-plan` for L3 fails the same way.

  The Pipeline and GitOps epics will each improvise a workaround.
- **Fix:** state in AD-5 that when `session/active = none`:
  - L2 plans against empty state, which shows a full create
  - L3 runs only `terraform validate` (or a plan with providers stubbed)
  - L4 runs only a manifest lint or render (`helm template`/kubeconform)
  - `pr-plan` follows the same matrix

### F-6: Nothing in the spine protects the RTO critical path (medium)
- **Source:** PRD FR-21, NFR-5 (≤45 min; stretch 30). Addendum (restore adds 10–20 min to a 30–45 min Rebuild).
- **Problem:** the Service-ready path runs in this order: ACM DNS validation, then ALB provisioning, then the ExternalDNS record, then the Probe resolving `app.<domain>`.
  - If the Probe or CoreDNS resolves the name before the record exists, Route 53's SOA negative-caching TTL (900 s by default) can add up to 15 minutes.
  - AD-20's "first sample in AMP" point adds up to one scrape interval (60 s) plus remote-write lag.
  - Nothing says EKS and RDS are created in parallel. They are in the same root, which is good, but an epic could split them.
- **Fix:**
  - Lower the hosted-zone SOA negative TTL in L1 (for example to 60 s), or have the Probe wait for authoritative resolution before its first request.
  - Record the scrape lag as a known measurement offset.
  - Add an invariant that RDS restore and EKS creation stay parallel inside `ephemeral/core`.

### F-7: The type sweep misses resource types FR-31 names or implies (medium)
- **Source:** PRD FR-31 ("including … DNS records"). Spine AD-6(b).
- **Problem:** Route 53 records can't be tagged, so neither check (a) nor check (b) catches a leftover `app.<domain>` record. The sweep also leaves out:
  - EKS clusters
  - VPCs
  - the KMS keys/aliases and CloudWatch log groups that EKS creates (`/aws/eks/<name>/cluster` is recreated by EKS after Terraform deletes it, which also causes an "already exists" collision on the next Rebuild)
  - retained RDS automated backups
- **Fix:**
  - Add to (b): EKS, VPC, the Route 53 record sets in the zone (only the allowlisted NS, SOA and ACM-validation records may remain), KMS keys pending, log groups under `/aws/eks/`, and `rds:auto-backup`.
  - Pin the EKS log group name and either own it in L2 with `skip_destroy = false`, or disable control-plane logging.

### F-8: The NFR-1 cost controls have no decision behind them (medium)
- **Source:** PRD NFR-1 (under $30 target, $50 cap, alarm before the cap, overnight Ephemeral Stack = defect, Persistent cost tracked).
- **Problem:** the spine places the billing alarm in L0 but sets no thresholds. It also has no way to detect a Session left running overnight. AD-5's session parameter makes that detection cheap, but nothing reads it.
- **Fix:**
  - Set budgets at $30 actual and $45 forecast (a convention).
  - Add a scheduled `session-watchdog` workflow that alerts through SNS when `session/active ≠ none` for more than 4 hours. It alerts only and does not tear down, which stays consistent with FR-30.
  - Name `docs/cost-model.md` as the place where Persistent Footprint cost is tracked.

### F-9: L0's session parameter breaks FR-1's no-diff rule; retained backups add cost (medium)
- **Source:** PRD FR-1 ("Re-applying … on an unchanged account produces no diff"), FR-22. Spine AD-5, AD-9.
- **Problem:**
  - CI writes `/k8s-on-aws/session/active`, which L0 owns, so a re-plan of L0 shows drift.
  - With `delete_automated_backups = false`, every Session leaves behind a set of retained backups for the whole retention period. That storage grows with the number of Sessions.
- **Fix:**
  - Add `lifecycle { ignore_changes = [value] }` to the session parameter as an AD-5 rule.
  - Set `backup_retention_period` to the minimum FR-22 needs (1 day). Have Teardown prune retained backups older than the newest Session, except while a PITR exercise is running.

### F-10: Nothing enforces SM-C1 (medium)
- **Source:** PRD §8 SM-C1 ("Do not cut RTO by moving more resources into the Persistent Footprint"), §3 Persistent Footprint list.
- **Problem:** AD-1 lets anything that "must survive" live in L0 or L1, but there is no closed list. The spine already adds the CloudWatch log group, SNS and SSM parameters. Under RTO pressure, someone could move the ACM certificate, ALB or VPC into L1.
- **Fix:**
  - Make `scripts/teardown-check/allowlist.yaml` the closed Persistent inventory, mirroring §3 plus the documented additions.
  - Any addition needs an ADR that states it is not an RTO optimization.

### F-11: Nothing enforces NFR-6 explainability (medium)
- **Source:** PRD NFR-6 ("every component … covered by an ADR, a runbook or a write-up … removed or documented before M3").
- **Problem:** the spine introduces about 15 components (fck-nat, ESO, ExternalDNS, Kyverno, Alloy, the k8s-monitoring chart, Grafana, oauth2-proxy, the db-init Job, the GitOps Bridge annotations, and others). Nothing ties each one to documentation. Kyverno is installed before any Postmortem motivates it (FR-24).
- **Fix:**
  - Add a convention: `docs/components.md` lists every Stack-table row with a link to its ADR, runbook or write-up, and a CI check fails when a chart or module has no entry.
  - Install Kyverno only with its first Action Item.

### F-12: The Pod Security convention contradicts the observability and hardening workloads (medium)
- **Source:** PRD FR-23 (CIS scan, PSS on App namespaces). Spine Conventions › Pod security (`baseline` on the other first-party namespaces).
- **Problem:** PSS `baseline` forbids `hostPath`, `hostPID` and `hostNetwork`. The Alloy DaemonSet that reads `/var/log/pods`, the node-exporter in the k8s-monitoring chart, and kube-bench (FR-23) all need these. The spine also names no namespace for kube-bench. The Observability and Hardening epics will either break or quietly relabel namespaces.
- **Fix:** list the exceptions explicitly:
  - `observability` is `privileged`, or Alloy uses `loki.source.kubernetes` and node-exporter is dropped
  - kube-bench runs in a `privileged` namespace `security`, as a one-shot Job

### F-13: AD-10's assumption sits close to NFR-2 (low)
- **Source:** PRD NFR-2 ("no long-lived … database passwords"), FR-10.
- **Problem:** the RDS-managed master password rotates every 7 days by default, but it is still a password. Its secret is named `rds!db-…`, which conflicts with AD-17's naming rule and its "no secret in L2" rule. AD-17 also doesn't say how db-init reads it, since it can't go through ESO under the name convention.
- **Fix:**
  - Carve out an AD-17 exception for the RDS-managed secret, read directly by db-init through Pod Identity.
  - Shorten rotation to 1 day or less.
  - Keep the assumption visible in the RDS ADR.

### F-14: Argo CD auto-sync will recreate the apps AD-7 deletes (low)
- **Source:** Spine AD-4, AD-7. Addendum controller pitfall.
- **Problem:** the root app-of-apps with self-heal re-creates deleted child apps.
- **Fix:** AD-7's first step disables auto-sync on the root app, or deletes it with non-cascading delete, before deleting the workload apps.

### F-15: Two automated write paths to `main` (low)
- **Source:** Spine AD-16 (CI bump commit), AD-20 (pipeline-written Rebuild Log). Deferred lists only the Rebuild Log.
- **Fix:** defer one decision, "how the pipeline commits to `main`", that covers both the image bumps and the Rebuild Log.

### F-16: Minor items (low)
- **ci-apply privileges.** ci-apply needs `iam:CreateRole` for Pod Identity roles, which risks self-escalation even though AD-18 says CI can't change its own roles. Add a permissions boundary and an explicit deny on `k8s-on-aws-ci-*`, the state bucket policy, and the budgets.
- **Teardown changes Persistent resources.** It prunes snapshots, which is required by FR-16 but technically conflicts with FR-1's "Teardown never … changes a Persistent Footprint resource". Note this as an accepted PRD tension.
- **Alloy → CloudWatch Logs.** Check that Alloy 1.21 ships a CloudWatch Logs exporter. If it doesn't, name the alternative (Fluent Bit / CloudWatch Observability add-on) before the Observability epic starts.
- **Manual steps in the Rebuild Log.** `manual_steps[]` can't be detected by the pipeline. Say that the Operator fills it through the `notes` PR, or through a workflow input.
