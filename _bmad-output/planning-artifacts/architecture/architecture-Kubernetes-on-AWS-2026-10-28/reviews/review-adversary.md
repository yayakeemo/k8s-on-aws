---
type: architecture-review
lens: adversarial (compliant-but-incompatible epic pairs)
target: ../ARCHITECTURE-SPINE.md
date: 2026-10-28
---

# Adversarial Review: Architecture Spine, Kubernetes-on-AWS

**Verdict:** The layering and the SSM handoff are sound. However, the spine leaves the **Teardown-vs-GitOps control path**, the **L3 annotation contract**, **tag semantics for artifacts that outlive a Session**, and **in-cluster ordering** undefined. Two epics can each obey every AD and still produce a platform that does not tear down, does not pass its own Teardown check, or does not start. Thirteen holes are listed below: 2 Critical, 6 High and 5 Medium. Each one ends with a proposed rule that closes it.

Method: for each hole, two epics are built that both follow the AD text exactly. The divergence is shown, and then the rule that would make one of the two builds non-compliant.

---

## H1: Teardown deletes apps that Argo CD immediately re-creates (Critical)

- **Units:** Session Lifecycle/Teardown × Pipeline (GitOps root, `gitops/root`)
- **Compliant divergence:**
  - The Pipeline epic builds the root app-of-apps with `automated: {prune: true, selfHeal: true}`. That is a normal GitOps choice, and no AD forbids it.
  - The Teardown epic follows AD-7: "delete workload apps … delete Gateway + HTTPRoutes" (for example, `argocd app delete` or `kubectl delete application`).
  - The root app sees its child Applications drift from Git and re-creates them within seconds. LBC then re-provisions the ALB and ExternalDNS re-writes the records.
  - The AD-7 poll ("ALB deleted, Route 53 records removed") never converges, or it converges briefly and then L3 destroy runs while a fresh ALB exists. The result is orphaned ALB, ENIs and security groups, and a hung VPC destroy.
  - A second problem: AD-4 forbids `kubectl apply` outside L3, but it says nothing about `kubectl delete` or `kubectl patch` from a workflow. Both epics can read that silence differently.
- **Also racing:** a merge to `gitops/` (an image-bump commit or a fault revert) during Teardown is not in the `ephemeral` concurrency group, because Argo CD pulls the change and is not triggered by a workflow. AD-5 gates workflows only, not reconciliation.
- **Closing rule (AD-7a, new):**
  - Teardown changes the cluster only through L3.
  - Its first step is `terraform apply infra/ephemeral/gitops -var teardown_phase=1`. That sets a cluster-secret annotation `teardown-phase`.
  - ApplicationSet generators select on that annotation, so phase 1 drops workloads and phase 2 drops Gateway and HTTPRoutes, while platform controllers stay.
  - The root app has `selfHeal` but never deletes the controllers until L3 destroy.
  - No workflow runs `kubectl` or `argocd` commands that mutate the cluster.
  - Argo CD sync windows deny syncs while `/k8s-on-aws/session/active` is `tearing-down:<id>` (see H7).

## H2: RDS final snapshots carry `Layer=ephemeral`, so the post-Teardown check can never pass (Critical)

- **Units:** Data (L2 RDS) × Session Lifecycle (AD-6 check)
- **Compliant divergence:**
  - The Data epic sets `copy_tags_to_snapshot = true`, which is the sensible default for traceability.
  - The provider `default_tags` (AD-6) stamp `Layer=ephemeral, Session=<id>` on the instance, and therefore on `k8s-on-aws-final-<id>` and on the retained automated backups (AD-9 `delete_automated_backups=false`).
  - Check (a) ("`Layer=ephemeral` returns nothing") then returns up to 5 snapshots on every run.
  - The same thing happens to KMS keys in `PendingDeletion` that the EKS module creates (a 7 to 30 day window), and to the ACM certificates and Secrets Manager secrets in their recovery window.
  - The Teardown epic will "fix" this by adding exclusions to the check, which silently weakens the Teardown contract.
- **Closing rule (AD-6a):**
  - Artifacts that are designed to outlive a Session are re-tagged `Layer=persistent, Retains=session-artifact` by the Teardown workflow immediately after L2 destroy. This covers final snapshots and retained backups.
  - Check (a) ignores only resources in a terminal pending-deletion state (KMS `PendingDeletion`). This exemption is listed by type in `allowlist.yaml` and is never matched by tag.
  - The EKS module's KMS key is replaced by the AWS-managed key, or it moves to L1, so that no key is created per Session.

## H3: Controller ownership is split between L3 and L4 (High)

- **Units:** Cluster & Identity (L2 Pod Identity) × Edge & App / Observability (L4 charts)
- **Compliant divergence:**
  - AD-4 says Terraform owns the Pod Identity associations, and those associations are keyed by `namespace/serviceAccount`. The Cluster epic picks `kube-system/aws-load-balancer-controller`, `external-secrets/external-secrets` and `observability/alloy`.
  - The Edge epic uses the LBC chart with `fullnameOverride: lbc`. The k8s-monitoring chart names its service account `k8s-monitoring-alloy-metrics`.
  - Pods start with no AWS credentials. Nothing fails at plan time, because EKS does not check that the service account exists.
  - Separately, AD-7 says "destroy infra/ephemeral/gitops (controllers, Argo CD)", which implies the controllers live in L3. The layer table and the source tree put them in L4 (`gitops/platform`).
  - An L3 epic that installs LBC with `helm_release` (it's "the GitOps handoff") and an L4 epic that also ships `gitops/platform/lbc` both look compliant, and together they create two owners.
- **Closing rule (AD-4a):**
  - A single registry, `infra/modules/workload-identity/map.yaml`, lists each component, namespace, service account and IAM policy. L2 creates associations from it. L3 publishes `sa.<component>=<ns>/<name>` annotations from it, and every chart's `serviceAccount.name` is templated from that annotation and never set literally.
  - AD-7's wording changes to: "L3 destroy removes Argo CD, which is the last owner of the controllers that L4 installed".
  - L3 installs nothing except Argo CD, the cluster Secret and the root app.

## H4: L4 has no path to L1 values (High)

- **Units:** Pipeline (L3 handoff) × Edge/Observability (L4)
- **Compliant divergence:**
  - The layer diagram shows `L3 reads SSM from L2` only. The L3 epic therefore publishes VPC ID, cert ARN, session_id and cluster name.
  - oauth2-proxy needs the Cognito pool ID, issuer and client ID. Alloy needs the AMP remote-write URL and the log group. ExternalDNS needs the zone ID and domain. ESO needs the region and secret prefix. All of these are L1 values.
  - The Edge epic hard-codes the issuer in `gitops/` values. That is allowed, because AD-4 forbids only per-Rebuild values in Git. The value then goes stale the first time the Cognito pool is replaced in L1.
- **Closing rule (AD-3a):**
  - The L3 annotation set is a closed, versioned contract, `infra/ephemeral/gitops/bridge-contract.yaml`. It enumerates every key, source layer and SSM path, covering L0, L1 and L2.
  - L3 may read any lower layer's SSM. The diagram changes to show that.
  - `gitops/` may not contain an AWS identifier, ARN, URL or domain literal. A CI grep enforces this.

## H5: db-init and the PreSync migration race, and the master secret breaks AD-17 (High)

- **Units:** Data (`db-init`, L2 RDS) × Edge & App (App Application, PreSync migrations)
- **Compliant divergence:**
  - The Data epic ships `db-init` as its own Application under `gitops/workloads/db-init`. The App epic runs migrations as a PreSync hook in the `app` Application, as AD-10 requires.
  - On a fresh Rebuild, the two Applications sync in parallel. The migration tries to connect as `app` before that role exists, fails, and enters backoff. The Service RTO then includes an arbitrary amount of retry time.
  - The RDS-managed master secret is named `rds!db-<uuid>`, is created in L2, and changes on every Rebuild. AD-17 requires every secret to live in L1 as `k8s-on-aws/<consumer>/<name>` with "no secret in L2". The Data epic cannot satisfy both AD-10 and AD-17.
  - The `rds-db:connect` resource ARN contains the DbiResourceId, which changes on every Rebuild. It must stay in L2 and never be written in a fixed form.
- **Closing rule (AD-10a):**
  - `db-init` and `migrate` are hooks in the **same** Application: PreSync wave -2 runs `db-init` and wave -1 runs `migrate`.
  - AD-17 gains one named exception. The RDS-managed master secret is reached only by `db-init`, through an ESO `SecretStore` scoped to the `app` namespace, with the ARN taken from the `rds.master-secret-arn` annotation.
  - The IAM-auth policy is built in L2 from `aws_db_instance.resource_id`.

## H6: Default-deny NetworkPolicy is either a no-op or locks out admission webhooks (High)

- **Units:** Network / Cluster (L2 VPC CNI add-on) × Hardening/Edge (L4 policies, Kyverno)
- **Compliant divergence:**
  - **Variant A:** the Cluster epic installs VPC CNI with default config, which leaves `enableNetworkPolicy` off. The L4 epics write perfect default-deny and allow policies that are never enforced. The AD-11 "only oauth2-proxy reaches App" rule is false, and nothing detects it.
  - **Variant B:** the add-on is enabled. The Network-policy convention ("every namespace starts with default-deny ingress") then applies to `kyverno`, `kube-system` (the LBC webhook), `external-secrets` (webhook) and `argocd`.
  - With `failurePolicy: Fail`, every Pod create is denied, and the cluster wedges on its first sync.
  - IP-mode ALB targets in `app` also need an allow from the ALB security group or the VPC CIDR.
- **Closing rule (Network convention, tightened):**
  - L2 sets `enableNetworkPolicy=true` on the VPC CNI add-on.
  - Each namespace's baseline is a pair of policies, default-deny plus `allow-from-control-plane` on webhook ports.
  - `app` allows ingress to oauth2-proxy from the VPC CIDR on the ALB target port only.
  - A Rebuild acceptance test proves that a denied flow is in fact denied.

## H7: Session state machine has only two states (High)

- **Units:** Pipeline (`ephemeral-apply`) × Incidents/Hardening (Action-Item fixes) × Rebuild
- **Compliant divergence:**
  - AD-5 lets `ephemeral-apply` plan only when the value is `none`, which is exactly when there is nothing to apply to. A `fix(pm-n)` that changes an L2 security group, node group or RDS parameter therefore never reaches the live Session where the Incident is being re-tested (AD-14), and lands only at the next Rebuild.
  - The Incidents epic expects re-test in the same Session. The Pipeline epic implements plan-only. Both are compliant.
  - Rebuild "sets it to a new session_id as its first step" without checking the current value. If a previous Teardown failed (the value is still the old id), the new Rebuild applies against the old state key. It re-tags everything with the new `Session`, changes `final_snapshot_identifier`, and orphans the old Session's audit trail.
  - If the post-Teardown check fails, AD-7's last step (`= none`) never runs, and `ephemeral-apply` stays blocked with no defined recovery.
- **Closing rule (AD-5a):**
  - The parameter holds one of `none | building:<id> | active:<id> | tearing-down:<id> | failed:<id>`.
  - Rebuild proceeds only from `none`.
  - Teardown proceeds from any non-`none` state.
  - `ephemeral-apply` *applies* L2/L3 with the current id when the state is `active:*`, inside the `ephemeral` group, and is a no-op otherwise.
  - A failed check leaves `failed:<id>`, which only a successful Teardown re-run clears.

## H8: The ESO identity can read every secret (High, security)

- **Units:** Secrets/Cluster (ESO Pod Identity role) × Observability & Probe / Edge (ExternalSecrets)
- **Compliant divergence:**
  - AD-17 says ESO authenticates through Pod Identity, and Pod Identity binds to the *controller's* service account.
  - The simplest compliant policy is `secretsmanager:GetSecretValue` on `k8s-on-aws/*`, served through one `ClusterSecretStore`.
  - Any namespace can then create an `ExternalSecret` for `k8s-on-aws/oauth2-proxy/cookie-secret`. A compromised Probe namespace could forge sessions.
- **Closing rule (AD-17a):** each consumer namespace gets a `SecretStore` whose AWS provider `role:` assumes a per-consumer role. That role is defined in L2 from the H3 registry and scoped to `k8s-on-aws/<consumer>/*`. `ClusterSecretStore` is forbidden.

## H9: The ExternalDNS domain filter excludes its own TXT ownership records (Medium)

- **Units:** Domain/DNS (AD-19 flags) × Edge (Gateway, HTTPRoute)
- **Compliant divergence:**
  - `--domain-filter=app.<domain>` combined with the default TXT registry naming (`a-app.<domain>`, `cname-app.<domain>`) puts the ownership records outside the filter.
  - ExternalDNS then cannot claim or clean its records, so AD-7's "records removed" poll stalls, or stale records survive.
- **Closing rule:** add `--txt-prefix=_extdns-%{record_type}.` so that ownership records fall under `app.<domain>`. AD-19 lists the full flag set, which removes the matching item from the Deferred list.

## H10: Argo CD needs a Git credential before ESO exists (Medium, circular)

- **Units:** Pipeline (L3 Argo CD install) × Secrets (AD-17)
- **Compliant divergence:**
  - If the repo is private, Argo CD needs a repo credential to sync anything, including ESO.
  - AD-17 says secrets reach pods only through ESO, and ESO is itself installed by Argo CD. That is a cycle.
- **Closing rule:** state either that "the repo is public, so Argo CD uses anonymous HTTPS", or add a named exception: L3 creates the single repo-credential Secret from `k8s-on-aws/argocd/repo-creds` (L1).

## H11: The Rebuild Log has two writers and no defined owner (Medium)

- **Units:** Rebuild workflow × Teardown workflow (AD-20)
- **Compliant divergence:**
  - Rebuild knows `platform_ready_at` and `service_ready_at`. Teardown knows `slo_summary`, `rpo_s` and the snapshot.
  - Both commit `docs/rebuild-log/<id>.json`.
  - If Rebuild fails before its commit, Teardown writes a partial record in a different shape. Two bypass commits per Session on `main` also trigger `pr-plan` and `ephemeral-apply` path filters, unless they are excluded.
  - PITR (`restore_mode=pitr`) needs the previous instance's DbiResourceId, and nothing records it.
- **Closing rule (AD-20a):**
  - Rebuild writes its timings and `dbi_resource_id` to `/k8s-on-aws/session/<id>/*` SSM parameters.
  - Teardown is the only writer of the JSON. It writes one commit, which touches only `docs/rebuild-log/**` and is excluded from all other workflow triggers.

## H12: Fixed resource names collide across overlapping or failed Sessions (Medium)

- **Units:** Cluster (EKS name, IAM role names) × Network (subnet `kubernetes.io/cluster/<name>` tags) × Edge (LBC `--cluster-name`)
- **Compliant divergence:**
  - One epic names the cluster `k8s-on-aws-<session_id>` to avoid collisions with a half-destroyed predecessor. Another tags subnets for `k8s-on-aws`. LBC then discovers no subnets.
  - Separately, session_id has minute resolution, so two dispatches within the same minute collide on the snapshot and log names.
- **Closing rule:** the cluster name is the constant `k8s-on-aws`, published in the bridge contract. Ephemeral IAM role names take the `k8s-on-aws-eph-` prefix. Rebuild rejects a session_id whose `k8s-on-aws-final-<id>` snapshot or log file already exists. Together with H7, this means at most one Session exists at a time.

## H13: Faults in L1 outlive the Session, and alerts fire every night (Medium)

- **Units:** Incidents (AD-14 auth faults) × Bootstrap/Persistent; Observability (AMP rules in L1) × Teardown
- **Compliant divergence:**
  - An auth fault on "the Cognito client" is an L1 change, applied by `persistent-apply` outside the `ephemeral` group. If it is not reverted before Teardown, it persists into the next Session, and the next Rebuild's Service RTO never completes.
  - Node and pod alert rules in AMP that use `absent()` or `up == 0` fire to SNS every night, because no cluster is running.
- **Closing rules:**
  - Teardown fails when there is an open `fault(*)` revert pending against `infra/persistent`.
  - Every AMP alert expression is joined with `probe_up{session_id!=""}` (or the rule groups are gated by session-presence recording), so no alert can fire while the state is `none`.

---

## Additional notes (not counted as holes)

- **Identity gap: ci-apply permissions.** L0 is applied only by a human, so every epic that needs a new CI permission (AMP query for AD-20 Service-ready, `rds:DescribeDBSnapshots`, `tag:GetResources`, ELB and Route 53 polling) is blocked on a human apply. Recommendation: enumerate the ci-apply policy in AD-18 up front, and give it a per-layer permission boundary.
- **Human access entries** need the Identity Center role ARN, which has a random suffix. Publish it as `/k8s-on-aws/bootstrap/admin-role-arn`.
- **AD-3 inconsistency:** AD-3 lists `<layer>` as `bootstrap | persistent | core`, but AD-5 uses `/k8s-on-aws/session/…`. Add `session` as a layer-neutral namespace owned by the workflows.
- **CRD ordering in L4:** Gateway API CRDs and the ESO and Kyverno CRDs must exist before the objects that use them. Argo CD does not compute Application health for child Applications by default, so sync waves across Applications do nothing unless the Application health check is re-enabled in `argocd-cm`, which L3 owns. Add this to AD-4.
- **Pod Identity Agent:** the agent must be an L2 EKS add-on that is ready before L3 completes. Otherwise the first L4 pods cache an identity with no credentials.
- **Verify:** check that Grafana Alloy 1.21 ships a CloudWatch Logs writer component (the AD-13 log path). If it does not, the log path needs Fluent Bit or the CloudWatch Observability add-on, which would be a second log agent.
