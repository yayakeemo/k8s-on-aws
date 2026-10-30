- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-bootstrap-l0-from-an-empty-aws-account.md`
  summary: Story 1.3's L0 plan in CI needs a source for `alert_email` (for example a TF_VAR from an Actions secret) and a github-provider token that can read the environments and the ruleset.
  evidence: `alert_email` has no default and lives only in the git-ignored tfvars. The default workflow GITHUB_TOKEN may not be able to read rulesets or environment deployment policies, so the L0 PR plan would fail.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-bootstrap-l0-from-an-empty-aws-account.md`
  summary: Add `terraform fmt -check` and `validate` for every root to `pr-plan` when story 1.3 adds the plan jobs.
  evidence: Today `pr-plan` runs only the Python tests and the components check, so an invalid `infra/bootstrap` change could merge green.
