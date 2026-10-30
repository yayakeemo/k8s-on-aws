"""The `main` ruleset requires the pr-plan `components` job by its display name.

If the job in .github/workflows/pr-plan.yml is renamed without changing
infra/bootstrap/github.tf in the same PR, every human PR is blocked. This test pins the two.

Run: uv run --python 3.14 -m unittest discover -s scripts/tests -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-plan.yml"
GITHUB_TF = REPO_ROOT / "infra" / "bootstrap" / "github.tf"


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def workflow_job_name(text: str, job_id: str = "components") -> str:
    """Return the `name:` of the job `job_id`: a 2-space key under `jobs:`, name at 4 spaces."""
    jobs = re.search(r"^jobs:[ ]*\n(?P<body>(?:(?:[ ]+.*|[ ]*)(?:\n|$))*)", text, re.MULTILINE)
    if jobs is None:
        raise AssertionError(f"top-level jobs: not found in {WORKFLOW}")
    job = re.search(
        rf"^[ ]{{2}}{re.escape(job_id)}:[ ]*\n(?P<body>(?:(?:[ ]{{3,}}.*|[ ]*)(?:\n|$))*)",
        jobs.group("body"),
        re.MULTILINE,
    )
    if job is None:
        raise AssertionError(f"job {job_id!r} not found under jobs: in {WORKFLOW}")
    name = re.search(r"^[ ]{4}name:[ ]*(?P<name>.*?)[ ]*$", job.group("body"), re.MULTILINE)
    if name is None:
        raise AssertionError(f"job {job_id!r} has no name: in {WORKFLOW}")
    return _strip_quotes(name.group("name"))


def ruleset_required_check(text: str) -> str:
    match = re.search(r'^\s*required_status_check\s*=\s*"(?P<name>[^"]+)"', text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"required_status_check not found in {GITHUB_TF}")
    return match.group("name")


class RequiredCheckNameTest(unittest.TestCase):
    def test_ruleset_check_matches_workflow_job_name(self) -> None:
        job_name = workflow_job_name(WORKFLOW.read_text(encoding="utf-8"))
        required = ruleset_required_check(GITHUB_TF.read_text(encoding="utf-8"))
        self.assertEqual(
            required,
            job_name,
            "infra/bootstrap/github.tf required_status_check must equal the pr-plan "
            "components job name; rename both in the same PR and re-apply L0 by hand.",
        )

    def test_ruleset_context_uses_the_local(self) -> None:
        self.assertRegex(
            GITHUB_TF.read_text(encoding="utf-8"),
            r"context\s*=\s*local\.required_status_check",
        )

    def test_parsers_on_samples(self) -> None:
        workflow = (
            "name: pr-plan\n"
            "jobs:\n"
            "  other:\n"
            "    name: not this one\n"
            "    with:\n"
            "      components:\n"
            "        name: nested, not a job\n"
            "  components:\n"
            "    # comment\n"
            "    steps:\n"
            "      - name: step name, not the job\n"
            '    name: "quoted name # with hash"\n'
            "    runs-on: ubuntu-24.04\n"
        )
        self.assertEqual(workflow_job_name(workflow), "quoted name # with hash")
        self.assertEqual(
            ruleset_required_check('locals {\n  required_status_check = "x (y)"\n}\n'), "x (y)"
        )

    def test_nested_components_key_is_not_a_job(self) -> None:
        workflow = (
            "jobs:\n"
            "  other:\n"
            "    with:\n"
            "      components:\n"
            "        name: nested\n"
        )
        with self.assertRaises(AssertionError):
            workflow_job_name(workflow)


if __name__ == "__main__":
    unittest.main()
