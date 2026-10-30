---
title: "Implementability Review: PRD Kubernetes-on-AWS"
reviewed: prd.md, addendum.md (both 2026-10-27)
created: 2026-10-27
reviewer_stance: adversarial, from the point of view of an architect/agent who must turn this PRD into architecture, epics and stories
---

# Implementability Review: PRD Kubernetes-on-AWS

## Verdict

**Not ready to decompose into epics without a revision pass.** The product intent is clear and unusually well bounded, but four issues would send a builder down a wrong path: the Rebuild/Teardown trigger model is undefined (and as written, merging a PR outside a Session would rebuild the paid stack), Teardown as defined will fail or leak cost because of AWS resources created by in-cluster controllers, the SLI as described cannot detect the flagship auth-outage incident, and the M1 "done when" cannot be met under the glossary's own definition of Rebuild. Most other findings are missing acceptance details or AWS mechanics the PRD gets wrong or leaves to guesswork.

**Severity scale**
- **Critical:** a builder following the PRD literally would build the wrong thing, or the thing would not work.
- **High:** a builder would have to guess at something that changes the design, cost or acceptance.
- **Medium:** an ambiguity or gap that produces rework or untestable stories.
- **Low:** wording, polish, or small cost/clarity risks.

| Severity | Count |
|---|---|
| Critical | 4 |
| High | 11 |
| Medium | 16 |
| Low | 8 |
| **Total** | **39** |

---

## Critical

### C-1. The Rebuild and Teardown trigger model is undefined and self-contradictory
- **Location:** UJ-1 (§2.3), FR-12, FR-20, Glossary "Teardown", NFR-1
- **Quotes:**
  - UJ-1: "He opens a PR, merges it, and one `terraform apply` brings back the network, cluster and database"
  - FR-12: "Merging triggers the apply."
  - FR-20: "One `terraform apply` plus an Argo CD sync takes the account from Persistent Footprint only to an App serving authenticated requests"
  - NFR-1: "An Ephemeral Stack left running overnight counts as a cost defect."
- **Problem:** Three different start mechanisms are implied: a PR merge (UJ-1), an apply triggered by any merge (FR-12), and an operator-run `terraform apply` (FR-20). Nothing says how "stack exists" versus "stack torn down" is represented. If the ephemeral configuration is applied on every merge to main, then merging any infra PR outside a Session (a docs-adjacent Terraform tweak, a Postmortem Action Item) silently rebuilds the EKS stack and starts billing, which is exactly the NFR-1 defect. If instead the desired state lives in Git (e.g. `enabled = true`), every Session needs two PRs, and Teardown becomes a PR too, which UJ-1 does not describe. Teardown's trigger (CI job, local command, PR) is never stated, and nor is whether it must go through Git under NFR-3 "all Platform state is defined in Git". An architect cannot design the pipeline without this.
- **Suggested fix:** Add an FR (or extend FR-12/FR-20) that fixes the model explicitly, for example: "The Ephemeral Stack is created and destroyed only by dedicated, manually dispatched pipeline workflows (`rebuild`, `teardown`) that run from `main`. Merges to `main` plan the ephemeral configuration but apply it only when the stack is currently up. Merges never create the Ephemeral Stack." State that Rebuild/Teardown dispatches are recorded (workflow run URL) in the Rebuild Log, which keeps the Git audit trail without a PR per Session. Rewrite UJ-1 to match.

### C-2. Teardown as defined will fail or leak cost: controller-created AWS resources are outside Terraform
- **Location:** Glossary "Teardown", FR-1, FR-2, FR-14, NFR-1
- **Quotes:**
  - Glossary: "Teardown: the automated destruction of the Ephemeral Stack, preceded by a final RDS snapshot."
  - Glossary: "Ephemeral Stack: ... VPC, EKS cluster, node group, RDS instance, and in-cluster workloads."
  - FR-2: "The App is reachable at a stable hostname under the registered domain after every Rebuild, with no manual DNS edits."
  - FR-1: "Running Teardown never destroys or changes a Persistent Footprint resource."
- **Problem:** The Gateway API implementation (FR-14) will provision a load balancer, target groups and security groups from inside the cluster; any PVC creates EBS volumes; a DNS automation (external-dns or similar) writes records into the persistent hosted zone. None of these are in Terraform state. A plain `terraform destroy` of the cluster leaves the load balancer, its ENIs and security groups behind, so the VPC/subnet destroy hangs or fails, and the orphaned load balancer (roughly $16+/month plus public IPv4 charges) keeps billing silently. Stale Route 53 records are left pointing at dead load balancers. Also, deleting those DNS records *changes* the persistent hosted zone, which violates FR-1's literal wording. The PRD gives no Teardown ordering requirement, so a builder will discover this the first time destroy fails.
- **Suggested fix:** Add Teardown acceptance criteria: (1) in-cluster resources that own AWS resources (Gateway/Service type LoadBalancer, PVCs, DNS records) are deleted and confirmed gone before cluster and VPC destroy; (2) after Teardown, an automated residue check finds zero load balancers, EBS volumes, ENIs, EIPs or target groups tagged for the stack; (3) a Teardown that leaves residue is a failed Teardown, recorded like a failed Drill. Amend FR-1 to say "DNS records created by the Ephemeral Stack belong to the Ephemeral Stack even though they live in the persistent hosted zone."

### C-3. The success SLI as described cannot detect the auth-outage Incident, and per-Session traffic may be zero
- **Location:** UJ-2, FR-15, FR-17, FR-18, Glossary "SLI"
- **Quotes:**
  - UJ-2: "An alert fires because the app's success SLI drops."
  - FR-15: "An unauthenticated request is redirected to sign-in and never reaches App code."
  - Glossary: "an SLI is a measured user-facing signal (request success rate, request latency)"
- **Problem:** If the identity provider or the SSO proxy is broken, failing requests stop at the proxy or at Cognito. They never reach the App, so an App-instrumented success SLI stays at 100% (or has no data) and UJ-2's alert never fires. The flagship incident story is unbuildable as written. Separately, there is one user. Outside the minutes the operator is clicking, there is no traffic, so the SLI is 0/0 and the alert cannot fire for any scenario. The PRD never says where the SLI is measured (edge, proxy, App), what counts as success (are 302 redirects to sign-in successes? 4xx?), or that synthetic traffic exists.
- **Suggested fix:** Specify in FR-17/FR-18: "SLIs are measured at the edge (Gateway/proxy) and by a synthetic probe that performs an authenticated request (sign-in plus list workouts) at a fixed interval throughout the Session. Success = 2xx/3xx on the probe's expected final response; 5xx, timeouts and redirect loops are failures." Note that the probe needs a dedicated Cognito test user whose credential is held in Secrets Manager, and record that as an accepted secret under NFR-2. Add an acceptance criterion to FR-25/FR-26: "each injected fault causes the SLO alert to fire within N minutes, or the Postmortem records it as a monitoring miss."

### C-4. M1's exit criterion is unachievable under the glossary's definition of Rebuild; several M1 FRs depend on M2 FRs
- **Location:** §6 Milestones (M1 row), Glossary "Rebuild" and "RTO", FR-2, FR-3, FR-6, FR-10, FR-11, FR-20, FR-21
- **Quotes:**
  - M1 done-when: "The Platform rebuilds from code, and the network ADR and Pod Identity ADR are written."
  - Glossary: "Rebuild: the automated creation of the Ephemeral Stack from code, ending when the App is reachable and authenticated."
  - M1 features: "FR-1–FR-11, FR-16, FR-20, FR-21 baseline started"
- **Problem:** By definition a Rebuild ends only when the App serves authenticated requests. That needs FR-13 (Argo CD), FR-14 (Gateway ingress) and FR-15 (Cognito SSO), all in M2. So in M1 no Rebuild can complete, no RTO can be measured (FR-21 "baseline started" is impossible), and FR-20 cannot pass. Other M1 FRs have the same dependency inversion:
  - FR-2: "App is reachable at a stable hostname" needs the App and ingress (M2).
  - FR-3: "An App User ... can sign in after the next Rebuild" needs FR-15 (M2).
  - FR-6: the packet path runs "through ... Gateway API ingress, to the App pod" (M2).
  - FR-10: "the SSO proxy's cookie secret" needs the SSO proxy (M2).
  - FR-11: "Every workload declares ... requests and limits" needs the workloads (mostly M2/M3).
  An agent generating epics from this table will produce M1 stories that cannot be accepted.
- **Suggested fix:** Either (a) move FR-13, FR-14 and FR-15 (and a minimal App) into M1 and accept a larger M1, or (b) define an interim M1 exit, "Ephemeral Stack reaches a healthy cluster plus a restored RDS instance from code; Infra-RTO measured", and move FR-2 (hostname part), FR-3 (sign-in part), FR-6, FR-10 (proxy secret), FR-20, FR-21 baseline and FR-11 (final evidence) to M2. Option (b) also needs a glossary term such as "Infra-RTO" so the two measures are never mixed in the Rebuild Log.

---

## High

### H-1. The RTO ceiling equals the expected Rebuild duration; RTO start and end points are not measurable as written
- **Location:** Glossary "RTO", FR-21, NFR-5, SM-2, addendum "RDS snapshot mechanics", UJ-1
- **Quotes:**
  - Glossary: "RTO: the wall-clock time from the start of a Rebuild to the App serving authenticated requests."
  - FR-21: "A Drill whose RTO exceeds 45 minutes is a failed Drill"
  - Addendum: "Restore time adds about 10–20 minutes to the Rebuild, which takes 30–45 minutes in total."
  - SM-2: "Every Drill is ≤ 45 minutes after baselining"
- **Problem:**
  1. The ceiling (45 min) equals the top of the expected range, so ordinary variance (Spot capacity, a slow RDS restore, certificate validation, DNS propagation, load balancer provisioning) produces "failed" Drills by design. The PRD also never requires the RDS restore to run in parallel with EKS creation. Run sequentially, roughly 12–15 min of EKS, 3–5 min of node group, 10–20+ min of RDS restore and then add-ons, Argo sync, load balancer and DNS exceed 45 minutes.
  2. FR-21 fails any Drill over 45 minutes, including the 5 baseline Drills, while SM-2 applies the ceiling only "after baselining". These contradict each other.
  3. "Start of a Rebuild" could mean PR open, merge, workflow dispatch or first `terraform apply`. "Serving authenticated requests" could be a human sign-in (UJ-1: "He times the run ... signs in") or a probe. Human-timed measurements are not comparable across Drills, and a human sign-in as the end event contradicts "zero manual steps".
- **Suggested fix:** Define RTO start as "timestamp the Rebuild workflow job starts" and end as "first successful authenticated synthetic probe (see C-3)", both recorded automatically into the Rebuild Log. Make the ceiling apply only after Drill 5, as SM-2 says. Add an architecture constraint: "RDS restore and EKS creation must not be serialised in the dependency graph." Consider recording a per-phase breakdown (network, cluster, nodes, RDS, Argo sync, edge) in each Rebuild Log entry so that "each RTO improvement is logged with its cause" can actually be done.

### H-2. The snapshot-restore mechanism in the addendum breaks the first-Rebuild fallback and can destroy the database mid-Session
- **Location:** FR-16, addendum "RDS snapshot mechanics", FR-12, FR-22
- **Quotes:**
  - Addendum: "Restore has to look up the latest snapshot, for example with `aws_db_snapshot` and `most_recent = true`."
  - FR-16: "When no snapshot exists ... Rebuild creates an empty database and runs schema setup instead of failing."
  - Glossary "RPO": "the latest usable snapshot"
- **Problem:**
  1. The `aws_db_snapshot` data source returns an error when no snapshot matches, so the suggested mechanism makes the first Rebuild fail. That is the very case FR-16 says must not fail.
  2. Any mid-Session apply (FR-12: every merge applies) re-evaluates "most recent". If a newer snapshot has appeared since the instance was created (an automated snapshot, an FR-22 drill snapshot, a manual one), `snapshot_identifier` changes and Terraform plans a **replacement of the live RDS instance**. That means data loss during a Session.
  3. "Usable" is undefined. A snapshot taken after a data-corrupting bad-deploy Incident is the most recent and would be restored silently.
- **Suggested fix:** Add acceptance criteria to FR-16: "Snapshot lookup succeeds with zero snapshots (lookup is done via a list call or a wrapper, not a data source that errors on empty)"; "Only manual Teardown snapshots matching the project's naming prefix are candidates"; "A mid-Session apply never replaces the RDS instance (the snapshot identifier is ignored after creation)"; "A snapshot can be marked unusable (tag) and is then skipped." Remove or correct the addendum example.

### H-3. Snapshot accumulation: no retention requirement, a hard AWS quota, and a contradiction with FR-1
- **Location:** Glossary "Persistent Footprint", FR-1, FR-16, Open Question 2, NFR-1, addendum "Final snapshot IDs"
- **Quotes:**
  - Glossary: Persistent Footprint includes "RDS snapshots"
  - FR-1: "The Operator can create the entire Persistent Footprint with Terraform ... Re-applying the Persistent Footprint configuration on an unchanged account produces no diff."
  - OQ2: "a retention policy is needed to keep storage within NFR-1."
  - Addendum: "A naive timestamp in the identifier causes a perpetual Terraform diff."
- **Problem:**
  1. Snapshots are created by Teardown (the Ephemeral configuration's destroy), not by the Persistent Footprint configuration, so "the entire Persistent Footprint is created from code [in a dedicated configuration]" cannot be true for snapshots. They are orphaned outside any Terraform state.
  2. A retention policy is raised only as an Open Question, not as an FR, so nobody will build it. RDS has a default quota of 100 manual snapshots per region. At roughly one Session a day, Teardown starts failing in about three months, and a failed final snapshot can block destroy or tempt `skip_final_snapshot`.
  3. Snapshots of a deleted instance are billed at full snapshot-storage rates; the free backup allowance applies only to running instances.
  4. The addendum names the unique-ID problem but gives no solution.
- **Suggested fix:** Add an FR: "Snapshots older than the newest N (e.g. 5), excluding any tagged `keep`, are deleted automatically after a successful Rebuild restore. The snapshot count never exceeds N+keep." Reword the glossary so that RDS snapshots are "data that survives Teardown, managed by the retention job, not by the Persistent Footprint configuration". Record the unique-ID approach as an architecture constraint, for example an identifier fixed once at instance creation (a static timestamp or random suffix stored in state), not a timestamp evaluated at plan time.

### H-4. Domain registration contradicts "created in Terraform" and "no manual steps", and Route 53 registration creates its own hosted zone
- **Location:** §4.1 description, FR-2, FR-20 [ASSUMPTION], OQ1, Glossary "Persistent Footprint"
- **Quotes:**
  - §4.1: "It is created once, in Terraform ... The Persistent Footprint includes the registration of a new domain"
  - FR-20: "again with no manual steps beyond domain registration. [ASSUMPTION: ... domain registration is a one-off, accepted exception.]"
- **Problem:** §4.1 says registration is part of the Terraform-created footprint, while FR-20 says it is a manual exception. A builder cannot tell whether to write Terraform for it. Practical traps the PRD does not mention:
  - Registering through Route 53 automatically creates a hosted zone. If Terraform also creates `aws_route53_zone`, you get two zones, and the registrar's NS records point at the wrong one, so DNS and certificate validation fail silently.
  - ICANN registrant-contact email verification is an unavoidable manual step (unverified domains get suspended).
  - Registration can take minutes to hours, and it is a non-refundable annual charge that cannot be destroyed and recreated. FR-1's "apply to an empty account" therefore cannot be re-run idempotently on a second account.
- **Suggested fix:** Decide now. Recommended: "Domain registration is a one-time manual step, done before the Persistent Footprint apply and recorded in a runbook. The Persistent Footprint configuration *imports or adopts* the hosted zone Route 53 created at registration (it does not create a second zone) and asserts that the registrar's NS records match it." Remove "registration" from the §4.1 Terraform sentence and add "contact email verification" to the accepted exception.

### H-5. Bootstrap chicken-and-egg: items the pipeline needs are missing from the Persistent Footprint
- **Location:** Glossary "Persistent Footprint", FR-1, FR-9, FR-12, FR-20, NFR-1, NFR-2
- **Quotes:**
  - FR-20: "The Persistent Footprint configuration can itself be applied to an empty AWS account."
  - FR-12: "Pipeline jobs authenticate to AWS only through OIDC (FR-9)."
  - FR-9: "No long-lived AWS keys exist anywhere."
- **Problem:** The Persistent Footprint list leaves out things that must exist before any Rebuild and survive Teardown:
  - the GitHub OIDC identity provider and CI IAM role(s): CI cannot run a Rebuild without them, and they cannot be created by a pipeline that needs them to authenticate
  - the billing alarm or budget (NFR-1)
  - long-lived Secrets Manager secrets (FR-10)
  - the ACM certificate, if the architecture keeps it there
  - any KMS keys shared across Rebuilds

  The state backend bucket also cannot store its own state on first apply. So "applied to an empty account with no manual steps" is impossible as written. There is at least a local-state bootstrap run with human credentials. Human AWS access is never specified: an IAM user with access keys would violate FR-9, so IAM Identity Center is implied but not stated.
- **Suggested fix:** Extend the glossary list with the CI OIDC provider and roles, billing alarm/budget, persistent secrets and (if chosen) the certificate. Add an FR: "A documented bootstrap step (run once, locally, with IAM Identity Center credentials) creates the state backend and CI role. Everything after it runs through the pipeline." State in NFR-2 how the operator authenticates to AWS.

### H-6. The Terraform-to-Argo CD handoff is unspecified, and "Argo CD owns every in-cluster resource" is not literally achievable
- **Location:** FR-13, FR-20, FR-9, FR-10, FR-14
- **Quotes:**
  - FR-13: "Argo CD owns every in-cluster resource, App included, and syncs it from Git after a Rebuild with no manual `kubectl apply`."
- **Problem:**
  1. Argo CD cannot install itself. Something (Terraform Helm release, a bootstrap script) installs Argo CD and the root Application.
  2. EKS managed add-ons (VPC CNI with network policy enabled, CoreDNS, kube-proxy, Pod Identity agent) are normally Terraform-managed and are in-cluster resources.
  3. Manifests in Git need values Terraform produces per Rebuild: the role ARNs behind Pod Identity associations, the certificate ARN, Cognito client ID, RDS endpoint, subnet or security group IDs for the load balancer. The PRD gives no mechanism (deterministic names, Argo cluster-secret annotations, a Terraform-written ConfigMap), and the obvious one (Terraform writes a ConfigMap) violates FR-13's "every".
- **Suggested fix:** Reword FR-13: "Argo CD owns every in-cluster resource except the Argo CD bootstrap and EKS managed add-ons, which Terraform owns. Rebuild-specific values reach Argo CD through one documented mechanism, chosen in architecture, and no value is hand-copied." Add a testable criterion: "After Rebuild, `argocd app list` shows all Applications Synced/Healthy with no manual action."

### H-7. Per-Session SLO math does not work at this traffic volume and Session length
- **Location:** FR-18, Glossary "Session", "SLI / SLO / Error Budget", "Incident"
- **Quotes:**
  - FR-18: "Availability: ≥ 99% of requests succeed. Latency: ≥ 95% of requests complete in < 500 ms."
  - FR-18: "When the Error Budget is exhausted, the change that caused it is reverted rather than patched forward."
  - Glossary: "Session: one working block during which the Ephemeral Stack exists. SLOs are evaluated per Session."
  - Glossary: "Incident: ... degradation of the App that breaches or threatens an SLO"
- **Problem:**
  - With roughly 100–700 requests a Session (mostly synthetic), a 1% budget is 1–7 requests. A single cold-start failure exhausts it, and every injected Incident exhausts it by definition.
  - Standard multi-window burn-rate alerting (for example 1h/5m windows at 14.4x) is calibrated for 28–30-day windows. Over a 2-hour window, "burn rate" needs a redefined baseline.
  - The Session start is ambiguous. If it starts when the Stack exists, the Rebuild warm-up (before the App is healthy) counts against the budget.
  - The revert rule cannot apply to node or network faults, where there is no change to revert.
  - A node failure that the platform absorbs (several replicas) would not "breach or threaten an SLO", so it would not qualify as Incident 3.
- **Suggested fix:**
  - Define the SLO window as "from RTO end to Teardown start".
  - Fix a minimum synthetic request rate (e.g. 1 req/10 s, so about 700 requests in 2 hours, giving a 1% budget of about 7 failures).
  - Define burn-rate alert windows explicitly for a 2-hour SLO window.
  - Scope the revert rule to "budget exhausted by a deployed change".
  - Allow an Incident to be declared on "observable user impact or an SLO alert" rather than SLO breach alone.

### H-8. Issuing TLS certificates on every Rebuild has rate-limit and RTO consequences, and conflicts with SM-C1
- **Location:** FR-2 [ASSUMPTION], addendum "Where TLS certificates live", SM-C1, H-1
- **Quotes:**
  - FR-2: "[ASSUMPTION: certificates are created during Rebuild, not kept in the Persistent Footprint; the architecture step decides.]"
  - SM-C1: "Do not cut RTO by moving more resources into the Persistent Footprint."
- **Problem:** If the architecture chooses cert-manager with Let's Encrypt, a fresh certificate per Rebuild runs into Let's Encrypt's duplicate-certificate limit (5 per identical hostname set per week). Daily Rebuilds plus failed retries would make Rebuilds fail. ACM issuance per Rebuild avoids that but adds validation time to RTO. Keeping an ACM certificate in the Persistent Footprint is free and faster, but SM-C1 discourages exactly that move. The builder is left to resolve a requirement tension the PRD created.
- **Suggested fix:** Add a constraint to FR-2: "Certificate issuance must tolerate at least 2 Rebuilds per day indefinitely without hitting issuer rate limits." Exempt zero-cost, non-compute resources from SM-C1, or decide here that the ACM certificate is in the Persistent Footprint.

### H-9. No requirement covers building and shipping the App image, so the bad-deploy path is undefined
- **Location:** FR-3, FR-12, FR-13, FR-25 "bad deploy", §7 "no multi-service image pipelines"
- **Quotes:**
  - FR-3: "A Rebuild does not need to rebuild or push container images."
  - FR-13: "Reverting a commit restores the previous App version within one sync cycle."
- **Problem:** FR-12 covers Terraform and FR-13 covers in-cluster manifests, but nothing covers how an App code change becomes an image in ECR and a new reference in Git: CI build and push, tag scheme (immutable SHA versus mutable), and whether the manifest change is a commit or comes from an image-updater tool. FR-13's "revert restores the previous version" only holds if image references are immutable and live in Git. A "bad deploy" Incident (FR-26 #1) needs this path to exist.
- **Suggested fix:** Add an FR: "A merge to the App source builds an image, pushes it to ECR with an immutable tag (Git SHA), and opens or commits a manifest change that pins that tag. ECR tag immutability is enabled. Reverting the manifest commit redeploys the previous image within one Argo CD sync."

### H-10. "No static database password exists" contradicts RDS master credentials, and schema setup has no owner
- **Location:** FR-10, FR-16
- **Quotes:**
  - FR-10: "The App authenticates to RDS with IAM database authentication. No static database password exists."
  - FR-16: "Rebuild creates an empty database and runs schema setup"
- **Problem:** An RDS instance always has a master user and password. A builder reading FR-10 literally will try to avoid one and fail. IAM auth also requires a database user created with `GRANT rds_iam`. That has to happen at schema setup on the first Rebuild, using the master credential, and the PRD does not say who runs it (Terraform provisioner, a Kubernetes Job synced by Argo CD, a migration tool in the App) or how it stays idempotent across restored snapshots.
- **Suggested fix:** Reword FR-10: "The App holds no database password; it uses IAM database authentication. The RDS master credential is generated and stored by RDS-managed Secrets Manager integration, never appears in Git or Terraform variables, and is used only by schema setup." Add to FR-16: "Schema setup and the IAM-auth user grant run as an idempotent, Git-defined job that succeeds on both an empty and a restored database."

### H-11. Recreating names on every Rebuild collides with AWS deletion windows
- **Location:** FR-10, FR-20, Glossary "Ephemeral Stack", SM-1
- **Quotes:**
  - FR-10: "Any remaining secret ... is stored in AWS Secrets Manager"
  - FR-20: "with zero manual steps"
- **Problem:** The PRD does not say whether secrets, KMS keys and log groups are ephemeral or persistent. If they are ephemeral with fixed names:
  - A deleted Secrets Manager secret is held for a 7–30-day recovery window (30 days by default), and creating a secret with the same name fails during that window. The second Rebuild fails.
  - KMS keys (the common EKS Terraform module creates one for secrets encryption by default) go into a 7–30-day pending-deletion state, so one accumulates per Rebuild.
  - The EKS control-plane log group can be re-created outside Terraform by EKS, which produces "already exists" errors on the next apply.

  Each of these breaks SM-1 ("zero-touch").
- **Suggested fix:** Add an acceptance criterion to FR-20: "Two consecutive Rebuild/Teardown cycles in the same day succeed with no manual cleanup." Require each such resource to be explicitly classified as Persistent or Ephemeral. Ephemeral ones use force-delete settings (secret recovery window 0) or unique names.

---

## Medium

### M-1. Glossary terms are used inconsistently
- **Location:** Glossary; §4.9 title; FR-22; FR-13; M1 done-when; §2.1; NFR-3
- **Quotes:** "Drill: one Rebuild, timed and recorded. Every Rebuild is a Drill." versus "§4.9 Incident Drills" and "FR-22: Unplanned data-loss drill"; "Rebuild ... ending when the App is reachable and authenticated" versus FR-13 "syncs it from Git after a Rebuild"; "Session: one working block during which the Ephemeral Stack exists" versus §2.1 "every 2-hour session" (including weekday kind sessions with no Ephemeral Stack); M1 "The Platform rebuilds from code" (Platform includes the Persistent Footprint, which is not rebuilt); NFR-3 "all Platform state is defined in Git" (RDS data and Cognito users are not).
- **Problem:** "Drill" means a Rebuild in one place and an incident exercise in another, so a builder cannot tell whether Incident Drills get Rebuild Log entries. Argo CD sync is both inside the Rebuild (by the glossary) and after it (FR-13). "Operator" and "App User" are used as defined roles but are not in the glossary.
- **Suggested fix:** Rename §4.9 to "Incident Exercises" and FR-22 to "Unplanned data-loss recovery". Change FR-13 to "as part of every Rebuild". Use lowercase "work session" for non-EKS blocks. Replace "Platform" with "Ephemeral Stack" in M1. Scope NFR-3 to "configuration state". Add "Operator" and "App User" to the glossary.

### M-2. The unplanned data-loss drill is ill-defined, and automated backups do not survive Teardown by default
- **Location:** FR-22, Glossary "Persistent Footprint", addendum "An unplanned failure falls back to the last automated backup."
- **Quote:** FR-22: "the Operator recovers the database from automated backups without a fresh final snapshot, and records the resulting RPO."
- **Problem:** Automated backups are deleted with the instance unless they are explicitly retained on delete, and retained backups are neither in the Persistent Footprint list nor in the cost model. The failure being simulated (instance deletion without a snapshot, data corruption, AZ loss) is not stated. Point-in-time restore is a third code path, besides snapshot restore and empty-create, that Terraform must support. Within a 2-hour Session the only automated backup may be the one taken at creation, so the measured RPO depends on PITR log shipping and not on "backups".
- **Suggested fix:** Specify the scenario (for example: "delete the instance mid-Session with no final snapshot, then restore to the latest restorable time from retained automated backups"). Require retained automated backups with a short retention, add them to the Persistent Footprint list and cost model, and state that this path may be a documented runbook rather than part of the Rebuild code.

### M-3. RPO = 0 is tautological as defined and has no measurement procedure
- **Location:** Glossary "RPO", FR-16, SM-7
- **Quotes:** "RPO: ... the time between the latest usable snapshot or backup and the failure or Teardown"; SM-7: "RPO = 0 on every planned Teardown."
- **Problem:** With a final snapshot, the definition gives 0 by construction, so it cannot detect a real loss (for example a write committed after the App was scaled down but before the snapshot completed, or a restore from the wrong snapshot).
- **Suggested fix:** Define the measurement: "Before Teardown, a canary record with a timestamp is written. After Rebuild, the newest record's timestamp is compared with the canary; RPO = Teardown start minus newest restored record." Automate it in the Rebuild Log.

### M-4. "Baselined", the tolerance for manual steps, and drift handling are undefined
- **Location:** FR-21, FR-20, SM-1, NFR-3
- **Quotes:** FR-21 "RTO is baselined over the first 5 Drills"; FR-20 "with zero manual steps"; SM-1 "100% of Drills after Drill 5 complete with no manual steps"; NFR-3 "Any drift found during a Drill is fixed in code, not by hand."
- **Problem:** The baseline statistic (median, mean, best) is not given, so the stretch target "≤ 30 min after baselining" has no reference. FR-20 says zero manual steps always, while SM-1 tolerates them for Drills 1–5. The PRD does not say whether a Drill that needs a manual fix can be finished by hand (and recorded) or must be aborted, which NFR-3 implies.
- **Suggested fix:** Define the baseline as the median RTO of Drills 1–5. State that FR-20 is enforced from Drill 6 onward. Add: "A manual intervention is allowed to finish a Drill, is logged as a Drill failure with its cause, and must be codified before the next Drill."

### M-5. Network-policy acceptance is ambiguous about direction and about the out-of-cluster database
- **Location:** FR-5
- **Quote:** "the App namespace defaults to deny. A pod without an explicit allow rule cannot reach the App or the database path."
- **Problem:** It does not say whether default-deny covers ingress, egress or both. "Database path" is outside the cluster: RDS's private IP is not stable across Rebuilds, so an IP-based egress rule is fragile, and security groups, not NetworkPolicy, gate the RDS port. Default-deny egress also breaks DNS, the Pod Identity agent endpoint, STS and Cognito unless each is allowed, so a builder will hit outages with no guidance.
- **Suggested fix:** State "default-deny ingress and egress in App namespaces; required egress (DNS, Pod Identity agent, AWS APIs, Cognito, RDS subnet CIDRs) is allowed explicitly". Make the acceptance a test: "a pod in another namespace and an unlabeled pod in the App namespace both fail to connect to the App service and to the RDS port; the App pod succeeds."

### M-6. Identity propagation, header trust and user provisioning are unspecified
- **Location:** FR-15, FR-3
- **Quotes:** FR-15 "A user sees only their own workouts."; FR-3 "An App User created before a Teardown can sign in after the next Rebuild."
- **Problem:** The App learns who the user is from headers set by the SSO proxy. If anything can reach the App without going through the proxy, a forged identity header bypasses tenancy. The identity key is not named (Cognito `sub` is stable; email may change). How App Users are created (self sign-up, admin-created, test users) is never stated.
- **Suggested fix:** Add to FR-15: "The App keys data by the Cognito `sub` claim; it accepts identity only from the proxy; a request sent directly to the App service with a forged identity header is rejected or is unreachable (tested)." Add to FR-3: "App Users are admin-created; self sign-up is disabled."

### M-7. SLO history has no retention or granularity requirement, and one candidate store cannot meet the trend goal
- **Location:** FR-19, addendum "SLO history store", OQ3
- **Quote:** "SLI and SLO results from past Sessions stay queryable after Teardown, so trends span Sessions."
- **Problem:** No retention is given. Grafana Cloud's free tier keeps metrics for about 14 days, which is shorter than the 6–8-week project, so it would fail silently. Whether raw time series or per-Session summaries are required decides between Amazon Managed Prometheus, which has an ongoing cost, and something free. Dashboards also need a persistent home if Grafana runs in the cluster (ephemeral). Amazon Managed Grafana adds $9 per editor per month to the Persistent Footprint.
- **Suggested fix:** Specify "per-Session SLI summary (availability, latency SLI, budget consumed, Session start/end) retained ≥ 12 months; raw series optional". Note that a per-Session summary committed to Git or S3 meets this at near-zero cost. Require dashboards to be defined as code in Git.

### M-8. The EKS version pre-flight check is undefined, and the upgrade story is awkward on an ephemeral cluster
- **Location:** FR-7, FR-8
- **Quotes:** FR-7 "A version entering extended support fails a pre-flight check."; FR-8 "performs at least one EKS minor version upgrade"
- **Problem:** The PRD does not say where the check runs (CI before apply, a Terraform check block), what source it uses (the EKS describe-cluster-versions API versus a hard-coded date) or what "entering" means. It also does not say whether the cluster's upgrade policy should be set to standard-only so that extended-support charges ($0.60/hr) can never apply. On a cluster rebuilt every Session, the obvious "upgrade" is bumping the pin and rebuilding, which is a fresh install and not an in-place upgrade. FR-8's "observed impact on SLIs" requires an in-place upgrade during a Session.
- **Suggested fix:** Specify that the check runs in the Rebuild workflow before apply and queries the AWS API, and that the cluster upgrade policy is set to standard support. Add to FR-8: "the upgrade is in place, during a Session, with SLIs observed throughout."

### M-9. Capacity constraints are not stated: pod density and CPU architecture
- **Location:** FR-7, FR-11, addendum cost table (t3.medium and t4g.medium)
- **Quote:** FR-11: "The Operator documents how the node group is sized against those requests."
- **Problem:** With the default VPC CNI, a t3.medium holds 17 pods. Argo CD (around 7 pods), Alloy, Kyverno, the chaos tool, the gateway controller, oauth2-proxy, the App, CoreDNS and DaemonSets fill a two-node group quickly, and pods go Pending during Drills. The addendum lists both x86 (t3) and Arm (t4g) Spot instances. If t4g is chosen, the App image must be built for arm64, which affects H-9.
- **Suggested fix:** Pin the CPU architecture in the PRD or hand it to architecture explicitly with the image consequence. Add to FR-11: "the node group has ≥ 20% headroom in both requested CPU/memory and the pod-IP limit, with prefix delegation or instance size chosen accordingly."

### M-10. FR-24 is circular and can be met vacuously
- **Location:** FR-24, SM-C2
- **Quote:** "Admission policies (Kyverno) are introduced as Postmortem Action Items. Each policy links to the Postmortem that motivated it."
- **Problem:** If no Postmortem motivates a policy, FR-24 is satisfied with zero policies, or the operator feels pushed to stage an Incident that ends in a Kyverno fix, which works against SM-C2. Kyverno's installation itself (an M3 component that needs capacity and an ADR under NFR-6) has no owner.
- **Suggested fix:** Either "Kyverno is installed in M2 with zero policies; at least one Postmortem Action Item is an admission policy" (so the outcome is committed), or make FR-24 conditional and remove Kyverno from the committed scope.

### M-11. Incident count and injection-path wording conflict
- **Location:** FR-25, FR-26, §4.4 description, Glossary "Incident"
- **Quotes:** FR-26 "Exactly three committed Incidents are run"; Glossary "an unplanned (or injected) degradation"; §4.4 "Injected faults use the same pipeline as real changes."; FR-25 "from code or a documented command"
- **Problem:** "Exactly three" turns a real unplanned Incident (likely, for example a failed Drill) into a scope violation. FR-25 requires four fault types, but FR-26 combines node and network into one, so one type is built and never used in an Incident. §4.4 says all faults go through the pipeline; FR-25 allows ad-hoc commands, and node failure via FIS or chaos tooling is not a Git change.
- **Suggested fix:** Use "at least three committed Incidents, one per scenario". State that a Git-driven injection (a bad-deploy commit) and command-driven injection (chaos experiments defined in Git, triggered by a recorded command) are both allowed. Reword §4.4 to match.

### M-12. There is no safety net for a forgotten Teardown, and a billing alarm cannot enforce a hard cap
- **Location:** NFR-1
- **Quote:** "hard cap of $50/month. A billing alarm alerts before the cap. ... An Ephemeral Stack left running overnight counts as a cost defect."
- **Problem:** An alarm cannot cap spend, the threshold is not given, and billing data lags by hours. Nothing detects a forgotten stack. Running all month, EKS alone is about $73.
- **Suggested fix:** Add: "A scheduled check (e.g. nightly) detects a running Ephemeral Stack outside a Session and notifies the operator or runs Teardown automatically. Budget alerts at 50%, 80% and 100% of $30, plus a forecast alert at $50."

### M-13. A 2-hour Session has no Teardown time budget
- **Location:** §2.1 JTBD, §6 intro, FR-21, NFR-5
- **Quotes:** "finish every 2-hour session with something visible"; NFR-5 "RTO ≤ 45 minutes"
- **Problem:** Teardown time is not measured or bounded. A 45-minute Rebuild plus roughly 15–25 minutes of destroy (EKS deletion, final snapshot, load balancer cleanup) leaves about 50 minutes of work, which affects how stories are sized.
- **Suggested fix:** Record Teardown duration in the Rebuild Log and add a soft target (e.g. ≤ 20 min). State that EKS Sessions are at least 3 hours, as §6's weekend-block wording implies.

### M-14. Least-privilege CI conflicts with a CI role that creates IAM, EKS and VPC
- **Location:** NFR-2, FR-9, FR-12
- **Quote:** NFR-2 "least-privilege IAM for each identity"
- **Problem:** The Rebuild role must create IAM roles, which is effectively admin. Without a stated approach, a builder either grants AdministratorAccess (violating NFR-2) or spends days hand-tuning a policy.
- **Suggested fix:** State the accepted approach: separate plan (read-only, used on PRs) and apply (main-branch only) roles. The apply role can create IAM roles only under a permissions boundary and path prefix. An ADR records it.

### M-15. Alert delivery and timing have no acceptance criteria
- **Location:** FR-17
- **Quote:** "alerts on SLO burn and on node or pod failure."
- **Problem:** No destination (email, SNS, chat), no time-to-alert, and no statement of whether the alerting stack is in-cluster (ephemeral) or managed. FR-27's "what monitoring caught" cannot be judged without a target.
- **Suggested fix:** Add: "Alerts are delivered to <channel> within 5 minutes of the condition; each alert rule is tested once by injection and the test is recorded."

### M-16. The milestone table has duplicates and omissions (separate from C-4)
- **Location:** §6
- **Quotes:** M1 "FR-1–FR-11, FR-16"; M2 "4.5" (contains FR-16); M3 "FR-8 (if not done)"; M2 done-when "RTO is baselined over 5 Drills"
- **Problem:**
  - FR-16 is in both M1 (explicitly) and M2 (through §4.5).
  - FR-8 is in M1 (inside FR-1–FR-11) and again in M3.
  - FR-21 is not listed for M2 even though M2's done-when requires the baseline.
  - No NFR is mapped, yet the billing alarm (NFR-1) and the no-static-credentials setup (NFR-2) must exist from the first Rebuild.
  - NFR-6's "before M3" deadline is not in any row.
  - The M3 stretch has no FR.
- **Suggested fix:** Give each FR exactly one owning milestone and mark carry-overs explicitly ("FR-21: started M1, done M2"). Add an NFR column or row (NFR-1/2/3/4 in M1, NFR-5 in M2, NFR-6 at the M2 exit). Give the stretch an ID (e.g. FR-30, optional).

---

## Low

### L-1. Two different cost figures
- **Location:** §1 Vision versus NFR-1
- **Quote:** "This keeps spend under $50/month" versus "actual AWS spend stays < $30/month, with a hard cap of $50/month"
- **Fix:** In the Vision, say "targets under $30/month, never above $50".

### L-2. The Persistent Footprint's monthly cost is never estimated
- **Location:** Glossary "Persistent Footprint", addendum cost table, SM-C1
- **Problem:** Rough cost: hosted zone $0.50, domain about $1–1.25 a month amortised, state bucket cents, ECR about $0.10/GB, Secrets Manager $0.40 per secret, retained snapshots at about $0.095/GB-month, KMS $1 per key, plus the SLO store (free to several dollars; Managed Grafana adds $9 per editor). That is about $3–6 a month without Managed Grafana. It is small, but it is unbudgeted, and it grows with each "move to persistent" decision.
- **Fix:** Add a Persistent Footprint cost line to the addendum and a ceiling (e.g. ≤ $8/month) to NFR-1.

### L-3. FR-28 "within one screen" is subjective
- **Location:** FR-28
- **Fix:** "All five links appear in the README before the first `##` heading after the summary (≤ 40 lines)."

### L-4. Live command output in a public repo may expose identifiers
- **Location:** FR-6, FR-26 status communications
- **Quote:** "Commands and outputs taken from the live Platform show each hop."
- **Fix:** Add "account IDs, public IPs and user emails are redacted before commit".

### L-5. "One sync cycle" is undefined
- **Location:** FR-13
- **Quote:** "within one sync cycle"
- **Problem:** Argo CD's default polling interval is about 3 minutes; with a webhook it is seconds.
- **Fix:** State a time bound (e.g. ≤ 5 minutes from merge of the revert to Healthy).

### L-6. Image registry hygiene and the pull path
- **Location:** FR-3, FR-4
- **Problem:** There is no ECR lifecycle policy, so images accumulate (a small cost). Third-party images (Argo CD, Alloy, Kyverno) and ECR API calls go through the t4g.nano NAT instance, which is also a single point of failure ("~5 min failover"). A network-fault Incident targeting NAT will also break image pulls during recovery.
- **Fix:** Add an ECR lifecycle rule (keep the last N tags). Note NAT as a known single point of failure in the network ADR.

### L-7. The kube-bench cadence is ambiguous
- **Location:** FR-23
- **Quote:** "A CIS EKS benchmark scan runs against the cluster"
- **Fix:** Say "once per milestone, or after any node AMI or version change; results committed".

### L-8. Unverified pricing and versions feed hard requirements
- **Location:** addendum cost table ("Unverified"), addendum technology table versions
- **Problem:** NFR-1's thresholds rest on prices the addendum itself marks as unverified. Pinned versions (Argo CD 3.4.x, Chaos Mesh 2.8.6 and others) will drift during the 6–8 weeks.
- **Fix:** Add a one-time story in M1: "verify prices and versions; update the addendum". Treat versions as minimums, not pins.

---

## Suggested order of fixes before epic decomposition

1. C-1 (trigger model) and C-4 (milestone redefinition). Everything in the epic structure depends on these two.
2. C-2 and H-11 (Teardown completeness and recreatability). These define the Rebuild/Teardown epic's acceptance criteria.
3. C-3 and H-7 (SLI measurement point, synthetic traffic, Session window). These define the observability epic and UJ-2.
4. H-1 to H-3 (RTO definition, snapshot mechanics, retention). These define the DR epic.
5. H-4, H-5 and H-6 (domain, bootstrap, Terraform/Argo handoff). These are architecture inputs.
6. Everything else can be fixed while stories are being written.
