---
title: "Extract: Kubernetes-on-AWS brief + addendum (input to PRD)"
created: 2026-10-27
sources:
  - B = _bmad-output/planning-artifacts/briefs/brief-Kubernetes-on-AWS-2026-10-27/brief.md
  - A = _bmad-output/planning-artifacts/briefs/brief-Kubernetes-on-AWS-2026-10-27/addendum.md
---

# Extract: Kubernetes-on-AWS

Source tags: **[B §Section]** = brief.md, **[A §Section]** = addendum.md. Quotes are close to the source; nothing added beyond what the sources say. Items marked **GAP** or **CONFLICT** are extractor notes, not source content.

## 1. Vision and purpose

- "A secure, observable EKS platform that I build entirely in Terraform, then operate, break on purpose, and recover." [B §Executive Summary]
- Purpose: "turn three resume claims I can't yet defend into evidence I can walk an interviewer through: Kubernetes operations, networking, and incident leadership." [B §Executive Summary]
- Target roles: "DevOps and cloud platform positions, starting with Accenture's Cloud Platform Engineer." [B §Executive Summary]
- Problem statement: "my resume lists claims I can't back with evidence, on AWS, a cloud where I have no professional history." [B §The Problem]
- The three gaps: Kubernetes operations ("running clusters day to day, not just deploying one ... upgrades, node rotation, and troubleshooting"); networking incl. ingress and service mesh ("no network design on record"); incident leadership ("taking command of an incident, communicating during it, and making sure it doesn't recur"). [B §The Problem]
- Existing strengths from CGI (mostly OCI): Terraform and Ansible automation; centralized identity (LDAP, AD, OIDC SSO); Linux hardening to CIS benchmarks; DR with defined RTO/RPO targets. [B §The Problem]
- Wants "real stories" like "the MFA flaw I caught at CGI, when DNS records and logs contradicted an assumption in the design." [B §The Problem]
- Solution: "A production-style EKS platform on AWS, built entirely in Terraform. I operate, break, and recover it; I don't just deploy it. Every change reaches it through a pipeline, and every failure leaves a written record." [B §The Solution]
- Longer-term vision: next steps are the deferred items (multi-account with AWS Organizations, Karpenter, real service mesh "once there's a reason for one") and CKA + AWS Solutions Architect certs "using the platform as my study lab"; longer aim is to "own AWS infrastructure for the long term. This project is my first rehearsal of that ownership." [B §Vision]

## 2. Goals and success criteria

Milestones: three milestones "over 6–8 weeks, at 2 hours a day": M1 foundation, M2 delivery and visibility, M3 incidents. "I start applying for jobs after M2." [B §Executive Summary]

Milestone outcomes [B §The Solution, table]:
- **M1: Foundation** - multi-AZ VPC designed by hand, IAM with Pod Identity, EKS cluster rebuilt from zero with Terraform. Interview line: "I designed the network and identity model, and I've measured my platform's rebuild time (RTO)."
- **M2: Delivery & visibility** - GitHub Actions to AWS through OIDC, Terraform changes via PR, Argo CD, Gateway API ingress, metrics, logs, alerts, SLOs on the fitness app. Interview line: "Every change goes through Git. I can see when users are affected, and I can roll back with a revert." "I start applying here."
- **M3: Incidents** - injected failures (bad deploys, node loss, network faults), each run as an incident with commander, timeline, blameless postmortem, shipped action items. Interview line: "I've led N incidents end to end, and here's the fix each one put into the code."

Success criteria by end of M2 [B §Success Criteria]:
1. "One `terraform apply` plus a GitOps sync rebuilds the platform from an empty AWS account to a working, authenticated fitness app, with **no manual steps**."
2. "Rebuild RTO is baselined over the first **5 drills** and then reduced, with each improvement and its cause logged."
3. "AWS spend stays **under $30/month**, which leaves a $20 buffer within the $50 limit."
4. "At least **4 ADRs**": network design; Pod Identity vs IRSA; ingress; RDS.
5. "I apply to **3 tailored roles** within 2 weeks of finishing M2."

Success criteria by end of M3 [B §Success Criteria]:
6. "**3 incidents** end to end, each with a commander, a timeline, a blameless postmortem, and a shipped action item": a bad deploy; an auth outage; a network or node failure.
7. "Every postmortem records what monitoring caught **and what it missed**."

The real test: "I can answer 'tell me about a time you…' about Kubernetes operations, networking, and incident leadership using only this project, without notes." [B §Success Criteria]

Other numbers:
- Budget "under $50/month" [B §Executive Summary; B §Constraints & Risks]
- RTO/RPO: "measured recovery time objective (RTO) and recovery point objective (RPO)" [B §Executive Summary]; "The measured restore time gives the RTO, and the gap since the last snapshot gives the RPO." [A §Workload and data design notes]. **GAP:** no numeric RTO or RPO target is stated anywhere.
- Interviewers "spend 2–5 minutes scanning the repo" [B §Who This Serves]

## 3. Users and stakeholders

- **Primary: interviewers and hiring managers** for DevOps and cloud platform roles; anchor = Accenture Cloud Platform Engineer posting; "Amazon and AWS are further targets." They "spend 2–5 minutes scanning the repo, then probe in the interview" and "need to see operations, not tutorials: decisions with trade-offs, things that broke, and what changed afterward." [B §Who This Serves]
- **Secondary: me (the builder).** "I need real skill, not a demo. Anything I can't explain under questioning works against me, so the project has to teach me as I build it." [B §Who This Serves]
- **App end users** (implicit): authenticated users of the fitness app via Cognito; "users persist across rebuilds." [A §Workload and data design notes]

Anchor posting requirement-vs-evidence map [A §Anchor posting]:
| Requirement | Status | Project must produce |
|---|---|---|
| Strong Linux networking | Partial | "VPC designed by hand, plus a debugging write-up showing a packet's path from the internet through ingress to a pod" |
| IaC: Terraform / Ansible / CloudFormation | Strength | "Terraform module and state design as the backbone of the platform" |
| Kubernetes operations | Gap | "upgrades, node rotation, troubleshooting, capacity" |
| Service mesh / ingress | Gap | "Ingress or Gateway API controller, plus a service-mesh decision recorded as an ADR" |
| Incident leadership | Gap | "Simulated incidents run with roles and communications, then blameless postmortems with action items that get shipped" |
| DR / BCP execution | Strength to translate | "Rebuild of the platform with a measured, documented RTO" |

## 4. Capabilities and features

### Infra / networking
- "A multi-AZ VPC I design myself: public and private subnets, fck-nat, and S3 and DynamoDB gateway endpoints." [B §Scope In - Network]
- "Kubernetes network policies through the VPC CNI." [B §Scope In - Network]
- "EKS on a standard-support version, with a small Spot managed node group." [B §Scope In - Cluster]
- "I perform and document upgrades and node rotation." [B §Scope In - Cluster]
- Gateway API ingress. [B §Scope In - Delivery; B §The Solution M2]
- Debugging write-up of "a packet's path from the internet through ingress to a pod". [A §Anchor posting]
- Kubernetes operations evidence incl. "troubleshooting, capacity". [A §Anchor posting]
- Service mesh (stretch, M3): "an ADR plus a minimal mTLS demo." [B §Scope In]

### Security / identity
- "EKS Pod Identity, with IRSA covered in an ADR." [B §Scope In - Identity]
- "GitHub Actions OIDC to AWS." [B §Scope In - Identity]
- "EKS access entries." [B §Scope In - Identity]
- "Cognito SSO at the edge." [B §Scope In - Identity]; OIDC SSO in front of the app "(oauth2-proxy or equivalent), with Amazon Cognito as the identity provider." [A §Workload and data design notes]
- "RDS IAM authentication." [B §Scope In - Identity]; app pod uses Pod Identity to get an IAM role then authenticates to RDS with IAM DB auth, "so no static DB password is needed." [A §Workload and data design notes]
- "Secrets Manager covers any remaining secrets (e.g., the oauth2-proxy cookie secret)." [A §Workload and data design notes]
- Hardening: "a CIS EKS benchmark scan with kube-bench"; "Pod Security Standards"; "Kyverno policies, introduced as postmortem action items." [B §Scope In - Hardening]
- Least-privilege IAM, CIS-style hardening applied on AWS. [B §What Makes This Different]

### App
- "A minimal Python fitness app that logs and lists workouts, backed by RDS." [B §Scope In - Workload]
- Two features: "log a workout" and "list my workouts". Effort "capped at about 8–10 hours, and anything beyond that goes on a 'someday' list." [A §Workload and data design notes]
- Recreates "my CGI OIDC project the cloud-native way" / "cloud-native version of the CGI mod_auth_openidc / Apache project." [B §Executive Summary; A §Workload and data design notes]

### Data
- "Amazon RDS (db.t4g.micro), created and destroyed with the platform." [A §Workload and data design notes]
- "The database is restored from a snapshot on every rebuild." [B §Scope In - Workload]
- "Destroy takes a final snapshot. Apply restores from the latest snapshot." [A §Workload and data design notes]
- Terraform gotchas to resolve: unique final snapshot identifiers per destroy ("a naive timestamp causes a perpetual diff"); restore must find latest snapshot; "The first apply has no snapshot to restore from." [A §Workload and data design notes]

### CI/CD / GitOps
- "Every change reaches the platform through GitHub Actions and Argo CD." [B §Executive Summary]
- "Terraform through pull requests, Argo CD for everything in-cluster." [B §Scope In - Delivery]
- Roll back "with a revert." [B §The Solution M2]
- Failures injected "through the same pipeline that real outages do." [B §What Makes This Different]

### Observability
- "Metrics, logs, alerts, and SLOs on the fitness app, with Grafana Alloy as the collector." [B §Scope In - Visibility]
- "I can see when users are affected." [B §The Solution M2]
- SLIs "tied to user pain, with error budgets you can actually use" (hiring signal). [A §What hiring signals point to]
- SLO history must persist across teardowns (open question). [B §Open Questions]

### DR / teardown-rebuild
- "I tear the platform down after each session and rebuild it from nothing." Every rebuild = "a disaster-recovery drill, with a measured RTO and RPO." [B §Executive Summary]
- One `terraform apply` + GitOps sync, empty account to working authenticated app, no manual steps. [B §Success Criteria 1]
- RTO baselined over first 5 drills, then reduced, improvements and causes logged ("rebuild log"). [B §Success Criteria 2; B §Constraints & Risks]
- Persistent between sessions: "the state backend, DNS, Cognito, and RDS snapshots." [B §Constraints & Risks]

### Chaos / incident drills
- Injected failures: "bad deploys, node loss, network faults". [B §The Solution M3]
- Required 3 incidents: bad deploy, auth outage, network or node failure. [B §Success Criteria 6]
- Each incident: I act as commander, keep a timeline, write blameless postmortem, ship action items. [B §The Solution M3]
- "Simulated incidents run with roles and communications." [A §Anchor posting]
- Postmortems record what monitoring caught and missed [B §Success Criteria 7]; chaos write-ups cover "what monitoring caught, what it missed, and what changed afterward." [A §What hiring signals point to]
- Kyverno policies arrive as postmortem action items. [B §Scope In - Hardening]
- Recorded incident runs happen on the real EKS cluster. [B §The Solution]

### Docs / evidence
- ADRs for each trade-off, "including what I deliberately left out (a full service mesh and multi-environment promotion)." [B §What Makes This Different]
- Minimum 4 ADRs: network design, Pod Identity vs IRSA, ingress, RDS. [B §Success Criteria 4]; plus service-mesh ADR (stretch). [B §Scope In]
- Documented upgrades and node rotation. [B §Scope In - Cluster]
- Rebuild log; "Every session ends with something visible, such as a commit, a doc, a dashboard screenshot, or a line in the rebuild log." [B §Constraints & Risks]
- Incident timelines and blameless postmortems. [B §The Solution M3]
- Packet-path debugging write-up. [A §Anchor posting]
- Documented RTO. [A §Anchor posting]
- Repo must be scannable in 2–5 minutes. [B §Who This Serves]

## 5. Constraints

- **Budget:** "under $50/month. The platform is therefore ephemeral." Pin EKS version in standard support "because extended support costs 6× as much." [B §Constraints & Risks]. Target spend under $30/month. [B §Success Criteria 3]
- **Time:** "2 hours/day, 7 days/week"; "about 12 effective hours a week ... roughly 75–90 usable hours in total." [B §Constraints & Risks]; 6–8 weeks. [B §Executive Summary]
- **Rebuild duration:** "about 30–45 minutes, including the RDS restore, so EKS work moves into longer weekend blocks." [B §Constraints & Risks]; "Expect about 10–20 minutes of extra rebuild time for the RDS restore." [A §Workload and data design notes]
- **Starting skill:** used Docker and done tutorials, "never operated a cluster"; M1 includes "about 10–15 hours of Kubernetes foundations." [B §Constraints & Risks]
- **App effort cap:** 8–10 hours. [B §Constraints & Risks; A §Workload and data design notes]
- **Tooling:** "built entirely in Terraform" [B §Executive Summary]; local kind cluster for day-to-day learning, real EKS for AWS integration and recorded incidents. [B §The Solution]
- **Region:** prices are "snapshots for us-east-1." [A §Research digest]. **GAP:** region is never stated as a constraint, only implied by the pricing snapshot; single region required (multi-region is out). [B §Scope Out]
- **Single account / single environment** (multi-env/region/account out). [B §Scope Out]

## 6. Explicit scope

**In** [B §Scope In]: multi-AZ hand-designed VPC (public/private subnets, fck-nat, S3 + DynamoDB gateway endpoints); network policies via VPC CNI; EKS standard-support version with small Spot managed node group; upgrades and node rotation; Pod Identity (IRSA in ADR); GitHub Actions OIDC; EKS access entries; Cognito SSO at edge; RDS IAM auth; Terraform via PR; Argo CD; Gateway API ingress; metrics/logs/alerts/SLOs with Grafana Alloy; kube-bench CIS scan; Pod Security Standards; Kyverno policies as postmortem action items; minimal Python fitness app on RDS restored from snapshot each rebuild.

**Stretch (M3):** service mesh ADR + minimal mTLS demo. [B §Scope In]

**Out** [B §Scope Explicitly out]:
- a full service mesh rollout
- multiple environments, regions, or accounts
- multi-service image pipelines and CI tool comparisons
- EKS Auto Mode and Fargate
- Karpenter, "unless time remains after M3"
- any frontend, and any app features beyond logging and listing workouts

**Deferred / phase 2** [B §Vision]: multi-account with AWS Organizations; Karpenter; real service mesh "once there's a reason for one"; CKA and AWS Solutions Architect certifications. App extras go to a "someday" list. [A §Workload and data design notes]

**Rejected alternatives** [A §Workload and data design notes]: in-cluster Postgres with S3 backup ("user preferred hands-on time with a managed AWS service"); DynamoDB ("no database DR story").

## 7. Non-functional requirements

- **Security:** OIDC federation; least-privilege IAM; CIS-style hardening [B §What Makes This Different]; no static DB password [A §Workload and data design notes]; remaining secrets in Secrets Manager [A]; kube-bench CIS EKS scan, Pod Security Standards, Kyverno, network policies [B §Scope In]; authenticated app [B §Success Criteria 1].
- **Cost:** < $30/month actual, < $50/month hard limit [B §Success Criteria 3; B §Constraints & Risks]; ephemeral cluster; standard-support EKS only; fck-nat and gateway endpoints "keep networking costs low" [A §Research digest Implication]; Spot nodes [B §Scope In].
- **Reliability / DR:** fully automated rebuild with no manual steps; measured and reduced RTO; RPO = gap since last snapshot; multi-AZ VPC [B §Success Criteria; B §Scope In; A §Workload and data design notes]; Cognito users persist across rebuilds [A].
- **Performance:** rebuild about 30–45 min including RDS restore [B §Constraints & Risks]. **GAP:** no app latency/throughput or SLO target values are stated.
- **Observability:** SLOs on the fitness app; alerts; detect user impact [B §Scope In; B §The Solution M2].

## 8. Risks, open questions, assumptions

**Risks** [B §Constraints & Risks]:
- "Main risk: stalling the way my last Kubernetes course did, because the work became abstract." Mitigation: problem-first learning; learn each concept when the platform needs it; every session ends with something visible.
- "Scope risk: polishing the app or adding pillars crowds out the incidents, and the incidents are the strongest differentiator." Mitigation: the out list plus the 8–10 hour app cap.
- RDS Terraform gotchas (snapshot IDs, latest-snapshot lookup, first apply with no snapshot). [A §Workload and data design notes]

**Open questions:**
- "SLO history across teardowns (for architecture): every teardown loses the metrics and logs, so SLO history needs to persist somewhere. The options are Amazon Managed Prometheus, Grafana Cloud's free tier, or exporting to S3." [B §Open Questions]

**Assumptions / unverified items** [A §Research digest]:
- Prices are us-east-1 snapshots; "Check them again before committing to a cost model."
- EKS Auto Mode fee "~12% of On-Demand, unverified."
- "The 2026 status of kube-prometheus-stack is unverified."
- Karpenter value for small clusters "unverified".
- Hiring signals: "Reddit unverified"; reference-repo differentiation is "(inference)".
- Anchor posting table is marked "(draft)". [A §Anchor posting]

**Extractor-noted gaps and contradictions:**
- **CONFLICT (persistent footprint):** B §Constraints & Risks says "the state backend, DNS, Cognito, and RDS snapshots" persist; A §Research digest Implication says "The persistent footprint is only the state backend plus DNS."
- **CONFLICT (incident types):** B §The Solution M3 lists "bad deploys, node loss, network faults"; B §Success Criteria 6 requires "a bad deploy, an auth outage, a network or node failure". Auth outage appears only in the success criteria.
- **GAP:** no numeric RTO or RPO targets; no SLO/SLI target values or error-budget policy.
- **GAP:** chaos/fault-injection tool not chosen (Chaos Mesh, LitmusChaos, AWS FIS listed in A only as status notes).
- **GAP:** "capacity" (A §Anchor posting) and the packet-path write-up (A) are not in the brief's scope list.
- **GAP:** Secrets Manager appears only in A, not in B §Scope.
- **GAP:** DNS domain/Route 53 is mentioned only as persisting, not specified; region not explicitly fixed.
- **Ambiguity:** Karpenter is "out ... unless time remains after M3" [B §Scope] yet also listed as deferred next step [B §Vision].
- **Ambiguity:** M3 interview line says "N incidents" while success criterion fixes 3.
- **Ambiguity:** RDS is "created and destroyed with the platform" [A] while RDS snapshots persist [B]; consistent, but cost of snapshot storage not estimated.

## 9. Technology and implementation choices (for PRD addendum)

**Chosen / named in scope:**
- Terraform (entire platform; Terraform via PRs) [B §Executive Summary; B §Scope In]
- terraform-aws-modules/eks v21 (July 2025, requires AWS provider v6) as reference; EKS Blueprints is "patterns only", defers to it [A §Reference implementations]. **Note:** A lists these as references, not an explicit choice.
- Amazon EKS, standard-support version pinned; small Spot managed node group [B §Scope In]
- VPC CNI (network policies; ≥1.21.1 supports admin/baseline policies on EC2 Linux nodes) [B §Scope In; A §Tooling status]
- fck-nat (on t4g.nano, ~$3/mo, no per-GB fee, 5 Gbps, ~5 min failover) [B §Scope In; A §Cost inputs]
- S3 and DynamoDB gateway endpoints (free) [B §Scope In; A §Cost inputs]
- EKS Pod Identity (default for new clusters; ABAC session tags; native cross-account since June 2025); IRSA in ADR (still required for Fargate and non-EKS) [B §Scope In; A §Tooling status]
- EKS access entries [B §Scope In]
- GitHub Actions with OIDC to AWS [B §Scope In]
- Argo CD (v3.4.x, built-in UI) for everything in-cluster; Flux v2.8.x noted as alternative [B §Scope In; A §Tooling status]
- Gateway API ingress [B §Scope In]
- Amazon Cognito as IdP; oauth2-proxy "or equivalent" for edge OIDC SSO [B §Scope In; A §Workload and data design notes]
- Amazon RDS db.t4g.micro, IAM DB auth, final snapshot on destroy, restore from latest snapshot (e.g., `aws_db_snapshot` with `most_recent`) [A §Workload and data design notes]
- AWS Secrets Manager [A §Workload and data design notes]
- Grafana Alloy collector (replacement for Grafana Agent EOL 2025-11-01 and Promtail EOL 2026-03-02; OTel Collector-based); LGTM stack (Loki, Grafana, Tempo, Mimir) noted [B §Scope In; A §Tooling status]
- SLO history store options: Amazon Managed Prometheus (~$0.90 per 10M samples, 40M free), Grafana Cloud free tier, or S3 export [B §Open Questions; A §Cost inputs]
- kube-bench (CIS EKS benchmark), Pod Security Standards, Kyverno (CNCF Graduated March 2026, moving to CEL); OPA/Gatekeeper noted [B §Scope In; A §Tooling status]
- kind for local learning [B §The Solution]
- Python for the app [B §Scope In]
- Chaos options: Chaos Mesh v2.8.6, LitmusChaos 3.33.0, AWS FIS `aws:eks:pod-*` actions (not on Fargate) [A §Tooling status]
- Service mesh mTLS demo (no mesh product named) [B §Scope In]

**Cost inputs (us-east-1 snapshots)** [A §Cost inputs]: EKS control plane standard $0.10/hr (~$73/mo always-on); extended $0.60/hr; NAT Gateway $0.045/hr + $0.045/GB; public IPv4 $0.005/IP-hr (~$3.60/mo each); Spot t3.medium ~$0.015–0.018/hr; Spot t4g.medium ~$0.015–0.026/hr; interface endpoints ~$0.01/AZ-hr + $0.01/GB; Amazon Managed Grafana $9/editor, $5/viewer per month.

**Excluded tech:** EKS Auto Mode, Fargate, Karpenter (unless time after M3), Cilium (community-supported only on EC2), DNS-based network policies (Auto Mode only). [B §Scope Out; A §Tooling status]

## 10. Qualitative intent

- "Operations, not deployment." The project "starts" where tutorials and AWS reference repos "stop once the cluster is running." [B §What Makes This Different]
- "Most of the parts are standard. The difference is what the repo shows about the person running it." "Anyone could build this, but few portfolio projects prove the person can run it." [B §What Makes This Different]
- "The real advantage is how well I build it and how clearly I write it up." [B §What Makes This Different]
- Show "decisions with trade-offs, things that broke, and what changed afterward" - "operations, not tutorials." [B §Who This Serves]
- "Incidents caused by real change" through the real pipeline. [B §What Makes This Different]
- Demo story: designed the network and identity model; measured rebuild time; every change through Git; see user impact; roll back with a revert; led incidents end to end with a fix in code for each. [B §The Solution table]
- Ephemeral "by design": every session a DR drill. [B §The Solution]
- Honest and defensible: "Anything I can't explain under questioning works against me." [B §Who This Serves]
- Avoid "tutorial clones, and Kubernetes treated as the goal rather than a means." [A §What hiring signals point to]
- Writing habit mirrors "the decision brief I wrote for a director at CGI." [B §What Makes This Different]
- Must be skimmable by an interviewer in 2–5 minutes. [B §Who This Serves]
