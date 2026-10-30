---
title: "Reconciliation: Brief -> PRD (Kubernetes-on-AWS)"
created: 2026-10-27
input: _bmad-output/planning-artifacts/briefs/brief-Kubernetes-on-AWS-2026-10-27/brief.md
targets:
  - prd.md
  - addendum.md
---

# Reconciliation: Brief -> PRD

These changes were intentional, so they are not reported here: job-search strategy (Accenture targeting, "apply to 3 roles", gap analysis), the Persistent Footprint contents, the fixed set of 3 incidents, deferring the chaos tool and the SLO store to architecture, and Karpenter being out of scope.

Findings are ordered by severity.

| # | Gap | Severity | PRD location |
|---|---|---|---|
| G1 | The main risk (stalling) and its problem-first-learning mitigation are missing | high | missing (only partly covered in §2.1) |
| G2 | The RTO "then reduced" goal is weakened to a 45-min ceiling plus a stretch goal | high | FR-21, NFR-5, SM-2 |
| G3 | The zero-manual-steps rebuild criterion is weakened: no gate at M2, a 5-Drill grace period, and the empty-account path is never tested | high | FR-20, SM-1, §6 |
| G4 | "Failures come in through the same pipeline" is weakened by "or a documented command" | med | FR-25, §4.4 |
| G5 | The milestone mapping makes the M1 RTO claim impossible to measure | med | §6 M1 row, §3 RTO |
| G6 | The PRD adds new work without checking it against the "adding pillars" scope risk | med | FR-2, FR-6, FR-11, FR-22, FR-25, NFR-6 |
| G7 | "Make sure it doesn't recur" has no verification step | med | FR-26, FR-27 |
| G8 | kind as the daily learning environment has no requirement, and the Vision implies an EKS rebuild every Session | low | §1, §3 Session, §6 |
| G9 | The time budget detail (12 effective h/week, 7 days/week) was dropped | low | §6 |
| G10 | Troubleshooting, part of the brief's definition of Kubernetes operations, has no evidence requirement | low | missing |
| G11 | Vision next steps (certifications, mesh "once there's a reason", ownership aim) were dropped | low | missing |

---

## G1. The main risk and problem-first learning are missing (high)

**Input (Constraints & Risks):**
> "**Main risk: stalling the way my last Kubernetes course did,** because the work became abstract. The mitigation is problem-first learning:
> - I learn each Kubernetes concept when the platform needs it.
> - Every session ends with something visible, such as a commit, a doc, a dashboard screenshot, or a line in the rebuild log."

> "M1 includes about 10–15 hours of Kubernetes foundations, which I'll learn by building platform pieces."

**PRD location:** missing. The PRD has no Risks section. §2.1 JTBD keeps the "something visible" habit ("so the project never stalls in abstraction"). Problem-first learning ("learn each concept when the platform needs it") is not in the PRD or the addendum. The addendum's "Effort calibration" keeps the 10–15 h figure but drops "learned by building platform pieces". The brief calls this the main risk, yet nothing tracks or checks the visible-output habit. The Rebuild Log records Drills only, so a kind-only session produces no log line at all.

**Suggested fix:**
- Add a §Risks section that names stalling as the primary risk, with both mitigations quoted.
- Add an NFR or process rule: "Every Session ends with a visible artefact (a commit, doc, dashboard screenshot or Rebuild Log line). Sessions are recorded in a session log, kind sessions included." Optionally add a counter-metric: "N consecutive Sessions with no artefact = stall signal".
- Add a working principle: "Kubernetes concepts are learned when a platform FR needs them. There is no standalone course track." In §6 or the addendum, note that the 10–15 h of M1 foundations happens through building FR-4 to FR-11.

## G2. The RTO "then reduced" goal is weakened (high)

**Input (Success Criteria #2):**
> "Rebuild RTO is baselined over the first **5 drills** and then reduced, with each improvement and its cause logged."

**PRD location:** FR-21, NFR-5, SM-2. The PRD requires a baseline, a 45-minute ceiling and a log of improvements. The actual reduction is only a stretch goal (≤ 30 min). A baseline of 40 min that stays at 44 min passes SM-2. This contradicts the PRD's own Vision ("a rebuild time that gets measurably shorter") and UJ-3 ("RTO trending down").

**Suggested fix:** in SM-2/FR-21, require that the median RTO of the last N Drills before the end of M2 (or M3) is below the 5-Drill baseline median, with at least one logged improvement. Keep ≤ 45 min as the ceiling and ≤ 30 min as the stretch goal.

## G3. The zero-manual-steps rebuild criterion is weakened (high)

**Input (Success Criteria #1, "By the end of M2"):**
> "One `terraform apply` plus a GitOps sync rebuilds the platform from an empty AWS account to a working, authenticated fitness app, with **no manual steps**."

**PRD location:** FR-20, SM-1, §6.
- FR-20 redefines the starting point as "Persistent Footprint only". The empty-account path becomes two Terraform configurations plus manual domain registration. This is tagged [ASSUMPTION], which is acceptable, but no requirement ever **exercises** the empty-account path. As written, it could go untested.
- SM-1 applies only to "Drills after Drill 5", so the 5 baseline Drills may include manual steps. That makes the baseline RTO (G2) inconsistent with later Drills.
- The brief puts this and the other criteria at the end of M2. The PRD's SM-1, SM-2 and SM-5 have no milestone. The §6 M2 "Done when" row lists neither zero-touch Rebuild nor the cost target.

**Suggested fix:**
- Add an acceptance criterion: "Before the end of M2, at least one empty-account rebuild (Persistent Footprint apply plus Rebuild) is run and recorded in the Rebuild Log. Its only manual step is domain registration."
- Make SM-1 "100% of Drills from the end of M2 onward". Flag any baseline Drill that had manual steps in the Rebuild Log.
- Add "zero-touch Rebuild" and "spend < $30" to the M2 "Done when" row.

## G4. "Failures come in through the same pipeline" is weakened (med)

**Input (What Makes This Different):**
> "**Incidents caused by real change.** Failures come in through the same pipeline that real outages do."

**PRD location:** FR-25 and the §4.4 description. §4.4 keeps the idea, but FR-25 allows injection "from code **or a documented command**". A command bypasses the pipeline. UJ-2's recovery ("restores service with a Git revert") only works if the auth fault arrived through Git. Note that the injection *tool* is deferred, and that deferral is fine. This gap is about the injection *path*.

**Suggested fix:** add to FR-25: "Change-induced faults (bad deploy, auth outage, network policy fault) are introduced as a merged PR and flow through FR-12/FR-13. Only infrastructure faults such as node loss may use an out-of-band tool or command." Add an FR-26 criterion that each Postmortem links the PR or commit that introduced the fault.

## G5. The milestone mapping makes the M1 RTO claim impossible to measure (med)

**Input (Solution table, M1):**
> "I designed the network and identity model, and I've measured my platform's rebuild time (RTO)."

**PRD location:** §6 and §3. M1 includes FR-16, FR-20 and "FR-21 baseline started". But §3 defines RTO as lasting until "the App serving authenticated requests", and the App (FR-15), GitOps (FR-13) and ingress (FR-14) are all in M2. As a result, no Drill in M1 can produce an RTO under the PRD's own definition.

**Suggested fix:** do one of the following:
- define an interim M1 RTO end point (for example, cluster Ready and the RDS instance restored) and record it as a separate Rebuild Log column
- move a minimal FR-13/FR-15 slice into M1

Whichever you choose, state which Drills count toward the 5-Drill baseline.

## G6. New work is not checked against the "adding pillars" scope risk (med)

**Input (Constraints & Risks):**
> "**Scope risk:** polishing the app or adding pillars crowds out the incidents, and the incidents are the strongest differentiator. The mitigation is the 'out' list above plus a cap of 8–10 hours on app code."

> "roughly 75–90 usable hours in total"

**PRD location:** §7 keeps the app-polish half. The 8–10 h cap is in §4.5. However, the PRD adds work that is not in brief.md:
- domain registration (FR-2)
- a packet-path write-up (FR-6)
- capacity evidence (FR-11)
- an unplanned data-loss drill (FR-22)
- an explainability NFR (NFR-6)
- status communications (FR-26)
- a billing alarm and an EKS-version pre-flight check
- 4 fault types for 3 incidents (FR-25)

Some of these may come from the brief's addendum. Even so, the PRD never checks the total against the 75–90 h budget or protects M3 incident time.

**Suggested fix:**
- Add a rough hours-per-milestone allocation in §6 or the addendum, with M3 time reserved for incidents.
- Mark the additions that are not essential (FR-6, FR-11, FR-22, the 4th fault type) as "cut first if M3 is at risk".
- Restate the scope risk in the new Risks section (see G1).

## G7. "Make sure it doesn't recur" has no verification step (med)

**Input (The Problem):**
> "**Incident leadership.** This means taking command of an incident, communicating during it, and making sure it doesn't recur, rather than only fixing it."

**PRD location:** FR-26 and FR-27. Commander, timeline and communications are covered. Preventing recurrence is reduced to "at least one Action Item merged as a PR". Nothing checks that the fix actually prevents the failure.

**Suggested fix:** add to FR-27: "After the Action Item merges, the same fault is re-injected, and the Postmortem records whether the fix prevented or detected it."

## G8. kind as the daily learning environment has no requirement (low)

**Input (The Solution):**
> "Day-to-day Kubernetes learning happens on a local kind (Kubernetes in Docker) cluster. The real EKS cluster comes up for AWS integration work and for recorded incident runs."

**PRD location:** §6 mentions "a local cluster" in passing, and the addendum lists kind. However, §1 Vision says the platform is "torn down at the end of every working session and rebuilt … at the start of the next one". That implies an EKS rebuild every day, which conflicts with the brief's split and the cost assumptions.

**Suggested fix:** in §1/§3, say that EKS Sessions happen for AWS integration and incident runs only, and that daily work uses kind. Optionally add an FR that in-cluster manifests run on kind with only small overlays, so learning carries over.

## G9. Time budget detail was dropped (low)

**Input:**
> "**Time: 2 hours/day, 7 days/week.** I'm planning on about 12 effective hours a week…"

**PRD location:** §6 keeps "about 2 hours a day" and "75–90 usable hours". It drops "7 days/week" and "~12 effective hours a week", which is the planning rate the 75–90 h figure comes from.

**Suggested fix:** add "7 days/week, about 12 effective hours/week" to §6 or the addendum's Effort calibration.

## G10. Troubleshooting has no evidence requirement (low)

**Input:**
> "**Kubernetes operations.** This means running clusters day to day, not just deploying one. It covers upgrades, node rotation, and troubleshooting."

**PRD location:** missing. Upgrades and node rotation are covered by FR-8. Troubleshooting appears only implicitly, inside the Incidents.

**Suggested fix:** state in FR-26 or FR-28 that the Postmortems and runbooks are the troubleshooting evidence, or add a short troubleshooting runbook requirement under NFR-6.

## G11. Vision next steps were dropped (low)

**Input (Vision):**
> "a real service mesh once there's a reason for one"; "the CKA and AWS Solutions Architect certifications, using the platform as my study lab"; "This project is my first rehearsal of that ownership."

**PRD location:** §8.2 keeps AWS Organizations and Karpenter as deferred. The CKA/SA study-lab use, the condition on a real service mesh, and the long-term ownership framing are all missing. §0 explains that career reasoning is left out on purpose, so this is low.

**Suggested fix:** add a short "Later phases" list to §1 or §8.2: multi-account, a real mesh once there is a reason for one, and use as a CKA/SA study lab.

---

## Checked and consistent (no action)

- $50 cap / < $30 target ($20 buffer), standard support vs 6× extended support, 6–8 weeks, 75–90 h, 30–45 min rebuild, 10–15 h foundations (addendum), 8–10 h app cap, 5 Drills, ≥ 4 ADRs (all four topics), 3 incidents with the brief's scenarios, 2–5 min reviewer scan.
- The "Operations, not deployment" positioning (§1), the reviewer's needs (§2.1, UJ-3), the "real test" (SM-4), "what monitoring missed" (FR-27, SM-C3), and ADRs covering what was left out (FR-29).
- All in-scope items (network, cluster, identity, delivery, visibility, hardening, workload, mesh stretch) and the out-of-scope list.
