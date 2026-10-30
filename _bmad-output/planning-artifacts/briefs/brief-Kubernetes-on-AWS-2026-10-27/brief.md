---
title: "Product Brief: Kubernetes-on-AWS — Secure, Observable Platform (Terraform)"
status: final
created: 2026-10-27
updated: 2026-10-27
---

# Product Brief: Kubernetes-on-AWS

## Executive Summary

Kubernetes-on-AWS is a secure, observable EKS platform that I build entirely in Terraform, then operate, break on purpose, and recover. It exists to turn three resume claims I can't yet defend into evidence I can walk an interviewer through: Kubernetes operations, networking, and incident leadership. The target roles are DevOps and cloud platform positions, starting with Accenture's Cloud Platform Engineer.

The platform runs a small fitness app behind Cognito SSO, which recreates my CGI OIDC project the cloud-native way. The app keeps its data in RDS, and every change reaches the platform through GitHub Actions and Argo CD. I tear the platform down after each session and rebuild it from nothing. That keeps cost under $50/month and turns every rebuild into a disaster-recovery drill, with a measured recovery time objective (RTO) and recovery point objective (RPO).

The work ships in three milestones over 6–8 weeks, at 2 hours a day:

- **M1:** foundation
- **M2:** delivery and visibility
- **M3:** incidents

I start applying for jobs after M2.

## The Problem

I have two years of enterprise cloud work at CGI, mostly on OCI:

- Terraform and Ansible automation
- centralized identity (LDAP, AD, OIDC SSO)
- Linux hardening to CIS benchmarks
- disaster recovery with defined RTO and RPO targets

The DevOps and cloud platform roles I'm targeting ask for three things I can't yet prove:

- **Kubernetes operations.** This means running clusters day to day, not just deploying one. It covers upgrades, node rotation, and troubleshooting.
- **Networking, including ingress and service mesh.** I have Linux networking knowledge, but I have no network design on record.
- **Incident leadership.** This means taking command of an incident, communicating during it, and making sure it doesn't recur, rather than only fixing it.

My resume lists Kubernetes, AWS VPC, and incident response as competencies, but no experience bullet backs them up. If an interviewer asks "tell me about a time you…" about any of them, I have no real example to give. **The problem: my resume lists claims I can't back with evidence, on AWS, a cloud where I have no professional history.**

I want to walk into a platform interview with real stories. Today I can talk about the MFA flaw I caught at CGI, when DNS records and logs contradicted an assumption in the design. I need stories like that for these three skills.

## Who This Serves

- **Primary: interviewers and hiring managers** for DevOps and cloud platform roles. The anchor role is Accenture's Cloud Platform Engineer posting, and Amazon and AWS are further targets.
  - They'll spend 2–5 minutes scanning the repo, then probe in the interview.
  - They need to see operations, not tutorials: decisions with trade-offs, things that broke, and what changed afterward.
- **Secondary: me.** I need real skill, not a demo. Anything I can't explain under questioning works against me, so the project has to teach me as I build it.

## The Solution

A production-style EKS platform on AWS, built entirely in Terraform. I **operate, break, and recover** it; I don't just deploy it. Every change reaches it through a pipeline, and every failure leaves a written record.

The platform is ephemeral by design. I rebuild it from nothing for each working session, which keeps it within budget and makes every session a disaster-recovery drill. Day-to-day Kubernetes learning happens on a local kind (Kubernetes in Docker) cluster. The real EKS cluster comes up for AWS integration work and for recorded incident runs.

| Milestone | What gets built | What I can then say in an interview |
|---|---|---|
| **M1: Foundation** | A multi-AZ VPC I design myself, IAM with Pod Identity, and an EKS cluster rebuilt from zero with Terraform | "I designed the network and identity model, and I've measured my platform's rebuild time (RTO)." |
| **M2: Delivery & visibility** | GitHub Actions → AWS through OIDC, Terraform changes via pull request, Argo CD, Gateway API ingress, metrics, logs, alerts, and SLOs on the fitness app | "Every change goes through Git. I can see when users are affected, and I can roll back with a revert." **← I start applying here.** |
| **M3: Incidents** | Injected failures (bad deploys, node loss, network faults), each run as an incident. I act as commander, keep a timeline, write a blameless postmortem, and ship the action items. | "I've led N incidents end to end, and here's the fix each one put into the code." |

## What Makes This Different

Most of the parts are standard. The difference is **what the repo shows about the person running it**:

- **Operations, not deployment.** Tutorials and the AWS reference repos (EKS Blueprints, EKS Workshop) stop once the cluster is running. This project starts there, and none of those references include incident records.
- **Incidents caused by real change.** Failures come in through the same pipeline that real outages do.
- **Existing strengths applied on AWS, not just listed:** OIDC federation, least-privilege IAM, CIS-style hardening, and DR with a measured RTO.
- **Decisions written down.** Architecture decision records (ADRs) capture each trade-off, including what I deliberately left out (a full service mesh and multi-environment promotion). It's the same habit as the decision brief I wrote for a director at CGI.

The real advantage is how well I build it and how clearly I write it up. Anyone could build this, but few portfolio projects prove the person can *run* it.

## Success Criteria

**By the end of M2, when I start applying:**

1. One `terraform apply` plus a GitOps sync rebuilds the platform from an empty AWS account to a working, authenticated fitness app, with **no manual steps**.
2. Rebuild RTO is baselined over the first **5 drills** and then reduced, with each improvement and its cause logged.
3. AWS spend stays **under $30/month**, which leaves a $20 buffer within the $50 limit.
4. At least **4 ADRs** are written:
   - network design
   - Pod Identity vs IAM Roles for Service Accounts (IRSA)
   - ingress
   - RDS
5. I apply to **3 tailored roles** within 2 weeks of finishing M2.

**By the end of M3:**

6. I've run **3 incidents** end to end, each with a commander, a timeline, a blameless postmortem, and a shipped action item:
   - a bad deploy
   - an auth outage
   - a network or node failure
7. Every postmortem records what monitoring caught **and what it missed**.

**The real test:** I can answer "tell me about a time you…" about Kubernetes operations, networking, and incident leadership using only this project, without notes.

## Scope

**In:**

- **Network:**
  - a multi-AZ VPC I design myself: public and private subnets, fck-nat, and S3 and DynamoDB gateway endpoints
  - Kubernetes network policies through the VPC CNI
- **Cluster:** EKS on a standard-support version, with a small Spot managed node group. I perform and document upgrades and node rotation.
- **Identity:**
  - EKS Pod Identity, with IRSA covered in an ADR
  - GitHub Actions OIDC to AWS
  - EKS access entries
  - Cognito SSO at the edge
  - RDS IAM authentication
- **Delivery:** Terraform through pull requests, Argo CD for everything in-cluster, and Gateway API ingress.
- **Visibility:** metrics, logs, alerts, and SLOs on the fitness app, with Grafana Alloy as the collector.
- **Hardening:**
  - a CIS EKS benchmark scan with kube-bench
  - Pod Security Standards
  - Kyverno policies, introduced as postmortem action items
- **Workload:** a minimal Python fitness app that logs and lists workouts, backed by RDS. The database is restored from a snapshot on every rebuild.
- **Service mesh (stretch, M3):** an ADR plus a minimal mTLS demo.

**Explicitly out:**

- a full service mesh rollout
- multiple environments, regions, or accounts
- multi-service image pipelines and CI tool comparisons
- EKS Auto Mode and Fargate
- Karpenter, unless time remains after M3
- any frontend, and any app features beyond logging and listing workouts

## Constraints & Risks

- **Budget: under $50/month.** The platform is therefore ephemeral. Only the state backend, DNS, Cognito, and RDS snapshots persist between sessions. I'll pin an EKS version in standard support, because extended support costs 6× as much.
- **Time: 2 hours/day, 7 days/week.** I'm planning on about 12 effective hours a week, which gives roughly 75–90 usable hours in total. Each rebuild takes about 30–45 minutes, including the RDS restore, so EKS work moves into longer weekend blocks.
- **Starting point:** I've used Docker and done Kubernetes tutorials, but I've never operated a cluster. M1 includes about 10–15 hours of Kubernetes foundations, which I'll learn by building platform pieces.
- **Main risk: stalling the way my last Kubernetes course did,** because the work became abstract. The mitigation is problem-first learning:
  - I learn each Kubernetes concept when the platform needs it.
  - Every session ends with something visible, such as a commit, a doc, a dashboard screenshot, or a line in the rebuild log.
- **Scope risk:** polishing the app or adding pillars crowds out the incidents, and the incidents are the strongest differentiator. The mitigation is the "out" list above plus a cap of 8–10 hours on app code.

## Open Questions

- **SLO history across teardowns (for architecture):** every teardown loses the metrics and logs, so SLO history needs to persist somewhere. The options are Amazon Managed Prometheus, Grafana Cloud's free tier, or exporting to S3.

## Vision

Once this scope lands, the natural next steps are:

- the items deferred above: multi-account with AWS Organizations, Karpenter, and a real service mesh once there's a reason for one
- the CKA and AWS Solutions Architect certifications, using the platform as my study lab

The longer aim is the one in my resume summary: moving from managed-service delivery to a team where I **own AWS infrastructure for the long term**. This project is my first rehearsal of that ownership.
