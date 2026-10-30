# PRD Quality Review — Kubernetes-on-AWS

## Overall verdict
This is a strong PRD for a solo portfolio build. It has a clear thesis ("it focuses on operations, not deployment"), thresholds where most PRDs put adjectives, and counter-metrics that guard against gaming its own targets. Three things put the build at risk. The milestone table assigns FRs to M1 that depend on M2 features, so M1 can't be finished as written. The Persistent Footprint and bootstrap story leaves out the identities and secrets needed for a "zero manual steps" Rebuild through CI. The SLO and alerting FRs never say where request traffic comes from, so per-Session SLIs and burn alerts may have nothing to measure. All three are fixable in a paragraph each, and all three would otherwise surface as blocked stories.

## Decision-readiness — adequate
Decisions are stated as decisions, and the addendum records rejected alternatives with reasons. Examples are Cilium ("community-supported only on EC2"), in-cluster Postgres and DynamoDB ("no database DR story"), and Flux as the alternative to Argo CD. The open questions in §10 are real and each one names who decides ("deferred to the architecture step"). SM-C1 surfaces a real tension, RTO against Persistent Footprint growth, and resolves it in the open.

What's missing is any way to make calls under time pressure. The PRD contains no `[NOTE FOR PM]` callouts. §8.1 puts "everything in §4: FR-1 to FR-29" in scope against a budget of "roughly 75–90 usable hours" (§6), but it names no cut line. The biggest unspoken tension is in the sequencing itself. §4.9 calls incidents "the project's strongest evidence", yet they land in M3, after M2's "The operator starts applying to roles."

### Findings
- **[medium]** No cut line for a fixed hour budget (§6, §8.1). 29 FRs, an EKS upgrade, five baseline Drills and three Incidents have to fit into 75–90 hours, and the PRD gives no order in which to drop work if the hours run out. An AI agent or the builder will have to make that call ad hoc. *Fix:* add a short "if behind schedule, drop in this order" list (for example FR-8 upgrade → FR-22 → FR-24 → M3 stretch), or tag FRs must / should.
- **[medium]** The differentiator arrives after job applications start (§6 M2 "Done when", §4.9 Description). Applications begin at M2, but the Postmortems that SM-3 and UJ-3 rely on only exist at M3. This trade-off may be deliberate, but it isn't acknowledged. *Fix:* add a `[NOTE FOR PM]` stating the trade-off, or pull one Incident (for example the bad deploy, which needs only FR-13) into M2.

## Substance over theater — strong
The content is earned throughout. The Vision could not swap into another EKS PRD, because it is built on "ephemeral by design" and "every rebuild is a timed disaster-recovery drill". The three roles (Operator, Reviewer, App User) each drive FRs: the Reviewer drives FR-28 and FR-29 and the "2–5 minutes" constraint, and the App User drives FR-15. The NFRs have numbers: "< $30/month, with a hard cap of $50/month" and "RTO ≤ 45 minutes". The differentiation claim is backed by deliverables, not adjectives. SM-C3 ("A Postmortem claiming monitoring missed nothing is a warning sign") is the kind of line that only comes from thinking about the product.

### Findings
- **[low]** M2's "Done when" mixes in career context (§6). "The operator starts applying to roles" is not something the platform can be checked against. §0 says the PRD "does not repeat the career reasoning". *Fix:* move it to a note under the table.

## Strategic coherence — strong
The thesis is explicit in §1 and the SMs validate it rather than measuring activity. SM-1 (zero-touch Rebuild), SM-2 (RTO trend) and SM-3 (Incidents with shipped Action Items) measure exactly the operations story the Vision bets on. Each primary SM except SM-4 has a counter-metric. The MVP is a coherent experience-and-evidence scope. The "App is a workload, not a product" stance in §2.2 and §7 keeps the App from eating the hour budget, and the 8–10 hour cap backs it up.

### Findings
- **[medium]** SM-4, labelled "The real test", can't be verified (§9). "The operator can answer 'tell me about a time you…' questions … without notes" has no method or threshold, and no FR validates it, although it is the metric closest to the brief's actual goal. *Fix:* make it operational, for example "a recorded mock interview of 10 questions across the three areas, each answered from a specific Postmortem, ADR or Rebuild Log entry", and run it at the end of M2 and M3.

## Done-ness clarity — adequate
Most FRs carry testable bullets. FR-1 ("produces no diff"), FR-5 ("cannot reach"), FR-15 ("never reaches App code"), FR-16's no-snapshot fallback and FR-21's 45-minute failed-Drill rule are all checkable. The gaps sit in the observability and drill FRs that the thesis leans on most.

### Findings
- **[high]** SLOs and burn alerts have no traffic source (FR-17, FR-18, UJ-2). Per-Session SLOs ("≥ 99% of requests succeed") and the UJ-2 trigger ("An alert fires because the app's success SLI drops") assume steady request volume. A single operator logging a few workouts during a 2-hour Session produces too few requests for a success rate or burn rate to mean anything, so the UJ-2 alert may never fire. *Fix:* add an FR for a synthetic, authenticated traffic generator (rate, endpoints, and whether it runs through the SSO path). Also state a minimum request count before a Session's SLO counts.
- **[high]** The RTO measurement is undefined at its start point (§3 RTO, FR-21, UJ-1). RTO runs "from the start of a Rebuild", but UJ-1 begins with "opens a PR, merges it", and FR-20 has "one `terraform apply` plus an Argo CD sync". It's unclear whether the clock starts at the merge, the start of the apply job, or the operator's stopwatch ("He times the run"). It's also unclear what counts as "serving authenticated requests". A trend metric (SM-2) needs a fixed start and end. *Fix:* define both endpoints, for example "start = pipeline apply job start; end = first 200 from an authenticated synthetic probe". State whether the Rebuild Log entry is written automatically.
- **[medium]** FR-17's alerts have no destination or thresholds. "Alerts on SLO burn and on node or pod failure" doesn't say where alerts go, what burn-rate windows or thresholds apply, or how fast an alert must fire. *Fix:* name the notification channel and a burn-rate rule (for example "fast burn: 2% of budget in 5 min"), and add one testable bullet: "an injected FR-25 fault produces an alert within N minutes."
- **[medium]** FR-22 may not be feasible on an ephemeral stack (FR-22, §3 Teardown). Every Teardown destroys the RDS instance. Unless automated backups are retained after deletion, no automated backup survives to restore from, and with ~2-hour Sessions a daily backup window may never fall inside one. *Fix:* say whether the drill happens inside one Session (point-in-time restore of a live instance) or relies on retained automated backups. Add `[ASSUMPTION]` or hand the mechanism to the architecture step via the addendum.
- **[medium]** Documentation-only FRs have no acceptance bar (FR-6, FR-8, FR-11). "Documents each one: plan, steps, observed impact on the App's SLIs" (FR-8) doesn't say what impact is acceptable during an upgrade. FR-11 doesn't say what "sized against those requests" must show. *Fix:* add a bound, for example "the upgrade and rotation complete without breaching the Session SLO", and "the sizing note shows the requested-to-allocatable ratio per node".
- **[low]** FR-13's "within one sync cycle" is unbounded. The sync interval isn't stated. *Fix:* give a number ("within 5 minutes of merge") or name the configured interval.
- **[low]** FR-23 doesn't give a Pod Security Standards level. "Pod Security Standards are enforced" says nothing about whether the level is baseline or restricted. *Fix:* name the level.

## Scope honesty — adequate
§7 Non-Goals and §8.2 Out of Scope do real work, for example "Karpenter … to be revisited only after M3" and "EKS Auto Mode and Fargate". The App's "Out of Scope" line in §4.5 is a good local fence. The open-items density is low: 4 Open Questions and 3 Assumptions, which suits the stakes. The weakness is inferences left untagged, mostly around bootstrap and the Persistent Footprint.

### Findings
- **[high]** The Persistent Footprint leaves out what the Rebuild needs, and bootstrap is skipped (§3 Persistent Footprint, FR-9, FR-12, FR-20).
  - The glossary list omits the GitHub OIDC provider and its IAM roles, which CI needs before any pipeline apply can run.
  - It also omits the Secrets Manager secret from FR-10, the billing alarm from NFR-1, and the IAM roles from FR-9.
  - FR-20 claims an empty account can be rebuilt "with no manual steps beyond domain registration". In practice the state backend and OIDC trust have to be created once with human credentials, which is in tension with NFR-2's "no long-lived credentials anywhere".

  *Fix:* add the missing items to the Persistent Footprint list, or state that they're ephemeral. Add an explicit, accepted bootstrap exception (a one-time local apply with short-lived SSO credentials) to FR-20 and the Assumptions Index.
- **[medium]** The Rebuild and Teardown triggers contradict "zero manual steps" (UJ-1, FR-20, NFR-1). UJ-1 starts each Session with "opens a PR, merges it", and Teardown has no stated trigger. NFR-1 makes a stack "left running overnight" a cost defect, but nothing prevents or detects one. *Fix:* state how Rebuild and Teardown are invoked (pipeline dispatch, PR, or local command). Add an FR or NFR bullet for a guard, either a scheduled teardown or an alarm on an Ephemeral Stack running past N hours.
- **[low]** "RPO = 0 for a planned Teardown" is an untagged inference (FR-16, SM-7). It assumes no writes after the final snapshot starts. That's reasonable, but it's an inference. *Fix:* tag it `[ASSUMPTION]`, or add "the App is drained before the final snapshot".

## Downstream usability — adequate
This PRD is chain-top: it feeds architecture and then AI-agent stories, so this dimension matters. The glossary is good and its capitalized terms are used consistently. IDs are contiguous (FR-1–29, NFR-1–6, SM-1–7, SM-C1–3, UJ-1–3), every UJ has a named protagonist, and most feature descriptions say which UJ they realize. The addendum cleanly separates "choices already made" from "decisions handed to the architecture step". The main blocker for downstream work is the milestone mapping.

### Findings
- **[high]** M1 contains FRs whose done-ness depends on M2 features (§6 M1 row).
  - M1 lists FR-20, but FR-20 ends with "an App serving authenticated requests" after "an Argo CD sync", and both depend on §4.4 and §4.5 (FR-13, FR-15), which are in M2.
  - M1 starts the FR-21 baseline, but RTO by definition ends at authenticated App traffic, so no M1 Drill can record a valid RTO.
  - M1's "FR-1–FR-11" range includes FR-6 (packet path "through … Gateway API ingress, to the App pod"), which needs FR-14 (M2) and the App.
  - FR-8 appears in both M1 and M3.

  Story creation will either produce blocked stories or quietly reorder the work. *Fix:* re-slice M1 so that FR-20 and FR-21 in M1 cover an interim "Ephemeral Stack up" Rebuild against a placeholder workload, or move FR-6, FR-20 and FR-21 to M2. Remove FR-8 from M1.
- **[low]** Some role nouns are used but not in the glossary. "Operator" and "App User" appear capitalized in FRs (FR-1, FR-3, FR-15) but are defined only in §2.1. "session" (lowercase, §2.1, UJ-1 "weekend session") overlaps with the glossary's Session. *Fix:* add Operator and App User to §3, and use Session consistently.

## Shape fit — strong
The shape fits a solo, chain-top capability spec. Three UJs are enough: each one corresponds to a distinct deliverable (rebuild, incident, reviewer scan), and none is filler. Named technologies in the FRs are justified up front in §0, which says "some AWS and CNCF tools are themselves the scope". The length fits the 3–5 page target, and pushing detail into the addendum keeps the body readable. There's no over-formalization, such as an enterprise stakeholder matrix or compliance tables.

## Mechanical notes
- **Assumptions Index roundtrip:** all three inline `[ASSUMPTION]` tags (FR-2, FR-20, §10 Q1) are indexed. The index labels the FR-2 entry "§4.1 FR-2", which is correct, and the others resolve.
- **Cross-references:**
  - SM-C3 "Counterbalances FR-27". The other counter-metrics counterbalance SMs, so consider "Counterbalances SM-3".
  - SM-4 has no "Validates" link.
  - §4.1, §4.3 (FR-8, FR-11) and §4.8 have no "Realizes UJ-x". That's acceptable, but FR-23 and FR-24 could cite UJ-3.
- **Cost consistency:** §1 says "under $50/month", while NFR-1 and SM-5 target "< $30". This is consistent if $50 is read as the cap, but consider citing both figures in §1. The one-time domain registration (~$10–15) will hit a single month's budget, which is worth a line in NFR-1.
- **FR-4:** "free gateway endpoints for S3 and DynamoDB". The DynamoDB endpoint has no stated consumer, since the App uses RDS. If it exists for Terraform state locking, say so. S3-native locking may make it unnecessary.
- **Addendum provenance:** the addendum cites `extract-brief.md`, which exists in the PRD folder. The reference resolves.
