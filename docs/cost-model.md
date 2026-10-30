# Cost model (Persistent Footprint)

NFR-1: actual spend stays **under $30/month**, with a **$50 hard cap**. AWS Budgets alert at $30
actual and $45 forecast.

This table covers only what survives Teardown (L0 and L1). Whatever the Persistent Footprint does
not use is the budget for Sessions (EKS, nodes, NAT, RDS, ALB while a Session runs).

All figures are **estimates** from us-east-1 list prices, made before anything was deployed. The
story that creates each item replaces its estimate with a measured or better-founded figure and
changes its Status to `live`. Every new Persistent Footprint item adds a row here in the same PR.

| Item | Layer | Expected $/month | Basis | Status |
| --- | --- | --- | --- | --- |
| S3 state bucket (versioned, plus `evidence/`) | L0 | 0.05 | < 1 GB at $0.023/GB-month plus requests | planned (story 1.2) |
| AWS Budgets ($30 actual, $45 forecast) | L0 | 0.00 | First two action-free budgets are free | planned (story 1.2) |
| SNS topic for budget email | L0 | 0.00 | Email notifications within the SNS free tier | planned (story 1.2) |
| SSM parameters (`/k8s-on-aws/...`) | L0, L1 | 0.00 | Standard-tier parameters are free | planned (story 1.2) |
| Route 53 hosted zone | L1 | 0.50 | $0.50 per hosted zone; queries negligible | planned (story 1.4) |
| Domain `yahiahussein.dev`, amortised | L1 | 1.25 | About $15/year `.dev` registration, divided by 12 | planned (story 1.4) |
| Cognito user pool | L1 | 0.00 | A handful of users, inside the free MAU allowance | planned (story 1.5) |
| ECR repositories (`app`, `probe`) | L1 | 0.20 | Up to 20 images each, about 2 GB at $0.10/GB-month | planned (story 1.6) |
| Secrets Manager, per secret ($0.40 each) | L1 | 1.60 | 4 secrets: `oauth2-proxy/client-secret`, `oauth2-proxy/cookie-secret`, `probe/credentials`, one `app-users/<username>`; each additional App User adds $0.40/month | planned (story 1.5, 1.6) |
| Amazon Managed Service for Prometheus workspace | L1 | 3.80 | ≤ 40M samples/month at $0.90 per 10M, plus storage and queries | planned (story 4.2) |
| CloudWatch log group (14-day retention) | L1 | 1.00 | About 2 GB/month ingested at $0.50/GB, plus storage | planned (story 4.3) |
| SNS topic for alerts | L1 | 0.00 | Email notifications within the SNS free tier | planned (story 4.4) |
| RDS final snapshots (5 kept) and the retained automated backup | L1 (Layer=persistent, retagged by Teardown, AD-6) | 0.50 | A few GB of snapshot storage at $0.095/GB-month | planned (story 2.6, 2.7) |
| **Total (estimate)** | | **8.90** | Against the **$30/month** target; leaves about $21 for Sessions | |
