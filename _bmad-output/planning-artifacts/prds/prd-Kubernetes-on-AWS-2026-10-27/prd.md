---
title: "PRD: Kubernetes-on-AWS"
status: final
created: 2026-10-27
updated: 2026-10-28
inputs:
  - _bmad-output/planning-artifacts/briefs/brief-Kubernetes-on-AWS-2026-10-27/brief.md
  - _bmad-output/planning-artifacts/briefs/brief-Kubernetes-on-AWS-2026-10-27/addendum.md
---

# PRD: Kubernetes-on-AWS

## 0. Document Purpose

This PRD defines what the Kubernetes-on-AWS platform must do. It is written for the builder (Yahia) and the AI agents that implement it, and it is kept clean enough to link from the portfolio repo. It builds on the final product brief and does not repeat the career reasoning behind it.

**How to read it:**
- **Structure:** features are grouped in §4, each with globally numbered FRs. FR IDs are stable, so FRs added during review are appended (FR-30 onward) and sit with the feature they belong to. Cross-cutting NFRs are in §5 and milestones in §6.
- **Vocabulary:** the terms in §3 are used exactly as defined.
- **Named technologies:** this is a learning platform, so some AWS and CNCF tools are themselves the scope (EKS, Terraform, Argo CD, Cognito, RDS). Those tools appear in the FRs.
- **Addendum:** versions, costs, mechanisms and rejected alternatives are in `addendum.md`.
- **Assumptions:** inferences are tagged `[ASSUMPTION]` inline and indexed in §11.

## 1. Vision

Kubernetes-on-AWS is a production-style EKS platform, built entirely in Terraform, that its Operator runs, breaks on purpose, and recovers. It hosts a small authenticated fitness app. Every change reaches the platform through a pipeline, and every failure leaves a written record.

The platform is **ephemeral by design**. It is torn down at the end of every working session and rebuilt from code at the start of the next one. Each Rebuild is a timed disaster-recovery Drill. This keeps spend under $50/month, and it produces a growing record of measured RTO and RPO.

What sets this apart from the many EKS reference repos is that **it focuses on operations, not deployment**. The repo shows how the platform is run:
- decisions with their trade-offs
- Incidents led from start to finish
- Postmortems whose Action Items were shipped as code and then re-tested
- a Rebuild time that gets measurably shorter

## 2. Target User

### 2.1 Jobs To Be Done
- **Operator (Yahia):** gain real, defensible skill in Kubernetes operations, AWS networking, and incident leadership. Every claim must be explainable under questioning, without notes.
- **Operator:** finish every 2-hour session with something visible (a commit, doc, dashboard screenshot or Rebuild Log line) so the project never stalls in abstraction.
- **Reviewer (interviewer / hiring manager):** in 2–5 minutes of scanning the repo, see evidence of operations: trade-offs, failures and what changed afterward.
- **App User:** log a workout and see their workouts, behind single sign-on.

### 2.2 Non-Users (v1)
There are no real customers and no other operators. §7 lists every scope boundary.

### 2.3 Key User Journeys
- **UJ-1. Yahia starts a weekend session from nothing.** The previous Session ended with a full Teardown, so only the Persistent Footprint remains. He triggers the Rebuild pipeline. Terraform brings back the network, cluster, and database (restored from the latest snapshot). Argo CD then syncs everything in the cluster. About 30–45 minutes later the Synthetic Probe signs in through Cognito and succeeds, and the pipeline records the RTO and RPO in the Rebuild Log. Yahia signs in and sees the workouts he logged last week. At the end of the Session he triggers Teardown. It takes a final snapshot, and the post-Teardown check confirms that nothing billable is left behind.
  **Edge case:** a fresh account has no snapshot yet, so the first Rebuild creates an empty database instead of failing.
- **UJ-2. Yahia leads an injected auth outage.** He merges a change that breaks the sign-in path. The Synthetic Probe starts failing at the edge, the sign-in SLI drops, and a burn-rate alert fires. He declares an Incident, takes the commander role and keeps a timestamped timeline. He works out the cause and restores service with a Git revert. Afterward he writes a blameless Postmortem, records what monitoring caught and what it missed, ships the Action Item as a PR, and re-runs the fault to show that the fix holds.
- **UJ-3. A reviewer scans the repo before an interview.** From the README, the reviewer reaches the architecture diagram, the ADR index, the Rebuild Log (with RTO trending down) and three Postmortems, each linked to the PR that shipped its fix. In the interview they ask, "What did your monitoring miss?", and the answer is already written down.

## 3. Glossary

- **Operator:** the one person who runs the Platform (Yahia).
- **Platform:** everything Terraform and Argo CD create inside the AWS account. The Platform is made of the Persistent Footprint plus the Ephemeral Stack.
- **Bootstrap:** the one-time creation of the Persistent Footprint in an empty AWS account. It runs with short-lived human admin credentials. Bootstrap is the only step that is not run by the pipeline.
- **Persistent Footprint:** the resources that survive Teardown:
  - the Terraform state backend
  - the registered domain and its DNS hosted zone (but not the records a Rebuild creates)
  - the CI's OIDC trust and IAM roles
  - the billing alarm
  - the Cognito user pool
  - the container image registry
  - persistent secrets
  - RDS snapshots
  - the SLO history store
- **Ephemeral Stack:** everything created by a Rebuild and destroyed by a Teardown: VPC, EKS cluster, node group, RDS instance, in-cluster workloads, and the resources that in-cluster controllers create (load balancers, volumes, DNS records).
- **Session:** the period during which the Ephemeral Stack exists. A Session begins with a Rebuild and ends with a Teardown. SLOs are evaluated per Session.
- **Rebuild:** an Operator-triggered pipeline run that creates the Ephemeral Stack from code. A Rebuild is complete when:
  - in M1, the cluster is healthy and the database is restored
  - from M2 onward, the first authenticated Synthetic Probe succeeds
- **Teardown:** an Operator-triggered pipeline run that takes a final RDS snapshot and destroys the Ephemeral Stack, leaving no billable Ephemeral Stack resource behind.
- **Drill:** one Rebuild, timed and recorded. Every Rebuild is a Drill.
- **Rebuild Log:** an append-only record of each Drill. Each entry holds:
  - the date
  - the RTO and RPO
  - any manual steps
  - anything that failed
  - changes since the last Drill
- **RTO:** the wall-clock time from the start of the Rebuild pipeline run to the Rebuild being complete:
  - **Platform RTO** is measured in M1, using M1's completion point.
  - **Service RTO** is measured from M2 onward, using the Synthetic Probe completion point.
- **RPO:** the data lost in a recovery, measured as the time between the latest usable snapshot or backup and the failure or Teardown.
- **App:** the fitness application. It has two features, "log a workout" and "list my workouts", and keeps its data in RDS.
- **Synthetic Probe:** an automated client that signs in through Cognito and calls both App features at a fixed interval throughout a Session.
- **SLI / SLO / Error Budget:**
  - an SLI is a user-facing signal measured at the edge (sign-in success, request success rate, request latency)
  - an SLO is the target for an SLI
  - the Error Budget is the allowed shortfall below the SLO
- **Incident:** an unplanned (or injected) degradation of the App that breaches or threatens an SLO and is run with a commander and a timeline.
- **Postmortem:** a blameless written review of an Incident: timeline, cause, what monitoring caught and missed, Action Items, and a re-test result.
- **Action Item:** a change produced by a Postmortem. It is shipped as a merged PR.
- **ADR:** Architecture Decision Record, a short document recording one decision, the options considered and the trade-off.

## 4. Features

### 4.1 Bootstrap and Persistent Footprint
**Description:** a small, long-lived base that makes the Ephemeral Stack cheap to destroy and gives the pipeline what it needs to run.
- It is created once, by Bootstrap. After that it changes only through a PR.
- The Operator does not own a domain yet, so registering one is part of this feature.

Realizes UJ-1.

#### FR-1: Bootstrap creates the Persistent Footprint from code
The Operator can create the entire Persistent Footprint by running Bootstrap once against an empty AWS account. Bootstrap uses a Terraform configuration kept separate from the Ephemeral Stack.
- Bootstrap uses short-lived admin credentials. It never creates or stores long-lived access keys.
- After Bootstrap, the pipeline can run Rebuild and Teardown with no further human credentials.
- Running Teardown never destroys or changes a Persistent Footprint resource.
- Re-applying the Persistent Footprint configuration on an unchanged account produces no diff.
- The Bootstrap runbook lists its manual steps. The only manual steps allowed are:
  - domain registration and its contact-email verification
  - confirming the budget and alert email subscriptions
  - the one-time migration of Bootstrap's local state into the state bucket

  (Amended 2026-10-28 by architecture AD-24.)

#### FR-2: Domain and DNS
The Operator registers a domain, and the Platform uses a hosted zone for it to give the App a public HTTPS hostname.
- The App is reachable at a stable hostname under the registered domain after every Rebuild, with no manual DNS edits.
- Teardown removes the DNS records the Rebuild created and leaves the hosted zone itself in place.
- TLS certificates are issued and validated automatically. [ASSUMPTION: certificates are created during Rebuild, not kept in the Persistent Footprint; the architecture step decides.]

#### FR-3: Identity and image persistence
The Cognito user pool, the container image registry and persistent secrets survive Teardown.
- An App User created before a Teardown can sign in after the next Rebuild.
- A Rebuild does not need to rebuild or push container images.

### 4.2 Network
**Description:** a multi-AZ VPC designed by hand, so the Operator can explain every route. Networking cost is kept low on purpose (FR-4). In-cluster traffic is restricted by network policies. Realizes UJ-1 and UJ-3.

#### FR-4: Hand-designed multi-AZ VPC
The Rebuild creates a VPC across at least two AZs in us-east-1, with public and private subnets, a cost-optimized NAT path, and free gateway endpoints for S3 and DynamoDB.
- Nodes and RDS run only in private subnets.
- Traffic from private subnets to S3 does not pass through NAT.
- An ADR records the network design (CIDR plan, subnet layout, NAT choice).

#### FR-5: Kubernetes network policies
Network policies are enforced in the cluster, and the App namespace defaults to deny.
- A pod without an explicit allow rule cannot reach the App pods or the RDS endpoint.

#### FR-6: Packet-path write-up
The Operator documents the path of a request from the internet, through DNS, the load balancer and Gateway API ingress, to the App pod. Commands and outputs taken from the live Platform show each hop.

### 4.3 Cluster and Identity
**Description:** an EKS cluster with least-privilege identity at every layer: humans, CI, pods and the database. It has no static credentials. Realizes UJ-1.

#### FR-7: EKS cluster on standard support
The Rebuild creates an EKS cluster on a version in standard support, with a small Spot managed node group.
- The pinned version is in standard support on the day of each Rebuild. A version entering extended support fails a pre-flight check.

#### FR-8: Upgrades and node rotation
The Operator performs at least one EKS minor version upgrade and one node rotation, and documents each one: plan, steps, observed impact on the App's SLIs.

#### FR-9: Workload and human identity
- Pods get AWS permissions through EKS Pod Identity. An ADR compares Pod Identity with IRSA.
- Humans get cluster access through EKS access entries. There is no shared kubeconfig credential.
- CI reaches AWS through GitHub Actions OIDC federation, using the roles created by Bootstrap. No long-lived AWS keys exist anywhere.

#### FR-10: Secrets
- The App authenticates to RDS with IAM database authentication. No static database password exists.
- Any remaining secret, such as the SSO proxy's cookie secret, is a persistent secret in AWS Secrets Manager and is never committed to Git.
- No Rebuild fails because of how a secret was deleted or named in an earlier Session.

#### FR-11: Capacity evidence
Every workload declares CPU and memory requests and limits. The Operator documents how the node group is sized against those requests.

#### FR-33: Troubleshooting evidence
The Operator writes up at least two real troubleshooting cases from the live Platform, such as a pod that would not schedule or a failing health check. Each write-up covers the symptom, the commands used, what was found and the fix.

### 4.4 Delivery Pipeline
**Description:** every change goes through Git. Terraform changes go through PRs, and Argo CD reconciles everything in the cluster. Rollback is a revert. Injected faults use the same pipeline as real changes. Realizes UJ-1 and UJ-2.

#### FR-12: Terraform through pull requests
A PR to the infrastructure code triggers a plan whose output is visible on the PR. Pipeline jobs authenticate to AWS only through OIDC (FR-9).
- A merged change to the Persistent Footprint is applied automatically. The exception is the Bootstrap layer (state backend, CI trust roles and budgets): CI only plans changes to it, and the Operator applies them. (Amended 2026-10-28 by architecture AD-18.)
- A merged change to the Ephemeral Stack is applied only while a Session is active.
- Outside a Session, a merge runs a plan only and never creates billable resources.

#### FR-13: GitOps for in-cluster state
Argo CD owns every in-cluster resource, App included, and syncs it from Git after a Rebuild with no manual `kubectl apply`.
- Reverting a commit restores the previous App version within one sync cycle.

#### FR-14: Gateway API ingress
Public traffic reaches the App through a Gateway API implementation. An ADR records the ingress choice.

### 4.5 App and Data
**Description:** a minimal Python app that recreates the Operator's CGI OIDC SSO project the cloud-native way. It carries real data so that data recovery can be tested in Drills. The App has a hard cap of 8–10 hours of build effort. Realizes UJ-1.

#### FR-15: Authenticated App
Only App Users authenticated through Cognito SSO at the edge can log a workout or list their own workouts.
- An unauthenticated request is redirected to sign-in and never reaches App code.
- An App User sees only their own workouts.

#### FR-16: Database restored on every Rebuild
- Teardown takes a final RDS snapshot with a unique identifier.
- Rebuild restores the RDS instance from the most recent snapshot.
- When no snapshot exists, such as on the first Rebuild, Rebuild creates an empty database and runs schema setup instead of failing.
- Workouts logged before a Teardown appear after the next Rebuild (RPO = 0 for a planned Teardown).
- Only the 5 most recent final snapshots are kept. Older ones are deleted automatically.
- Applying a change during a Session never replaces the live RDS instance.

**Out of Scope:** see §7. Ideas for a third feature or frontend polish are recorded on a "someday" list in the repo and not built.

### 4.6 Observability and SLOs
**Description:** the Operator can see when App Users are affected before they complain. SLIs are measured where users feel the pain, at the edge and including sign-in. The Ephemeral Stack lives only for a Session, so SLO history is kept outside it. Realizes UJ-2.

#### FR-17: Metrics, logs and alerts
The Platform collects metrics and logs from the edge, the App and the cluster. It alerts on SLO burn rate and on node or pod failure.

#### FR-32: Synthetic Probe
The Synthetic Probe runs throughout every Session from M2 onward. It generates enough authenticated traffic that each Session's Error Budget allows at least 5 failed requests.
- When sign-in is broken, the Synthetic Probe fails and the sign-in SLI drops, even though App code never runs.

#### FR-18: Per-Session SLOs with Error Budget
The App has three SLOs, all measured at the edge and evaluated per Session:
- **Sign-in:** ≥ 99% of sign-in attempts succeed.
- **Availability:** ≥ 99% of requests succeed.
- **Latency:** ≥ 95% of requests complete in < 500 ms.

When the Error Budget is exhausted, the change that exhausted it is reverted rather than patched forward.
- A dashboard shows current SLI values, remaining Error Budget, and burn rate.
- At least one ship-or-revert decision recorded in the repo cites the Error Budget.

#### FR-19: SLO history survives Teardown
SLI and SLO results from past Sessions stay queryable after Teardown, so trends span Sessions. The store is part of the Persistent Footprint, and the architecture step chooses it.

### 4.7 Session Lifecycle and DR Drills
**Description:** recovery is practiced every Session, not described in theory. The Operator starts and ends each Session on purpose, and Teardown leaves nothing billable behind. Realizes UJ-1.

#### FR-30: Operator-triggered Rebuild and Teardown
The Operator starts a Rebuild and a Teardown as separate, manually triggered pipeline runs. Neither one runs automatically on a merge.

#### FR-20: Zero-touch Rebuild
Once Bootstrap has run, a Rebuild takes the account from only the Persistent Footprint to a complete Rebuild, with zero manual steps.
- Any manual step in Drills 1–5 is recorded in the Rebuild Log as a defect and removed in code.
- From the end of M2, every Drill has zero manual steps.

#### FR-31: Complete Teardown
Teardown leaves no billable Ephemeral Stack resource behind, including the load balancers, volumes and DNS records that in-cluster controllers create.
- A check run after Teardown lists the account's billable resources and finds only Persistent Footprint resources. It fails loudly otherwise.

#### FR-21: Measured and falling RTO
- Every Drill appends a Rebuild Log entry (§3). The pipeline records the RTO, not a stopwatch.
- RTO is baselined over the first 5 Drills.
- A Drill whose RTO exceeds 45 minutes is a failed Drill and gets a cause recorded.
- At the end of M2, the median RTO of the last 5 Drills is lower than the baseline median. Each improvement is logged with its cause.
- Platform RTO and Service RTO are logged separately, so the two series can be compared.

#### FR-22: Unplanned data-loss exercise
At least once, the Operator recovers the database from automated backups without a fresh final snapshot, and records the resulting RPO.
- Automated backups must survive the destruction of the RDS instance for this exercise to be possible (see addendum).

### 4.8 Hardening
**Description:** the Operator's CIS hardening experience, applied to EKS. Some controls are added in response to Incidents rather than up front. This feature realizes no UJ directly. It supports NFR-2.

#### FR-23: Baseline hardening
- A CIS EKS benchmark scan runs against the cluster, and its results and any accepted exceptions are documented.
- Pod Security Standards are enforced on App namespaces.

#### FR-24: Policy as code from Postmortems
Admission policies (Kyverno) are introduced as Postmortem Action Items. Each policy links to the Postmortem that motivated it.

### 4.9 Incident Drills
**Description:** the project's strongest evidence. Failures are injected on the real EKS Platform and run as real Incidents. Wherever possible, a fault arrives through Git, as most real outages do, so that recovery by revert is realistic. Realizes UJ-2.

#### FR-25: Repeatable fault injection
The Operator can inject each fault type repeatably:
- bad deploy
- auth outage (identity provider or SSO proxy path broken)
- node failure
- network fault

**How faults are injected:**
- Bad-deploy, auth and network faults are injected as merged Git changes.
- A node failure may be injected by a scripted command kept in the repo.
- The architecture step chooses the injection tool.

#### FR-26: Incidents run end to end
Exactly three committed Incidents are run, one for each scenario below:
1. a bad deploy
2. an auth outage
3. a node or network failure

Each has a declared commander, a timestamped timeline, and status communications written as they would be sent.

#### FR-27: Postmortems with shipped, re-tested Action Items
Each Incident has a blameless Postmortem that records:
- what monitoring caught **and what it missed**
- at least one Action Item merged as a PR
- a re-test: the same fault is injected again after the Action Item ships, and the result is recorded

### 4.10 Evidence and Documentation
**Description:** the repo is the portfolio. It must read clearly to a reviewer in 2–5 minutes. Realizes UJ-3.

#### FR-28: Scannable README
The README links, within one screen, to:
- the architecture diagram
- the ADR index
- the Rebuild Log
- the Postmortems
- the packet-path write-up
- the troubleshooting write-ups

#### FR-29: ADRs
At least 4 ADRs exist by the end of M2: network design, Pod Identity versus IRSA, ingress, and RDS. Together they cover what was deliberately left out (full service mesh, multi-environment promotion).

## 5. Cross-Cutting NFRs

- **NFR-1 Cost:** actual AWS spend stays under $30/month, with a hard cap of $50/month.
  - The billing alarm alerts before the cap.
  - Teardown at the end of each Session is the default. An Ephemeral Stack left running overnight counts as a cost defect.
  - The Persistent Footprint's own monthly cost is tracked in the cost model.
- **NFR-2 Security:**
  - no long-lived credentials anywhere (AWS keys, database passwords, kubeconfig tokens), and no credentials in Git
  - Bootstrap uses short-lived credentials only
  - least-privilege IAM for each identity
  - private subnets for nodes and data
- **NFR-3 Reproducibility:** all Platform state is defined in Git. Any drift found during a Drill is fixed in code, not by hand.
- **NFR-4 Region and tenancy:** single AWS account, single environment, us-east-1.
- **NFR-5 Rebuild duration:** RTO of 45 minutes or less per Drill, with a falling median, as FR-21 defines. Stretch: Service RTO ≤ 30 minutes.
- **NFR-6 Explainability:** every component in the Platform is covered by an ADR, a runbook or a write-up that the Operator can explain without notes. A component that can't be explained is removed or documented before M3.

## 6. Milestones

The timeline is 6–8 weeks at about 2 hours a day, roughly 12 effective hours a week and 75–90 usable hours in total. Rebuild-heavy EKS work goes in longer weekend blocks, and day-to-day Kubernetes learning happens on a local `kind` cluster.

| Milestone | FRs | Done when |
|---|---|---|
| **M1: Foundation** | FR-1–FR-5, FR-7, FR-9, FR-10, FR-11, FR-16, FR-20, FR-30, FR-31; FR-21 with Platform RTO | The Platform rebuilds and tears down from the pipeline, Platform RTO is being logged, and the network ADR and Pod Identity ADR are written. |
| **M2: Delivery and visibility** | FR-6, FR-8, FR-12–FR-15, FR-17–FR-19, FR-23, FR-28, FR-29, FR-32, FR-33; FR-21 switches to Service RTO | SLOs are live and fed by the Synthetic Probe. Every change goes through Git. RTO meets FR-21. Every Drill has zero manual steps. 4 ADRs are done. |
| **M3: Incidents** | FR-22, FR-24–FR-27 | 3 Incidents and Postmortems are complete, with Action Items shipped and re-tested. |
| **M3 stretch** | — | Service-mesh ADR plus a minimal mTLS demo. |

**De-scope order:** if the schedule slips, cut or defer in this order:
1. the M3 stretch
2. FR-33, down to one case
3. FR-8, moved to M3

Incident work (FR-25–FR-27) is never cut.

## 7. Non-Goals and Out of Scope

**Product non-goals**
- Not a multi-team or multi-tenant platform. There are no real customers, no other operators, and no environments to promote between.
- Not an app product. App polish is a scope risk, and the Incidents are the differentiator. The App has no frontend beyond the two features, and no third feature.
- Not a tool bake-off. There are no CI tool comparisons and no multi-service image pipelines.
- Not always-on. There is no uptime commitment outside a Session.

**Deferred or excluded technology**
- A full service mesh rollout. Only the M3 stretch (ADR plus mTLS demo) is in scope.
- Multiple environments, regions or AWS accounts. AWS Organizations is deferred to a later phase.
- EKS Auto Mode and Fargate.
- Karpenter. It is out of scope, to be revisited only after M3 is complete.

## 8. Success Metrics

**Primary**
- **SM-1: Zero-touch Rebuild.** Every Drill from the end of M2 has zero manual steps. Validates FR-20, FR-30, and FR-13.
- **SM-2: RTO trend.** The FR-21 and NFR-5 targets are met. Validates FR-21.
- **SM-3: Incidents closed.** 3 of 3 committed Incidents have a Postmortem, at least one merged Action Item, and a passing re-test. Validates FR-26 and FR-27.
- **SM-4: The real test.** The Operator can answer "tell me about a time you…" questions on Kubernetes operations, networking, and incident leadership using only this project, without notes.

**Secondary**
- **SM-5: Cost.** Validates NFR-1 and FR-31.
- **SM-6: ADR coverage.** Validates FR-29.
- **SM-7: Planned-Teardown RPO.** Validates FR-16.

**Counter-metrics (do not optimize)**
- **SM-C1: Persistent Footprint growth.** Do not cut RTO by moving more resources into the Persistent Footprint. Counterbalances SM-2.
- **SM-C2: Incident count.** Do not pad the record with trivial or staged-to-pass Incidents. Three real ones beat ten shallow ones. Counterbalances SM-3.
- **SM-C3: Monitoring that "caught everything".** A Postmortem claiming monitoring missed nothing is a warning sign, not a win. Counterbalances FR-27.
- **SM-C4: Rehearsed answers.** Do not memorize answers to pass SM-4. If an answer can't be traced to a specific commit, Drill or Postmortem, the gap is in the work, not the delivery. Counterbalances SM-4.

## 9. Risks

| Risk | Mitigation |
|---|---|
| **Stalling**, as the Operator's last Kubernetes course did, because the work becomes abstract. | Problem-first learning: each concept is learned when the Platform needs it. Session cadence follows §2.1 and §6. |
| **Scope over budget.** Requirements added during review (Bootstrap, the Synthetic Probe, the post-Teardown check, troubleshooting write-ups, and re-tests) may together push the work past 75–90 hours and crowd out the Incidents. | The App stays capped at 8–10 hours. Follow the de-scope order in §6. |
| **Cost overrun** from a forgotten or incomplete Teardown. | FR-31's post-Teardown check, the billing alarm (NFR-1), and snapshot retention (FR-16). |
| **Rebuild fragility** (snapshot restore, the first-run path, secret reuse) eating Session time. | These are named as acceptance criteria in FR-10 and FR-16, and the addendum lists the known pitfalls for the architecture step. |

## 10. Open Questions

1. Which domain name to use? This needs an answer before M1's DNS work. [ASSUMPTION: the domain is registered through Route 53, for a single-vendor Terraform path. The architecture step can override this.]
2. Which store holds SLO history (FR-19)? This is deferred to the architecture step.
3. Which fault-injection tool (FR-25)? This is deferred to the architecture step.

## 11. Assumptions Index

- **§4.1 FR-2:** TLS certificates are created during Rebuild, not kept in the Persistent Footprint.
- **§10 Q1:** the domain is registered through Route 53.
