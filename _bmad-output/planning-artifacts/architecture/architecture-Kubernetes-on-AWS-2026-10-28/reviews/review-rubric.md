# Review — ARCHITECTURE-SPINE (Kubernetes-on-AWS) against the good-spine rubric

- **Reviewed:** `ARCHITECTURE-SPINE.md` (draft, 2026-10-28)
- **Driving spec:** `prds/prd-Kubernetes-on-AWS-2026-10-27/prd.md` (+ addendum, consulted for cost/RDS pitfalls)
- **Reviewer date:** 2026-10-28

## Verdict

**Revise before epics.** This is a strong spine. The layering, the SSM handoff, the GitOps Bridge boundary, the Probe-as-only-SLI rule and the Rebuild Log schema are the right invariants, and most Rules can be enforced. Two Rules have gaps that let billable resources come back or make the post-Teardown check fail by design (AD-5, AD-6). Two Rules conflict with each other (AD-10 vs AD-17). FR-5's RDS clause has no mechanism. One real cross-epic contract is missing: the App HTTP API that the Probe calls. None of these needs a redesign. Each one is fixed by adding or tightening a Rule.

---

## 1. Divergence points: fixed vs missed

**Fixed well:** layer ownership (AD-1), state/roots (AD-2), cross-root handoff (AD-3), Terraform/Argo boundary (AD-4), Session gating (AD-5), tagging (AD-6), Teardown order (AD-7), stateless cluster (AD-8), DB identity (AD-10), edge chain (AD-11), SLI source (AD-12), image/deploy (AD-16), secret path (AD-17), DNS ownership (AD-19), Rebuild Log schema (AD-20).

**Missed divergence points:**

| # | Gap | Epics that diverge | Severity |
|---|---|---|---|
| M1 | **App HTTP contract.** The Probe (`feature="log|list"`) and the App are built in separate epics. Paths, methods, request/response bodies and success status codes are not fixed. The Consistency table fixes the DB table instead, which is internal to the App. | App vs Observability/Probe | High |
| M2 | **NetworkPolicy enforcement engine and egress.** The convention is "default-deny *ingress*". FR-5 also requires that "a pod without an explicit allow cannot reach the RDS endpoint". Ingress policy cannot block egress to RDS, which sits outside the cluster. The engine is not named either (VPC CNI network-policy agent vs Calico), and the Cluster epic must turn it on. | Network vs Cluster vs App | High |
| M3 | **How CI writes to Git.** AD-16 needs a CI-made tag-bump commit to `gitops/`. AD-20 needs CI-written Rebuild Log files. Only the second appears (under Deferred). Both need the same branch-protection/bot mechanism. | Pipeline vs App/Images vs Drills | Medium |
| M4 | **Image-push identity.** `image-build` runs on merge and has to push to ECR. `ci-plan` is read-only, and `ci-apply` trusts only `environment:*` subjects. Which role pushes is undecided. | Pipeline vs Images | Medium |
| M5 | **Ordering of `db-init` vs migrations.** On a fresh DB, the migration PreSync Job (connecting as `app` via IAM auth) fails if `db-init` has not created role `app` first. The sync-wave/hook ordering is not fixed, and the two Jobs may sit in different Applications. | Data vs App | Medium |
| M6 | **Planning L3 with no cluster.** `pr-plan` on `infra/ephemeral/gitops` outside a Session has to configure the kubernetes/helm providers against a cluster that doesn't exist, so the plan errors. The spine never says that L3 (and L2?) plans are skipped or stubbed when `session/active = none`. | Pipeline vs GitOps | Medium |

## 2. Can each Rule be enforced, and does it prevent its stated divergence?

- **AD-5 (High): leaves a gap that recreates billable resources.** The Rule says "`ephemeral-apply` *plans only* when the value is `none`". It never says that it *applies* only when the value is a live `session_id`. Worse, Teardown sets `none` only as its **last** step, and only after the post-Teardown check passes. If Teardown fails partway (for example, the check fails loudly), the value stays at the old `session_id` while the stack is half destroyed. The next merge then runs `ephemeral-apply`, which rebuilds L2 outside any Session. That is exactly the FR-12/NFR-1 violation AD-5 exists to prevent.
  *Fix:* use a three-value state, `<session_id>` | `tearing-down` | `none`. Teardown writes `tearing-down` as its **first** step. `ephemeral-apply` applies only when the value matches `^s\d{8}-\d{4}$`, and otherwise plans only. Also: L0 creates the parameter, so L0 needs `lifecycle { ignore_changes = [value] }`, or the next L0 apply resets the value. And `session` is not in AD-3's layer enum (`bootstrap|persistent|core`), so add it.
- **AD-6 (High): check (a) fails by design, and one cost leak is untracked.**
  - The RDS final snapshot inherits the instance's tags (`copy_tags_to_snapshot`/default_tags), including `Layer=ephemeral`. Retained automated backups (AD-9 `delete_automated_backups=false`) behave the same way. Either one makes query (a) return results after every successful Teardown.
  - `terraform-aws-modules/eks` creates a customer-managed KMS key by default. Destroying it only *schedules* deletion (7–30 days). The key is still listed with `Layer=ephemeral` and costs about $1/month prorated. One accumulates per Session.
  - The Resource Groups Tagging API keeps returning terminated/deleted resources for a while (eventual consistency), so (a) can flap.
  *Fix:* set `copy_tags_to_snapshot = false`, and have Teardown tag the final snapshot `Layer=persistent`, or explicitly exclude `rds:snapshot`/automated backups from (a). Either fix the EKS module's KMS key (`create_kms_key = false`, using the AWS-managed key) or move it to L1. In (a), ignore resources in a terminated/deleted/pending-deletion state.
- **AD-7 (Medium): the sequence can be undone by Argo CD.** "Delete workload apps / delete Gateway" through Argo CD gets reverted by self-heal on the root app-of-apps unless auto-sync is turned off on the root first. The diagram also says "destroy infra/ephemeral/gitops (controllers, Argo CD)". AD-4 makes controllers Argo-owned L4, not L3. Destroying the Argo CD Helm release while Applications still carry `resources-finalizer` can hang namespace deletion.
  *Fix:* step 0 = turn off root auto-sync (or delete the root app non-cascading). Delete apps in reverse sync-wave order, and put Kyverno webhooks before controllers. Relabel the L3 step "Argo CD + root app".
- **AD-10 vs AD-17 (High): the two Rules contradict each other.** AD-17 says "every secret is created in L1 … there is no secret in L2". AD-10 relies on the RDS-managed master secret, which RDS creates in L2 under name `rds!db-…` and which gets a new ARN on every Rebuild. The Rules don't say how `db-init` reaches it (ESO? an annotation carrying the ARN?).
  *Fix:* add one named exception to AD-17. The RDS-managed master secret is delivered through an ESO `ExternalSecret` in namespace `app`, and its ARN is passed as a GitOps Bridge annotation.
- **AD-9 (Low):** the `restore_to_point_in_time` block also belongs under `ignore_changes`. Otherwise an `ephemeral-apply` during a Session that runs without `restore_mode` can force RDS replacement (FR-16, last bullet).
- **AD-11 (Low):** with default-deny ingress in `app`, the ALB → oauth2-proxy hop needs an explicit allow (ALB IP targets come from VPC subnets). Say so, or the Edge epic and the Network epic will each assume the other handles it.
- **AD-15 (Low):** "Third-party charts must publish arm64 images" can only be enforced once Kyverno exists. Kyverno is deferred to Postmortems (FR-24), so for now this is a review-time check. That's acceptable, but state it.
- **AD-1, 2, 3, 4, 8, 12, 13, 14, 16, 18, 19, 20:** each can be enforced (lint/grep/CI checks are possible) and each addresses its stated divergence.

## 3. Could anything under Deferred let two epics diverge?

- **Rebuild Log commit mechanism.** It's safe only if the same mechanism also covers the AD-16 tag-bump commit (M3). Merge the two into a single "CI writes to Git" decision.
- **oauth2-proxy flags.** Mostly safe, but the claim used for `X-Forwarded-User` *must* be `sub` (AD-11), and that is the App/Edge contract. Fix `--user-id-claim=sub` in AD-11 and defer the rest.
- **CIDR/node mix:** safe. "Min 2 nodes across 2 AZs" is the invariant. Consider also requiring ≥2 Spot instance types, so a single Spot pool reclaim doesn't take out both nodes during a Drill.
- **SLO maths, chaos framework, pull-through cache, Kyverno policies, mesh:** safe.

## 4. Is the named tech plausibly current (claimed verified 2026-10-28)?

Most entries are plausible for late 2026 given release cadences (AWS provider 6.70, EKS 1.36, Argo CD 3.5, Grafana 13.3, Gateway API 1.6, Python 3.14, uv 0.13).

- **RDS for PostgreSQL 17.11: likely not yet released.** PostgreSQL minors ship quarterly on the second Thursday of Feb/May/Aug/Nov. 17.10 would be Aug 2026, and 17.11 would be about 12 Nov 2026, *after* the verification date. RDS also lags upstream. *Fix:* re-verify with `aws rds describe-db-engine-versions --engine postgres`. Also record why 17 was chosen over PostgreSQL 18, which is GA on RDS.
- **External Secrets Operator 2.14.0:** a high minor for its release cadence. Re-check.
- **Alloy → CloudWatch Logs (AD-13):** check that the Alloy release ships a CloudWatch Logs exporter component. If it doesn't, the log path needs Fluent Bit or the CloudWatch Observability add-on. That would add a component the Observability and Cluster epics must agree on.
- **Alloy 1.21.2 and k8s-monitoring 4.5.5** are listed separately. The chart pins its own Alloy version, so state which one wins.

## 5. PRD coverage (FR-1..33, NFR-1..6)

All FRs appear in `binds` and in the capability map. Coverage is thin or mis-attributed here:

| Item | Issue | Fix |
|---|---|---|
| FR-5 | The RDS-reachability clause is not achieved (M2). | Add default-deny egress in `app`/`probe` (or Security Groups for Pods), and fix the engine. |
| FR-8 | Upgrade/node-rotation path not addressed: in-Session `ephemeral-apply` of the version variable? node-group update strategy? | One line in AD-5/Versions: upgrades happen in-Session through `ephemeral-apply` of the single version variable. |
| FR-23 | The CIS scan tool (kube-bench / EKS benchmark) is neither decided nor deferred. The map wrongly cites AD-14 (faults). | Add to Deferred (Hardening epic), and fix the map. |
| FR-33, FR-6, FR-29 | Docs only. Mapping to AD-15 is meaningless. | Map to the Docs convention only. |
| NFR-3..NFR-6 | Not in the capability map. NFR-5 (≤45 min RTO) has no architectural lever named (e.g., L2 RDS restore runs in parallel with EKS creation). | Add rows. State that RDS and EKS are created in parallel within L2. |

## 6. Operational envelope

| Dimension | Status | Note |
|---|---|---|
| Deployment & environments | Decided | single env, us-east-1, one account |
| Infra/provider strategy | Decided | Terraform roots + Argo CD |
| Operations (alerting, runbooks) | Mostly decided | alert email via SNS. Who reads it outside a Session (alerts with no data)? Fine as is. |
| **Cost** | **Gap** | The billing alarm threshold/mechanism (CloudWatch billing alarm vs AWS Budgets) is not fixed. There's no pointer to the addendum's cost inputs. Persistent-footprint cost drivers are unbounded: ECR has no lifecycle policy, and with immutable `sha-*` tags images pile up. Retained automated backups and KMS keys also accumulate. *Fix:* add AD "Cost guards": the threshold value, an ECR lifecycle (keep N), a backup retention days value, and a cost-model link. |
| **Backup/DR** | Partial | RDS is covered. The state bucket (versioning? object lock?), Cognito user pool (deletion protection; users are not backed up) and AMP workspace (deletion protection) are not addressed, and these are the Persistent Footprint's single points of loss. *Fix:* one Rule: L0/L1 critical resources have `prevent_destroy` + service deletion protection, and the state bucket is versioned. |
| Security | Mostly decided | Account-level detection (CloudTrail, GuardDuty) is neither decided nor deferred. Defer it explicitly, with the cost note. |

## 7. Bloat (not invariants)

- **The `App data` convention** (table `workouts`, UUIDv7, column types) is internal to the App epic. Replace it with the App HTTP contract (M1), and keep only the JSON error envelope.
- **The Commits convention** (Conventional Commits) is a repo-hygiene preference, not a cross-epic invariant. It can stay (cheap), but `fault(<incident>)` is the only load-bearing part.
- **Stack rows for FastAPI/psycopg/uv** touch only the App epic. They're harmless as a seed, but nothing outside `app/`/`probe/` depends on them.
- **Deferred "Karpenter, Auto Mode…"** repeats PRD §7. One line pointing to the PRD is enough.
- **The [ASSUMPTION] in AD-12** about the hosted-UI gap is useful content, but it belongs in the Observability epic/Postmortem material. Keep it as a one-liner.

## 8. Mermaid diagrams

Checked by hand against Mermaid flowchart/sequence grammar.

1. **Layer flowchart (`flowchart BT`)**: valid. `<br/>`, `·` and edge labels are fine.
2. **Teardown `sequenceDiagram`**: valid syntax. One rendering caveat: `k8s-on-aws-final-<session_id>` contains `<session_id>`, which Mermaid's HTML sanitizer may strip as an unknown tag, so the label renders as `k8s-on-aws-final-`. *Fix:* write `&lt;session_id&gt;` or `{session_id}`. The `= none` text is fine.
3. **Topology `flowchart LR`**: valid. Subgraph-to-node edge `PRIV --> nat` and the stadium/cylinder shapes are fine. `r53` is first referenced outside `PF` and then listed inside it. That renders inside `PF` as intended. Semantic nit: the diagram places `app.<domain>` records in the Persistent Footprint, but they are ephemeral (AD-19). Label the node "Route 53 hosted zone". LBC/ExternalDNS are not drawn, which is acceptable at seed level.

## Prioritised fix list

1. AD-5: three-value session state with `tearing-down` written first; apply only on a valid session_id; `ignore_changes` on the L0 parameter. **High**
2. AD-6: fix snapshot/backup tag inheritance and the EKS KMS key, and filter deleted resources in check (a). **High**
3. AD-10/AD-17: add a named exception for the RDS-managed master secret (ESO + ARN annotation). **High**
4. Add the App HTTP contract to Consistency Conventions; remove the table schema. **High**
5. FR-5: fix the NetworkPolicy engine and add default-deny egress (or SG-for-Pods) for RDS. **High**
6. AD-7: turn off root auto-sync first; fix the L3 label; add finalizer/webhook ordering. **Medium**
7. Pipeline: one decision covering CI Git writes (tag bump + Rebuild Log), the image-push role, and L3 plan behaviour outside a Session. **Medium**
8. Cost and DR guards: billing threshold, ECR lifecycle, `prevent_destroy`/deletion protection, versioned state bucket. Re-verify PostgreSQL 17.11 and the ESO version. **Medium**
