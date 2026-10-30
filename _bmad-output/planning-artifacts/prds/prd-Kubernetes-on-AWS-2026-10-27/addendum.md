---
title: "PRD Addendum: Kubernetes-on-AWS"
created: 2026-10-27
updated: 2026-10-27
---

# PRD Addendum: Kubernetes-on-AWS

This addendum holds material that belongs downstream (mostly to the architecture step) or that is too detailed for the PRD body. The source is the brief and the brief's addendum (see `extract-brief.md`).

## Technology choices already made (from the brief)

| Area | Choice | Alternatives considered | Notes |
|---|---|---|---|
| IaC | Terraform | — | Use terraform-aws-modules/eks v21 (requires AWS provider v6) as a reference. Use EKS Blueprints for patterns only. |
| NAT | fck-nat on t4g.nano | Managed NAT Gateway ($0.045/hr + $0.045/GB) | ~$3/month, no per-GB fee, ~5 min failover. |
| Network policy | VPC CNI network policies | Cilium, rejected because it has only community support on EC2 nodes | v1.21.1 or later supports admin and baseline policies on EC2 Linux nodes. |
| Pod identity | EKS Pod Identity | IRSA, covered in an ADR | IRSA is still required for Fargate and non-EKS clusters. |
| GitOps | Argo CD 3.4.x | Flux 2.8.x | — |
| Edge SSO | oauth2-proxy (or equivalent) with Cognito as the IdP | — | The cloud-native version of the operator's earlier Apache and mod_auth_openidc project at CGI. |
| Database | RDS db.t4g.micro with IAM DB auth | In-cluster Postgres with S3 backup; DynamoDB | In-cluster Postgres was rejected because the operator wanted hands-on time with a managed AWS service. DynamoDB was rejected because it has no database DR story. |
| Telemetry collector | Grafana Alloy | — | Grafana Agent reached end of life on 2025-11-01 and Promtail on 2026-03-02. |
| Hardening | kube-bench, Pod Security Standards, Kyverno | OPA/Gatekeeper | Kyverno became a CNCF Graduated project in March 2026 and is moving to CEL. |
| Local learning | kind | — | Used for day-to-day learning. Recorded incidents run on real EKS. |

**Unverified research to re-check:**
- The 2026 status of kube-prometheus-stack.
- Karpenter's value for small clusters.

## Decisions handed to the architecture step

- **SLO history store (FR-19):** Amazon Managed Prometheus (~$0.90 per 10M samples ingested, with 40M samples free; verify the free-tier terms), the Grafana Cloud free tier, or export to S3.
- **Fault-injection tool (FR-25):** Chaos Mesh v2.8.6, LitmusChaos 3.33.0, or AWS FIS `aws:eks:pod-*` actions.
- **Gateway API implementation (FR-14):** to be decided, with the choice recorded in the ingress ADR.
- **Where TLS certificates live (FR-2):** in the Persistent Footprint, or issued during each Rebuild.
- **Registrar and domain name (FR-1, FR-2):** see PRD §10, Open Question 1, and the Route 53 registration pitfall below.

## RDS snapshot mechanics (FR-16, FR-22)

- **Snapshot identifier:** each `terraform destroy` needs a unique final snapshot identifier. A naive timestamp in the identifier is recomputed on every apply. That causes a perpetual Terraform diff and can force RDS replacement in the middle of a Session. Fix: pin the identifier for the lifetime of the Session, or set `ignore_changes` on it.
- **Restore lookup:** Rebuild must restore from the latest snapshot and fall back to an empty database on the first apply. An `aws_db_snapshot` data source with `most_recent = true` errors when no snapshot matches, so use a lookup that tolerates an empty result (for example, a list data source with a conditional).
- **Restore time:** adds about 10–20 minutes to the Rebuild, which takes 30–45 minutes in total.
- **RPO:** 0 for a planned Teardown, because of the final snapshot. After an unplanned failure, RPO is the time since the last automated backup.
- **Snapshot retention:** RDS allows 100 manual snapshots per region by default, and each final snapshot adds storage cost. Automatically delete all final snapshots except the 5 most recent.
- **Automated backups (FR-22):** RDS deletes automated backups when the instance is destroyed unless `delete_automated_backups = false` is set. Retained backups then expire at the end of their normal retention period.

## Pitfalls and sizing notes flagged in review

- **Controller-created resources (FR-31):** the AWS Load Balancer Controller, the EBS CSI driver, and ExternalDNS create AWS resources that Terraform doesn't track. Teardown must:
  1. Delete the in-cluster objects (Gateways and Services, and PVCs) and the DNS records that ExternalDNS manages.
  2. Wait for the AWS resources behind them to disappear.
  3. Only then destroy the VPC.

  If Teardown skips these steps, the VPC destroy hangs and orphaned load balancers keep billing.
- **Secrets Manager recovery window (FR-10):** a deleted secret's name stays reserved for 7–30 days, so a Rebuild can't recreate a secret with the same name. Keep secrets in the Persistent Footprint (the PRD's decision), or set `recovery_window_in_days = 0` for any secret that must be ephemeral.
- **Route 53 registration (FR-1, FR-2):** registering a domain creates a hosted zone automatically, and someone must verify the registrant contact email manually. Bootstrap should either adopt that hosted zone or create its own and update the domain's name servers to match.
- **Bootstrap credentials (FR-1, NFR-2):** use IAM Identity Center credentials through an MFA-backed `aws sso login` session. Never create IAM user access keys.
- **Synthetic Probe sizing (FR-32):** an Error Budget of 5 failed requests at a 99% SLO needs at least 500 probe requests per Session. For a 2-hour Session, that's about one request every 10–15 seconds. The probe needs a dedicated Cognito test user, with its credentials kept in Secrets Manager.

## Cost inputs (us-east-1 prices as of October 2026; re-verify before relying on them)

| Item | Price | Notes |
|---|---|---|
| EKS control plane, standard support | $0.10/hr | ~$73/month if always on, so the cluster must be ephemeral. |
| EKS control plane, extended support | $0.60/hr | 6× standard. This is why FR-7 has a pre-flight check. |
| EKS Auto Mode fee | ~12% of On-Demand | Unverified. Auto Mode is out of scope. |
| Public IPv4 | $0.005/IP-hr | ~$3.60/month each. |
| Spot t3.medium | ~$0.015–0.018/hr | — |
| Spot t4g.medium | ~$0.015–0.026/hr | — |
| Interface endpoints | ~$0.01/AZ-hr + $0.01/GB | Use gateway endpoints wherever possible. |
| Amazon Managed Grafana | $9/editor, $5/viewer per month | — |
| Route 53 hosted zone | ~$0.50/month | Persistent Footprint. |
| Domain registration | ~$10–15/year for common TLDs | Unverified. |

## Effort calibration

- **Kubernetes foundations:** about 10–15 hours in M1.
- **App:** capped at 8–10 hours. Anything beyond that goes on the "someday" list.
- **Rebuild:** 30–45 minutes, so EKS work goes in weekend blocks.
