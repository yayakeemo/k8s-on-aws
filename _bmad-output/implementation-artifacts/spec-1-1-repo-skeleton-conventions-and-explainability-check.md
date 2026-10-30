---
title: 'Story 1.1: Repo skeleton, conventions and explainability check'
type: 'feature'
created: '2026-10-30'
status: 'done'
baseline_commit: 'NO_VCS'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-Kubernetes-on-AWS-2026-10-28/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repo is empty, so later stories have no fixed place to put anything. The conventions aren't written down, and nothing stops a component from shipping without an explanation (NFR-6).

**Approach:** Lay down the architecture's source tree, write `docs/conventions.md`, `docs/cost-model.md` and `docs/components.md`, and add a stdlib-only Python check that fails CI when a Terraform root or Argo CD Application/ApplicationSet is not listed in `docs/components.md`.

## Boundaries & Constraints

**Always:**
- Use exactly the directory layout of ARCHITECTURE-SPINE "Source tree". Empty directories hold a `.gitkeep`.
- The check uses only the Python 3.14 standard library and runs with `uv run`, so it needs no `pip install`.
- The check runs as a job in `.github/workflows/pr-plan.yml`, on `ubuntu-24.04` with pinned actions. Story 1.3 adds the plan jobs to the same file, which keeps the workflow list closed.
- Bot commits (`chore(bot): …`) do not trigger `pr-plan`.
- Docs restate the architecture's Consistency Conventions. They never contradict them.

**Never:**
- No Terraform, Argo CD manifests, app code or AWS resources. Those belong to stories 1.2 and later.
- No `git init`, no remote and no GitHub settings (rulesets and environments belong to story 1.2).
- No third-party Python dependencies.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean skeleton | No `.tf` files, no Argo CD manifests | Exit 0, `components: 0 discovered, all listed` | N/A |
| Listed root | `infra/persistent/main.tf` exists, and components.md has a row for `infra/persistent` that links an existing file | Exit 0 | N/A |
| Unlisted root | `infra/ephemeral/core/main.tf` exists, with no row | Exit 1 | stderr: `unlisted component: infra/ephemeral/core (terraform root)` |
| Module dir | `.tf` files under `infra/modules/x/` | Not treated as a root | N/A |
| Unlisted Argo app | `gitops/root/apps.yaml` holds `kind: ApplicationSet` with `name: workloads` | Exit 1 | stderr: `unlisted component: argocd/workloads (ApplicationSet in gitops/root/apps.yaml)` |
| Multi-doc YAML | Several `---`-separated documents, two of them Applications | Both are discovered | N/A |
| Broken explainer link | A row whose link target file does not exist | Exit 1 | stderr: `missing explainer for <id>: <path>` |
| Templated name | `name: '{{ .x }}'` | Treated as unlisted, using the raw name | The message names the file |

</frozen-after-approval>

## Code Map

- The repo has no code. Only `_bmad/`, `_bmad-output/` and `.claude/` exist, and none of them should be touched.
- `ARCHITECTURE-SPINE.md` "Consistency Conventions", "Stack" and "Source tree": the source for `conventions.md`, the pins and the layout.
- `epic-1-context.md`: the Persistent Footprint items for the cost model, and the bot-commit rules.
- AD-21: the `infra/workload-identities.yaml` schema `{namespace, serviceAccount, policy}`. AD-2: exactly four roots, with `infra/modules/` excluded.

## Tasks & Acceptance

**Execution:**
- [x] Directory tree from the AC, with `.gitkeep` in each empty leaf -- gives every later story a fixed place
- [x] `.gitignore` -- ignore `.terraform/`, `*.tfstate*`, `*.tfplan`, `__pycache__/` and `.venv/` -- keeps state and plans out of Git
- [x] `infra/workload-identities.yaml` -- `identities: []`, with a comment header documenting each field and an example entry -- the AD-21 registry
- [x] `docs/conventions.md` -- naming prefixes, SSM and secret paths, the `session_id` format, tags, namespaces, labels, the exact-pin rule with the Stack table pins for Terraform, AWS provider and AWS CLI, JSON log fields, Conventional Commits plus `fault(<incident>)`, `fix(pm-<n>)` and `chore(bot)`, docs locations, and the rule to log every live-Platform problem in `docs/writeups/_journal.md` -- AC 3
- [x] `docs/writeups/_journal.md` -- the entry template (date, `session_id`, symptom, first commands) and no entries -- the journal the conventions require
- [x] `docs/cost-model.md` -- a table of Item, Layer, Expected $/month, Basis and Status, with one row per planned L0/L1 item (state bucket, budgets, SNS, SSM params, Route 53 zone, domain amortised, Cognito, ECR, Secrets Manager per secret, AMP, CloudWatch log group, RDS final snapshots), marked `planned (story x.y)`, plus a total against the $30 target -- NFR-1
- [x] `docs/components.md` -- explains the format and has an empty table of Component, Kind and Explained by, where the first cell is the backticked id and the third is a relative markdown link -- the NFR-6 map
- [x] `scripts/check_components.py` -- discovers roots (directories under `infra/` holding `*.tf`, excluding `infra/modules/**`) and Argo apps (YAML documents under `gitops/` whose top-level `kind:` is `Application` or `ApplicationSet`, read through a regex over the top-level `metadata.name`), parses the components.md rows, reports unlisted components and missing explainer files, and exits non-zero on any problem. Takes `--repo-root` (default `.`) -- the enforcement
- [x] `scripts/tests/test_check_components.py` -- `unittest` cases covering every row of the I/O matrix, each built in a temp directory -- proves the check
- [x] `.github/workflows/pr-plan.yml` -- `pull_request` to `main`. A `components` job on `ubuntu-24.04` with `actions/checkout` and `astral-sh/setup-uv` pinned to commit SHAs, uv `0.13.6` and Python `3.14`, which runs the tests and then the check. Skips only when the PR author (`github.event.pull_request.user.login`) is `github-actions[bot]`. The PR title is never used for the skip, because any human can type it. -- runs the check on every human PR
- [x] `docs/runbooks/.gitkeep`, `docs/adr/.gitkeep` -- placeholders only. ADR 0001 comes later.

**Acceptance Criteria:**
- Given the finished skeleton, when listing the tree, then every directory named in Story 1.1 AC 1 exists.
- Given the clean skeleton, when running `uv run --python 3.14 scripts/check_components.py`, then it exits 0.
- Given a PR, when `pr-plan` runs, then the `components` job runs the unit tests and the check, and fails on any unlisted component.
- Given `docs/conventions.md`, when it is read, then every item in Story 1.1 AC 3 is present and matches ARCHITECTURE-SPINE.

## Implementation Notes

- Action pins: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1), `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` (v9.0.0), resolved with `git ls-remote` on 2026-10-30.
- The check skips fenced code blocks in `components.md`, so the documented example row is not parsed. It also skips `.terraform/` cache dirs under `infra/`, and reports a YAML Argo doc with no readable top-level `metadata.name` as `unreadable component: ...` (exit 1).
- Rows that link with a URL scheme (`https:` etc.) are rejected; explainers must be repo files. Anchors (`#...`) are stripped before the existence check.
- Listed rows with no matching component (stale rows) are not flagged; only the I/O matrix behaviours are enforced.
- Cost figures are list-price estimates (total about $8.90/month); each owning story replaces its row's figure.
- Verified locally with uv 0.11.21 (CI pins 0.13.6) and Python 3.14: 14 tests pass; the check exits 0 on the skeleton.

## Spec Change Log

- **Loop 1 (2026-10-30)**
  - **Trigger:** three reviewers (blind, edge-case and verification-gap) found the same problem. `pr-plan` skipped the `components` job on the PR-title prefix `chore(bot):`, which any human PR can carry, so the NFR-6 gate could be bypassed. A skipped required job counts as passing.
  - **Amended:** the `pr-plan.yml` task now gates on the PR author being `github-actions[bot]`.
  - **Known-bad state avoided:** a human PR titled `chore(bot): …` merging an unlisted component unchecked.
  - **KEEP:** the loop-0 implementation was good and is preserved at `C:/Users/YAHIA~1.HUS/AppData/Local/Temp/claude/C--Users-yahia-hussein-OneDrive-Projects-Personal-Kubernetes-on-AWS/e8b5c331-5a93-4627-8db2-6be018f56679/scratchpad/story-1-1-loop1-backup/`. Re-derive from it: copy every file back unchanged, then apply only the changes below. Keep all docs content, the cost rows, the action SHA pins, the fenced-example skip, the `.terraform/` skip, URL-scheme link rejection and all 14 existing tests.
    1. `pr-plan.yml`: use the author gate above.
    2. `check_components.py`:
       - count unreadable components from the typed `(component, error)` results, not by matching message text
       - fix the missing space in `Component("argocd/?",f"...`
       - discover roots from `*.tf` and `*.tf.json`
       - match the `.yaml`/`.yml` suffix case-insensitively
       - read YAML with `encoding="utf-8-sig"` so a BOM before `kind:` is tolerated
    3. Tests:
       - an Argo Application whose `metadata:` holds only `labels: {name: x}`: exit 1, the `unreadable component: …` line, and `components: 1 discovered`
       - a root holding only `main.tf.json`
       - an `.YAML` manifest
       - a BOM-prefixed manifest
    4. `infra/workload-identities.yaml`: note that the rendered-gitops CI check arrives with the story that adds Pod Identity (2.5).
    5. `docs/conventions.md`: state the layer mapping L0=`bootstrap`, L1=`persistent`, L2–L4=`ephemeral`.
    6. `docs/cost-model.md`: set the RDS snapshots row's Layer to `persistent (retagged by Teardown, AD-6)`.
    7. `.gitignore`: add `crash.log`, `crash.*.log`, `override.tf`, `override.tf.json`, `*_override.tf`, `*_override.tf.json` and `.env`.

## Review Triage Log

| # | Source | Finding | Verdict | Evidence / route |
|---|--------|---------|---------|------------------|
| 1 | blind, edge, vgap | `pr-plan` skip keyed on the spoofable PR title | low | Real: a human PR titled `chore(bot):` skips the gate. The fix is a direct correction, so it is kept. The spec asked for the title check → **bad_spec** (loop 1) |
| 2 | edge | `edited` PR type not subscribed, so a title change gives a stale result | low | Real only under title gating, which loop 1 removes. Same root cause as #1 → **bad_spec** |
| 3 | vgap | The `unreadable component` path has no test | medium | Pre-verified: no test reaches the branch → patch, folded into the loop-1 KEEP |
| 4 | vgap | The bot-skip condition is not verified | low | Pre-verified gap with no workflow harness and no Actions runs yet → **defer** |
| 5 | blind | `total` is counted by matching message text, plus a formatting nit | low | Real and brittle; direct correction → patch (loop-1 KEEP) |
| 6 | blind, edge | `*.tf.json` roots are not discovered | low | Real: `rglob("*.tf")` misses them; direct correction → patch (KEEP) |
| 7 | edge | An uppercase `.YAML`/`.YML` suffix is ignored | low | Real: the suffix compare is case-sensitive; direct correction → patch (KEEP) |
| 8 | edge | A UTF-8 BOM hides `kind:` on the first line | low | Real: `^kind:` fails after a BOM, and Windows editors write BOMs; direct correction → patch (KEEP) |
| 9 | blind | The workload-identities comment claims a CI check that does not exist yet | low | Real; a one-line doc correction → patch (KEEP) |
| 10 | blind | Layer terms are undefined, and the RDS snapshot row's Layer is invalid | low | Real; doc correction → patch (KEEP) |
| 11 | blind | `.gitignore` misses `crash.log`, override files and `.env` | low | Real; direct addition → patch (KEEP). `*.tfvars` is not ignored, because tfvars may be committed (no secrets in them) |
| 12 | blind | Stale rows are not flagged | low | Not required by the intent; the fix adds a new check → rejected |
| 13 | blind, edge | Duplicate rows or app names are not detected | low | Argo app names are unique within `argocd`; duplicate rows are harmless; the fix adds a branch → rejected |
| 14 | blind | The Kind column is not validated | low | Cosmetic; the fix adds logic → rejected |
| 15 | blind, edge | Table rows outside `## Map` are parsed | low | No such table exists, and fenced examples are already skipped; the fix adds state → rejected |
| 16 | blind, edge | Explainer links are not limited to ADRs or runbooks, and `%20`, `<>`, absolute and `../..` links are not handled | low | Unlikely; most of these fail loudly; the fix adds branches → rejected |
| 17 | blind, vgap | No test for rejecting `https:` links | low | Removing that branch still fails through the existence check → rejected |
| 18 | blind | Python pinned as `3.14`, plus `requires-python >=3.14` | false | The architecture Stack table pins Python as `3.14`; the code matches it |
| 19 | blind | Vendored `charts/` under gitops could be scanned | low | No vendored charts are planned; the fix adds exclusion logic → rejected |
| 20 | blind | The cost model omits KMS, API calls and version growth | low | KMS is not used (AD-6: AWS-managed keys only); the rest is negligible, and the figures are labelled estimates → rejected |
| 21 | edge | Content inline after a `---` separator is lost | low | Unusual in manifests; the fix adds parsing logic → rejected |
| 22 | edge | A `---` inside a block scalar splits the document | low | Unlikely in Argo manifests; complex fix → rejected |
| 23 | edge | A Go template at column 0 inside `metadata` | low | It fails loudly as unreadable rather than silently → rejected |
| 24 | edge | Escaped quotes in names | false | Kubernetes names cannot contain quotes |
| 25 | edge | `kind: Application` under a non-argoproj apiVersion | low | Unlikely, and it fails loudly → rejected |
| 26 | edge | A non-UTF-8 `components.md` raises a traceback | low | It fails loudly; unlikely → rejected |
| 27 | vgap (loop 1) | A `.tf` file directly in `infra/modules/` is not covered by any test | low | Pre-verified: the reviewer reduced the condition to `modules in parent.parents` and all 18 tests still passed → patch |
| 28 | vgap (loop 1) | No test for rejecting URL-scheme links | low | carried #17 → rejected |
| 29 | blind (loop 1) | Stale or duplicate rows, and the Kind column unchecked | low | carried #12, #13, #14 → rejected |
| 30 | blind, edge (loop 1) | The explainer may be any file, an absolute path, or a `../..` link | low | carried #16 → rejected |
| 31 | blind (loop 1) | Flow-style `metadata: {name: x}`, the `...` end-of-document marker, escaped quotes | low | Fails loudly as unreadable; escaped quotes carried as false (#24) → rejected |
| 32 | blind (loop 1) | A local `modules/` folder inside a root is counted as a root | low | AD-2 puts shared code only in `infra/modules/`; it fails loudly → rejected |
| 33 | blind, edge (loop 1) | The author gate is likely dead code; a human pushing to a bot-authored PR gets skipped | low | AD-25: bot commits are pushed through the ruleset bypass and never open PRs, so human PRs are always checked; the fix adds complexity → rejected |
| 34 | blind (loop 1) | No `push`/`merge_group` trigger on `main` | low | The `main` ruleset requires a PR for every human change; bot pushes only bump tags or rebuild-log files → rejected |
| 35 | blind, edge (loop 1) | `.gitignore` misses an extensionless `tfplan` and `.env.*` | low | Real (`plan -out=tfplan` is common); direct addition → patch. `*.tfvars` carried #11 |
| 36 | blind (loop 1) | The journal template heading `##` is a sibling of `## Entries` | low | Real; direct correction → patch |
| 37 | blind (loop 1) | Cost model: an inconsistent Layer label, and per-user secret cost not stated | low | Real; direct doc correction → patch. KMS carried #20; the Session headroom belongs to Epic 2 → rejected |
| 38 | blind (loop 1) | The workload-identities namespace and policy-path schema is not enforced | low | New capability outside Story 1.1; it belongs with story 2.5 → rejected |
| 39 | edge (loop 1) | A row inside an HTML comment counts as listed | low | Unlikely; the fix adds parser state → rejected |
| 40 | edge (loop 1) | `.json` Argo manifests are not scanned | low | `gitops/` is YAML by convention; unlikely → rejected |
| 41 | edge (loop 1) | An OSError on an unreadable gitops file raises a traceback | low | Fails loudly; unlikely → rejected |
| 42 | edge (loop 1) | Under `python -OO`, `__doc__` is None and startup crashes | low | CI and docs run plain `uv run`; never run with `-OO` → rejected |

## Design Notes

Component ids: a Terraform root uses its path (`infra/persistent`), and an Argo app uses `argocd/<metadata.name>`. Example row:

```markdown
| `infra/persistent` | terraform root | [ADR-0002](adr/0002-persistent-layer.md) |
```

The check parses YAML with a regex instead of PyYAML because `gitops/` will hold Go-templated ApplicationSets that are not always valid YAML, and the check has to stay dependency-free. Cost figures are us-east-1 list-price estimates, labelled as estimates, and later stories update them.

## Verification

**Commands:**
- `uv run --python 3.14 -m unittest discover -s scripts/tests -v` -- expected: all tests pass
- `uv run --python 3.14 scripts/check_components.py` -- expected: exit 0
