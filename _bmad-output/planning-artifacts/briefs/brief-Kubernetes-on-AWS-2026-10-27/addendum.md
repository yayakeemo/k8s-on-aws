---
title: "Addendum: Kubernetes-on-AWS Product Brief"
created: 2026-10-27
updated: 2026-10-27
---

# Addendum — Kubernetes-on-AWS

This addendum holds detail that belongs in downstream documents (the product requirements document, or PRD, and the architecture) rather than in the brief.

## Anchor posting: Accenture Cloud Platform Engineer, requirement vs. evidence (draft)

| Posting requirement | Current evidence (resume) | Status | What the project must produce |
|---|---|---|---|
| Strong Linux networking | Linux sysadmin, LDAP service, DNS-log analysis in the MFA case | Partial: no designed network on record | VPC designed by hand, plus a debugging write-up showing a packet's path from the internet through ingress to a pod |
| Infrastructure as code (IaC): Terraform / Ansible / CloudFormation | Terraform Associate, Ansible playbooks, Ansible Vault | **Strength** | Terraform module and state design as the backbone of the platform |
| Kubernetes **operations** experience | Listed as a competency, nothing in experience | **Gap** | Operations evidence beyond deployment: upgrades, node rotation, troubleshooting, capacity |
| Service mesh / ingress | None | **Gap** | Ingress or Gateway API controller, plus a service-mesh decision recorded as an architecture decision record (ADR) |
| Incident **leadership** | "Incident response" listed, nothing in experience | **Gap** | Simulated incidents run with roles and communications, then blameless postmortems with action items that get shipped |
| Disaster recovery / business continuity planning (DR / BCP) execution | OCI Full Stack Disaster Recovery (FSDR) with recovery time and recovery point objective (RTO/RPO) targets | **Strength** to translate | Rebuild of the platform with a measured, documented RTO |

## Workload and data design notes (for architecture)

- **App:** a minimal Python fitness app with two features, "log a workout" and "list my workouts". Effort is capped at about 8–10 hours, and anything beyond that goes on a "someday" list.
- **Edge auth:** OpenID Connect (OIDC) single sign-on (SSO) in front of the app (oauth2-proxy or equivalent), with **Amazon Cognito** as the identity provider. Cognito lives outside the ephemeral platform, so users persist across rebuilds. This is the cloud-native version of the CGI mod_auth_openidc / Apache project.
- **Data:** **Amazon RDS (db.t4g.micro)**, created and destroyed with the platform.
  - Destroy takes a final snapshot. Apply restores from the latest snapshot. The measured restore time gives the RTO, and the gap since the last snapshot gives the RPO.
  - Terraform gotchas to resolve in architecture:
    - Final snapshot identifiers must be unique per destroy, and a naive timestamp causes a perpetual diff.
    - The restore needs to find the latest snapshot (e.g., `aws_db_snapshot` with `most_recent`).
    - The first apply has no snapshot to restore from.
  - Expect about 10–20 minutes of extra rebuild time for the RDS restore.
- **Identity showcase:** the app pod uses EKS Pod Identity to get an IAM role, then authenticates to RDS with IAM database authentication, so no static DB password is needed. Secrets Manager covers any remaining secrets (e.g., the oauth2-proxy cookie secret).
- **Rejected alternatives:**
  - In-cluster Postgres with S3 backup: richer Kubernetes stateful-ops story, but the user preferred hands-on time with a managed AWS service.
  - DynamoDB: no database DR story.

## Research digest (web research, 2026-10-27)

Prices are snapshots for us-east-1. Check them again before committing to a cost model.

### Cost inputs

| Item | Price | Source |
|---|---|---|
| EKS control plane (standard support) | $0.10/hr (~$73/mo always-on) | aws.amazon.com/eks/pricing |
| EKS control plane (extended support) | $0.60/hr. Pin a version that is in standard support | aws.amazon.com/eks/pricing |
| EKS Auto Mode | Per-instance management fee with no Spot discount (~12% of On-Demand, **unverified**) | aws.amazon.com/eks/pricing; cloudburn.io |
| NAT Gateway | $0.045/hr + $0.045/GB | aws.amazon.com/vpc/pricing |
| Public IPv4 | $0.005/IP-hr (~$3.60/mo each) | AWS blog: public IPv4 charge |
| Spot t3.medium | ~$0.015–0.018/hr | doit.com; holori.com |
| Spot t4g.medium | ~$0.015–0.026/hr | holori.com |
| fck-nat on t4g.nano | ~$3/mo, no per-GB fee (5 Gbps, ~5 min failover) | github.com/AndrewGuenther/fck-nat |
| S3 / DynamoDB gateway endpoints | Free | — |
| Interface endpoints | ~$0.01/AZ-hr + $0.01/GB | aws.amazon.com/privatelink/pricing |
| Amazon Managed Prometheus | ~$0.90 per 10M samples (40M free) | aws.amazon.com/prometheus/pricing |
| Amazon Managed Grafana | $9/editor, $5/viewer per month | monitoringcost.com |

**Implication:** with a budget under $50/mo, the cluster must be ephemeral. Spin it up for a work session, then destroy it. fck-nat and gateway endpoints keep networking costs low. The persistent footprint is only the state backend plus DNS.

### Tooling status (2025–2026)

- **Pod Identity vs. IAM Roles for Service Accounts (IRSA):** Pod Identity is the default for new clusters. It supports attribute-based access control (ABAC) session tags and, since June 2025, native cross-account access. IRSA is still required for Fargate and for Kubernetes outside EKS. The v21 Karpenter submodule of terraform-aws-modules/eks dropped IRSA. *For this project, knowing both and explaining when to use each is the identity story.*
- **Observability:** Grafana Agent reached end of life (EOL) on 2025-11-01 and Promtail on 2026-03-02. Their replacement is **Grafana Alloy**, which is based on the OpenTelemetry Collector. The LGTM stack is Loki, Grafana, Tempo, and Mimir. The 2026 status of kube-prometheus-stack is unverified.
- **Chaos:** Chaos Mesh (v2.8.6, Oct 2026) and LitmusChaos (3.33.0, Oct 2026) are both Cloud Native Computing Foundation (CNCF) Incubating projects and active. AWS Fault Injection Service (FIS) has `aws:eks:pod-*` actions, which don't work on Fargate.
- **Policy:** Kyverno reached CNCF Graduated status in March 2026 and is moving toward Common Expression Language (CEL). OPA/Gatekeeper is also CNCF Graduated and supports CEL and ValidatingAdmissionPolicy.
- **Network policy:** VPC CNI ≥1.21.1 supports admin/baseline policies on EC2 Linux nodes. DNS-based policies work only on Auto Mode. Cilium on EC2 is community-supported only, not supported by AWS.
- **GitOps:** Argo CD v3.4.x has a built-in UI. Flux v2.8.x is CNCF Graduated and has been community-run since Weaveworks shut down. Both are maintained.
- **Karpenter vs managed node groups:** a common pattern is a small managed node group for system pods plus Karpenter for workloads. At 1–3 nodes the cost difference is small, so Karpenter's value here is mostly the story it lets you tell (**unverified** for small clusters).

### Reference implementations

- **aws-ia/terraform-aws-eks-blueprints:** now a set of patterns only. It defers to terraform-aws-modules/eks, and support is best-effort.
- **terraform-aws-modules/eks:** v21 (July 2025, requires AWS provider v6).
- **aws-samples/eks-workshop-v2:** active and Terraform-based.
- **Differentiation (inference):** borrow from these, but own the IAM, network, and service level objective (SLO) design, and add incident artifacts. None of the reference repos include incident artifacts.

### What hiring signals point to (blogs and SRE interview guides; Reddit unverified)

- **Generic:** tutorial clones, and Kubernetes treated as the goal rather than a means.
- **Differentiating:**
  - Breaking things on purpose and documenting the recovery.
  - ADRs and written trade-offs.
  - Service level indicators (SLIs) tied to user pain, with error budgets you can actually use.
  - Blameless postmortems whose action items get shipped.
  - Chaos write-ups covering what monitoring caught, what it missed, and what changed afterward.
