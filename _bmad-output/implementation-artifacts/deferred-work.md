- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-repo-skeleton-conventions-and-explainability-check.md`
  summary: Confirm on a real GitHub run that `pr-plan`'s `components` job runs on human PRs and is skipped only for `github-actions[bot]`-authored PRs.
  evidence: The repo has no workflow-testing harness and there is no remote or Actions history yet (story 1.2 creates the GitHub settings). The first real PR under stories 1.2/1.3 is the natural point to verify the job condition.
