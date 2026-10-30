# Conventions

These conventions restate the "Consistency Conventions" and "Stack" sections of the architecture
spine (`_bmad-output/planning-artifacts/architecture/architecture-Kubernetes-on-AWS-2026-10-28/ARCHITECTURE-SPINE.md`).
If this file and the spine ever disagree, the spine wins and this file is fixed.

## Naming

| What | Convention | Example |
| --- | --- | --- |
| AWS resource names | Prefix `k8s-on-aws-` | `k8s-on-aws-state` |
| Ephemeral IAM roles (L2) | Prefix `k8s-on-aws-eph-` | `k8s-on-aws-eph-external-dns` |
| SSM parameters (cross-root handoff, AD-3) | `/k8s-on-aws/<layer>/<name>`, where `<layer>` is `bootstrap`, `persistent`, `core` or `session` | `/k8s-on-aws/persistent/zone_id` |
| Secrets Manager secrets (AD-17) | `k8s-on-aws/<consumer>/<name>` | `k8s-on-aws/oauth2-proxy/cookie-secret` |
| EKS cluster name | The constant `k8s-on-aws` | `k8s-on-aws` |
| RDS final snapshots (AD-9) | `k8s-on-aws-final-<session_id>` | `k8s-on-aws-final-s20261028-1022` |

Cross-root values travel only through those SSM parameters, read with the `aws_ssm_parameter`
data source. `terraform_remote_state` is forbidden.

## session_id

`s` followed by the UTC time `YYYYMMDD-HHMM`, all lowercase, for example `s20261028-1022`.
It must stay valid as an RDS identifier suffix, a Kubernetes label value and a Prometheus label
value, so it never contains uppercase letters, underscores or colons.

## Tags

Every AWS resource carries:

| Tag | Values | Notes |
| --- | --- | --- |
| `Project` | `k8s-on-aws` | Always |
| `Layer` | `bootstrap`, `persistent`, `ephemeral` | Always (AD-6) |
| `Session` | `<session_id>` | Ephemeral resources only |
| `ManagedBy` | `terraform`, `lbc`, `external-dns` | Who created it |

Terraform applies tags through provider `default_tags`. The AWS Load Balancer Controller applies
them through `--default-tags`, with values taken from the bridge annotations. Tags are the
Teardown contract: the post-Teardown check finds leftovers by `Layer=ephemeral`.

The `Layer` tag maps to the architecture layers as follows:

| Architecture layer | `Layer` tag |
| --- | --- |
| L0 Bootstrap | `bootstrap` |
| L1 Persistent | `persistent` |
| L2 Ephemeral core, L3 Ephemeral GitOps handoff, L4 In-cluster | `ephemeral` |

## Kubernetes namespaces

| Namespace | Holds |
| --- | --- |
| `argocd` | Argo CD |
| `gateway` | The `public` Gateway |
| `app` | The App, oauth2-proxy and the DB Jobs (`db-init`, `migrate`) |
| `probe` | The Synthetic Probe |
| `observability` | Alloy, Grafana |
| `security` | kube-bench |
| `external-dns` | ExternalDNS |
| `external-secrets` | External Secrets Operator |
| `kyverno` | Kyverno |
| `kube-system` | AWS add-ons and the AWS Load Balancer Controller |

## Kubernetes labels

Every first-party object carries the recommended labels `app.kubernetes.io/name`,
`app.kubernetes.io/part-of` and `app.kubernetes.io/component`, with
`app.kubernetes.io/part-of=k8s-on-aws`.

## Version pinning

Every provider, module, chart and image is pinned to an **exact** version: no ranges, no `~>`,
no `latest`, no floating tags. GitHub Actions are pinned to a full commit SHA. The EKS version is
one variable, and the Rebuild pre-flight requires `describe-cluster-versions` to report
`STANDARD_SUPPORT`.

Current pins (from the architecture's Stack table; update both together):

| Tool | Version |
| --- | --- |
| Terraform CLI | `1.17.0` |
| `hashicorp/aws` provider | `6.70.0` |
| AWS CLI | `>= 2.32` (needed for `aws login`; the CLI is the one tool not pinned exactly) |
| Python | `3.14` |
| uv | `0.13.6` |

The full list of chart, module and image versions lives in the architecture's Stack table.

## Logs

Every first-party service writes JSON lines to stdout. Each line has at least these fields:

| Field | Meaning |
| --- | --- |
| `ts` | RFC 3339 UTC timestamp |
| `level` | Log level |
| `msg` | Message |
| `session_id` | The current `session_id` |

## Commits

- [Conventional Commits](https://www.conventionalcommits.org/) for every commit:
  `<type>(<scope>): <summary>`.
- `fault(<incident>): …` for fault injections (AD-14), for example `fault(bad-deploy): …`.
- `fix(pm-<n>): …` for Postmortem Action Items, linking the Postmortem.
- `chore(bot): …` is reserved for `github-actions[bot]`. Bot commits may touch only image-tag bumps
  under `gitops/workloads/` and `docs/rebuild-log/`, and they never trigger `pr-plan`,
  `persistent-apply` or `ephemeral-apply` (AD-25).

## Workflows

The workflow list is closed: `pr-plan`, `persistent-apply`, `ephemeral-apply`, `image-build`,
`rebuild` (dispatch), `teardown` (dispatch), `session-watchdog` (schedule). New checks become jobs
in one of these workflows, never a new workflow. Runners are `ubuntu-24.04`, and
`ubuntu-24.04-arm` for image builds.

## Docs locations

| What | Where |
| --- | --- |
| Architecture decision records | `docs/adr/NNNN-<slug>.md` ([MADR](https://adr.github.io/madr/) format) |
| Runbooks | `docs/runbooks/` |
| Postmortems | `docs/postmortems/YYYY-MM-DD-<slug>.md` |
| Write-ups | `docs/writeups/` |
| Rebuild Log records | `docs/rebuild-log/<session_id>.json` (written only by Teardown) |
| Component map | `docs/components.md` |
| Cost model | `docs/cost-model.md` |

`docs/components.md` maps every Terraform root and Argo CD app to the ADR or runbook that explains
it, and CI fails on any unlisted component (NFR-6). Every story that adds a Terraform root or an
Argo CD Application/ApplicationSet adds its row in the same PR. Every story that adds a Persistent
Footprint item updates its row in `docs/cost-model.md`.

## Problem journal

Every real problem met on the live Platform is logged in `docs/writeups/_journal.md` **as it
happens**, with the date, the `session_id`, the symptom and the first commands run. This is
mandatory, not optional: the journal is the raw material for the troubleshooting write-ups (FR-33).
