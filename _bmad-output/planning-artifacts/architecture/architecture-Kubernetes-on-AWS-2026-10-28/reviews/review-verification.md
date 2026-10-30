# Review — Verification lens (ARCHITECTURE-SPINE.md)

- **Reviewed:** 2026-10-28
- **Lens:** checks that each committed decision was reality-checked against current docs, not taken from training data. Stack versions were spot-checked. Most of the effort went into the fit claims inside the ADs.
- **Verdict:** **Mostly sound. Two committed claims do not hold as written** (Alloy → CloudWatch Logs in AD-13, and the RDS-managed secret after a restore in AD-9/AD-10). A third (the AD-6 Teardown check) has a logic gap that will fail every Teardown. Fix these three before the epics start.

## Findings

### F1 — HIGH — Alloy has no CloudWatch Logs writer (AD-13, Logs convention)
- **Claim:** "Alloy forwards them to CloudWatch." / "Logs go to one CloudWatch Logs group in L1."
- **Reality:** Alloy has no native CloudWatch Logs exporter. Its CloudWatch components only read: `otelcol.receiver.awscloudwatch` and `prometheus.exporter.cloudwatch`. The one workable path is CloudWatch Logs' OTLP endpoint `https://logs.us-east-1.amazonaws.com/v1/logs`. It uses SigV4, takes the `x-aws-log-group` and `x-aws-log-stream` headers, and has no query-parameter form. Alloy would reach it through `otelcol.exporter.otlphttp` and `otelcol.auth.sigv4` (service `logs`, region set explicitly). The k8s-monitoring v4 OTLP destination supports `auth.type: sigv4` and `extraHeaders`, so it can be wired that way.
- **Evidence:** https://grafana.com/docs/alloy/latest/reference/components/otelcol/otelcol.receiver.awscloudwatch/ · https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_HTTP_Endpoints_OTLP.html · https://github.com/grafana/k8s-monitoring-helm/blob/main/charts/k8s-monitoring/docs/destinations/otlp.md
- **Fix:** In AD-13, name the mechanism: Alloy `otelcol.exporter.otlphttp` with SigV4 to the CloudWatch OTLP logs endpoint, with the log group and stream (both created in L1) passed as headers. The fallback is the `amazon-cloudwatch-observability` EKS add-on (Fluent Bit). Add a spike to M1 to prove it.

### F2 — HIGH — RDS cannot turn on a managed master secret during a PostgreSQL restore (AD-9, AD-10)
- **Claim:** `manage_master_user_password` is used together with restore from a final snapshot or PITR from retained backups.
- **Reality:** AWS docs say that `ManageMasterUserPassword` on `RestoreDBInstanceFromDBSnapshot` and on `RestoreDBInstanceToPointInTime` is **RDS for Oracle only**. Two other facts compound this:
  - When an instance is deleted, RDS deletes its managed secret: "If you delete a DB instance that manages a secret … the secret … [is] also deleted."
  - A restored PostgreSQL instance keeps the master password stored in the snapshot. That password is the last rotated value, and it lived in a secret that no longer exists.

  For PostgreSQL, the managed secret can only come back through a later **ModifyDBInstance**. The Terraform docs don't say whether `aws_db_instance` issues that modify after `snapshot_identifier` or `restore_to_point_in_time`. If it doesn't, `db-init` has no usable master credential on any Rebuild after the first, and every restoring Rebuild fails.
- **Evidence:** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html · https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/main/website/docs/r/db_instance.html.markdown
- **Fix:** Add to AD-9 a step after restore: `aws rds modify-db-instance --manage-master-user-password --apply-immediately`, or confirm that the provider does this. `db-init` must wait for `MasterUserSecret.SecretStatus=active`. Also, because the `app` role persists in the restored data, `db-init` must stay idempotent (it already is). Prove this in the first restore Drill.

### F3 — MEDIUM-HIGH — The `Layer=ephemeral` tag query will match intentionally retained RDS artifacts (AD-6, AD-7, AD-9)
- **Claim:** The post-Teardown check passes only if a Tagging API query for `Layer=ephemeral` returns nothing.
- **Reality:** Both of these survive Teardown by design: final snapshots (`k8s-on-aws-final-*`) and retained automated backups (`delete_automated_backups=false`). If `copy_tags_to_snapshot` is true, or if the snapshot otherwise gets the instance's tags, they carry `Layer=ephemeral`, `Session=…`. `GetResources` also returns "tagged *or previously tagged*" resources, and in practice recently deleted resources (terminated instances, deleted ENIs) linger in results for a while. Either way the check can fail on a clean Teardown.
- **Evidence:** https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/API_GetResources.html · https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.Retaining.html
- **Fix:**
  - Either retag final snapshots `Layer=persistent` (or set `copy_tags_to_snapshot=false` and tag them explicitly), or exclude `rds:snapshot` and the automated-backup type in the query and the allowlist.
  - Re-check every hit with the service's native `Describe*` call before failing.
  - Retry or wait before failing, to absorb eventual consistency.

### F4 — MEDIUM — Retained automated backups carry costs and limits the spine does not state (AD-9)
- **Reality:**
  - Retained automated backups are billed. With no running instance, the free backup allowance (100% of *running* provisioned storage) is zero, so every retained backup and final snapshot is billed overnight.
  - The limit is 40 retained automated backups per region.
  - PITR is possible only within the retention period that was set at deletion time.
  - Teardown prunes snapshots but never prunes retained backups. Each Session creates a new `DbiResourceId`, so the Rebuild workflow must pick the newest retained backup by `source_dbi_resource_id`. That Terraform argument exists and is correct.
- **Evidence:** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.Retaining.html
- **Fix:** Keep `backup_retention_period` short (1–3 days). Prune retained backups beyond the newest N in Teardown. Record the backup-storage cost under NFR-1.

### F5 — MEDIUM — ESO with Pod Identity works only through the controller's own identity (AD-17)
- **Reality:** ESO supports EKS Pod Identity only when the SecretStore has **no `auth` section** and uses the controller's credentials. "`serviceAccountRef` *cannot* be used together with EKS Pod Identity." All ExternalSecrets therefore share one role, unless a SecretStore sets `role` so that ESO assumes a narrower role.
- **Evidence:** https://external-secrets.io/latest/provider/aws-access/
- **Fix:** In AD-17, state that SecretStores use one `ClusterSecretStore` (or a per-namespace `SecretStore`) with `role:` set to a per-consumer assume-role scoped to `k8s-on-aws/<consumer>/*`. The ESO controller role is allowed only `sts:AssumeRole` on those roles, plus `sts:TagSession`.

### F6 — LOW-MEDIUM — oauth2-proxy flags for the Probe's bearer token (AD-12; flags deferred to the Edge epic)
- **Verified:**
  - `--skip-jwt-bearer-tokens` exists.
  - `X-Forwarded-User` is `session.User`. That comes from `UserClaim`, which defaults to `sub` in `providers/provider_data.go`, so AD-11's Cognito `sub` holds unless `--prefer-email-to-user` is set.
  - Cognito ID tokens carry `aud` = client ID. Access tokens have no `aud`, so using the ID token is correct.
- **Risk:**
  - The documented bearer path matches `aud` against the client ID **or `--extra-jwt-issuers` (`issuer=audience`) pairs**. `--oidc-extra-audience` is documented for the main verifier. Use the documented one.
  - The Probe user's ID token needs `email` with `email_verified=true`. Otherwise you need `--insecure-oidc-allow-unverified-email`.
  - `--email-domain` must admit the Probe user.
  - `--pass-user-headers` is on by default.
- **Evidence:** https://oauth2-proxy.github.io/oauth2-proxy/configuration/overview · https://raw.githubusercontent.com/oauth2-proxy/oauth2-proxy/master/providers/provider_data.go
- **Fix:** In AD-12, replace "extra audience" with `--extra-jwt-issuers=<cognito-issuer>=<probe-client-id>`. Create the Probe user with a verified email.

### F7 — LOW — LBC Gateway: certificate discovery and default tags are confirmed, with caveats (AD-6, AD-11)
- **Confirmed:**
  - LBC Gateway docs: L4 and L7 gateways support "static certificate configuration and certificate discovery", driven by the listener and route hostnames.
  - `certificateRefs` on a Gateway listener is **not** supported. Use `LoadBalancerConfiguration.listenerConfigurations[].defaultCertificate`, or discovery through a listener `hostname`.
  - `--default-tags` applies to "all AWS resources managed by this controller". Gateway CRDs also expose per-LB, per-TG and per-rule `tags`.
- **Risk:**
  - Discovery needs the ACM cert to be `ISSUED` before the Gateway reconciles, and it needs `acm:ListCertificates` and `acm:DescribeCertificate` on the LBC role.
  - `--default-tags` is a startup flag, so changing `Session` requires a controller restart. That is fine, because the cluster is new each Session.
- **Evidence:** https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/guide/gateway/gateway.md · https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/configurations/ · https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/gateway/loadbalancerconfig/
- **Fix:** Close the Deferred item "LBC certificate-discovery field" now: set listener `hostname: app.<domain>` on Gateway `public` and rely on discovery, or pass the ARN through the GitOps Bridge annotation into `defaultCertificate`. The ARN route is more deterministic and is recommended. Have Rebuild wait for ACM `ISSUED`.

### F8 — LOW — ExternalDNS `gateway-httproute` with an ALB hostname (AD-19)
- **Verified:**
  - ExternalDNS supports `gateway-httproute` with v1 HTTPRoute and Gateway.
  - Hostnames come from the HTTPRoute and listener.
  - The only Gateway annotation it reads is `external-dns.kubernetes.io/target`.
  - LBC writes the ALB DNS name to Gateway status.
- **Not confirmed in docs:** that a Hostname-type `status.addresses` entry becomes a Route 53 alias. The ExternalDNS AWS provider normally aliases ELB hostnames, so this is likely, but it is unproven.
- **Evidence:** https://kubernetes-sigs.github.io/external-dns/latest/docs/sources/gateway-api/
- **Fix:** Add this to the M1 smoke test. Set `--gateway-namespace=gateway` and `--gateway-name=public` to keep the scope narrow.

## Confirmed without issue
- **AMP alert manager → SNS (Standard topic) → email:** supported. SNS and PagerDuty are the receivers. The topic policy must allow `aps.amazonaws.com`. https://docs.aws.amazon.com/prometheus/latest/userguide/AMP-alertmanager-receiver-createtopic.html
- **k8s-monitoring v4 Prometheus destination:** `auth.type: sigv4` with `region` and `roleArn`. https://github.com/grafana/k8s-monitoring-helm/blob/main/charts/k8s-monitoring/docs/destinations/prometheus.md
- **Alloy `prometheus.remote_write` `sigv4`:** uses the AWS SDK default chain, which includes EKS Pod Identity container credentials. No doc names the Pod Identity case explicitly, so treat it as **likely**, and verify `aps:RemoteWrite` in the M1 smoke test.
- **RDS PITR from a retained backup in Terraform:** `restore_to_point_in_time.source_dbi_resource_id` (or `source_db_instance_automated_backups_arn`) exists. It forces a new resource.
- **fck-nat module v1.6.1:** released 15 Aug, the latest. It requires AWS provider 6 and Terraform 1.9 or later. t4g.nano is the project's documented default.

## Version spot-checks (4)
| Item | Spine | Found | OK |
| --- | --- | --- | --- |
| AWS Load Balancer Controller | 3.6.2 | v3.6.2, 25 Oct (latest) | yes |
| Grafana OSS | 13.3.0 | 13.3.0, 27 Oct (latest) | yes |
| RaJiska fck-nat module | 1.6.1 | v1.6.1, 15 Aug (latest) | yes |
| Gateway API GA in LBC | assumed | GA March 2026 (feature gates required) | yes. The `ALBGatewayAPI` feature gate must be enabled in the chart values |
