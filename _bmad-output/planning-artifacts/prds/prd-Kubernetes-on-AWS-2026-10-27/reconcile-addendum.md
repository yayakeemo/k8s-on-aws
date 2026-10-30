---
title: "Reconcile: PRD vs brief addendum"
created: 2026-10-27
input: _bmad-output/planning-artifacts/briefs/brief-Kubernetes-on-AWS-2026-10-27/addendum.md
targets:
  - prd.md
  - addendum.md (PRD addendum)
---

# Reconcile: PRD vs brief addendum

**Excluded on purpose (not reported):** the Persistent Footprint override (state, DNS, Cognito, snapshots, ECR), hiring-signal research and job-posting mapping as career strategy, and the chaos-tool and SLO-store choices deferred to architecture.

**Summary:** 13 gaps. 2 high, 7 med, 4 low. Most of them are evidence the anchor posting and hiring signals call for. The PRD names the artifact but leaves out the quality that makes it count, for example an SLI that sees the user's pain or a fix that is shown to work.

## High

### G1. SLIs measured where the App cannot see the auth failure
- **Input:** "Service level indicators (SLIs) tied to user pain, with error budgets you can actually use."
- **PRD:** FR-18 (§4.6), FR-15, UJ-2.
- **Problem:** FR-15 says an unauthenticated request "never reaches App code". During an auth outage, an SLI measured in the App sees *less traffic*, not failures. UJ-2 nevertheless expects "the app's success SLI drops". The SLIs are generic request success rate and latency. They are not tied to the two user journeys or to sign-in.
- **Severity:** high. UJ-2 and Incident 2 (FR-26) depend on it.
- **Fix:** add to FR-18 that SLIs are measured at the edge (load balancer or SSO proxy) and cover the user journeys: sign-in success, "log a workout" success and "list my workouts" latency. Add an acceptance criterion that an injected auth outage (FR-25) moves at least one SLI below its SLO.

### G2. The Error Budget is not usable at Session scale
- **Input:** "error budgets you can actually use."
- **PRD:** FR-18, §3 Session.
- **Problem:** SLOs are evaluated per Session (about 2 hours) on a one-user app. Without a defined traffic source, 99% and 95% over a handful of requests mean nothing statistically, and burn-rate alerts (FR-17) can't fire reliably. Nothing requires the budget to drive a decision that is recorded.
- **Severity:** high.
- **Fix:** add a requirement for synthetic traffic (a probe or load generator exercising both features plus sign-in at a stated rate) running for the whole Session. Require that at least one recorded decision cites the remaining budget, such as a revert or deferring a fault injection, and that the decision is linked from the Postmortem or Rebuild Log.

## Medium

### G3. Chaos write-ups don't prove "what changed afterward"
- **Input:** "Chaos write-ups covering what monitoring caught, what it missed, and **what changed afterward**." Also: "Breaking things on purpose and documenting the recovery."
- **PRD:** FR-27, SM-3.
- **Problem:** FR-27 requires a merged Action Item but doesn't require evidence that the change worked. The loop never closes.
- **Fix:** add to FR-27 that after the Action Item merges, the same fault (FR-25 makes it repeatable) is injected again. The Postmortem then gets a "re-test" section showing the gap is now detected or mitigated, with alert or SLI evidence.

### G4. The service-mesh decision ADR was demoted to a stretch goal
- **Input:** Service mesh / ingress is a **Gap**. "Ingress or Gateway API controller, plus a service-mesh decision recorded as an architecture decision record (ADR)."
- **PRD:** §6 M3 stretch ("Service-mesh ADR plus a minimal mTLS demo"). FR-29 only says ADRs "include what was deliberately left out (full service mesh…)".
- **Problem:** this is inconsistent. FR-29 implies the mesh decision is recorded, but the milestone table makes the mesh ADR optional. The input treats the decision record as required evidence for a gap.
- **Fix:** make a standalone service-mesh decision ADR (adopt / defer / reject, with trade-offs) mandatory in FR-29 (5 ADRs by M2 or M3). Keep only the mTLS demo as stretch.

### G5. No requirement for Kubernetes troubleshooting evidence
- **Input:** Kubernetes operations is a **Gap**. "Operations evidence beyond deployment: upgrades, node rotation, **troubleshooting**, capacity."
- **PRD:** FR-8 covers upgrades and rotation, FR-11 covers capacity. Troubleshooting: missing (implied at most by Incidents; NFR-6 mentions "runbook" in passing).
- **Fix:** add an FR for troubleshooting runbooks (for example CrashLoopBackOff, pending pods / insufficient capacity, DNS resolution, Pod Identity/IAM denial, failed Argo CD sync). Each runbook gets diagnostic commands and output captured from the live Platform and is linked from the README.

### G6. Terraform module and state design is not a requirement
- **Input:** IaC is the **Strength**. "Terraform module and state design as the backbone of the platform."
- **PRD:** FR-1 (separate configuration only), FR-12. Missing: module structure, state layout, locking and the cross-config data flow from Footprint to Ephemeral Stack.
- **Fix:** add an acceptance criterion or ADR for Terraform state and module design: backend with locking, separate state per configuration, how the Ephemeral Stack reads Footprint outputs, and which modules are hand-written vs consumed from terraform-aws-modules.

### G7. The perpetual-diff gotcha has no acceptance criterion
- **Input:** "Final snapshot identifiers must be unique per destroy, and a naive timestamp causes a perpetual diff."
- **PRD:** FR-16 requires a "unique identifier" only. The diff issue appears only in the PRD addendum (not normative). FR-1's no-diff check covers only the Footprint.
- **Fix:** add to FR-16 (or NFR-3): "`terraform plan` immediately after a Rebuild shows no changes, including to the RDS final-snapshot identifier."

### G8. The cost inputs never become a cost model
- **Input:** "Prices are snapshots for us-east-1. Check them again before committing to a cost model." Also the Public IPv4 line ($0.005/IP-hr) and fck-nat "~5 min failover".
- **PRD:** NFR-1 has a spend target and billing alarm only. Prices sit in the PRD addendum with "re-verify" but nothing requires the re-verification or a model. Public IPv4 (fck-nat, load balancer) and persistent costs (snapshots, Q2) are not modelled.
- **Fix:** add to NFR-1 a per-Session and per-month cost model, built from prices re-verified before M1. It must count public IPv4, load balancer, NAT instance, EKS hours × expected Sessions, and the Footprint (snapshot storage). Actuals are compared monthly. This also closes Open Question 2.

### G9. Network-policy caveats lost (CNI version, no DNS-based rules)
- **Input:** "VPC CNI ≥1.21.1 supports admin/baseline policies on EC2 Linux nodes. DNS-based policies work only on Auto Mode."
- **PRD:** FR-5 states no version and no limits. The PRD addendum has the version but not the DNS limit. Auto Mode is out of scope (§8.2), so FQDN egress rules aren't available. A default-deny App namespace still has to reach Cognito, STS/Pod Identity agent, Secrets Manager and RDS.
- **Fix:** in FR-5, pin VPC CNI ≥1.21.1. State that egress allow rules are CIDR- or selector-based, not DNS-based. Add an acceptance criterion that sign-in, the DB connection and secret retrieval still work under default deny.

## Low

### G10. The packet-path write-up lost its "debugging" framing
- **Input:** "a **debugging** write-up showing a packet's path from the internet through ingress to a pod."
- **PRD:** FR-6 documents the path hop by hop but doesn't require debugging a fault along it.
- **Fix:** require FR-6 to trace one real broken-path case (for example a bad security group, a missing route or a network policy denial) and show how each hop was checked.

### G11. Tooling-status "unverified" flags have no owner or gate
- **Input:** "The 2026 status of kube-prometheus-stack is unverified." Grafana Agent and Promtail are EOL. EKS Auto Mode fee and Karpenter small-cluster value are "**unverified**".
- **PRD:** the PRD addendum lists them as unverified, and there is no action. FR-7 bans EOL for EKS only.
- **Fix:** add an NFR: no component that is EOL, or nearing EOL within the project window, is adopted. Each item marked unverified is checked in the relevant ADR before adoption.

### G12. Policy engine fixed as Kyverno without a recorded trade-off
- **Input:** "Kyverno reached CNCF Graduated… moving toward CEL. OPA/Gatekeeper is also CNCF Graduated and supports CEL and ValidatingAdmissionPolicy."
- **PRD:** FR-24 names Kyverno. No ADR covers the policy engine (FR-29 has only 4).
- **Fix:** add a short policy-engine ADR, or a section in an existing ADR: Kyverno vs Gatekeeper vs native ValidatingAdmissionPolicy.

### G13. RTO stretch target ignores the RDS restore floor
- **Input:** "Expect about 10–20 minutes of extra rebuild time for the RDS restore."
- **PRD:** NFR-5 / SM-2 stretch ≤ 30 minutes. The restore time sits only in the PRD addendum.
- **Fix:** note in NFR-5 that RDS restore (10–20 min) is on the critical path. Require the Rebuild Log to record the RDS restore time separately so RTO improvements can be attributed.

## Note (not an input gap, but found while checking)
- FR-22 relies on "automated backups" of an RDS instance that is destroyed on every Teardown. By default, deleting the instance deletes its automated backups. Architecture should confirm that backups are retained (`delete_automated_backups = false`), or that the drill runs within a single Session.
