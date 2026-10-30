"""Unit tests for scripts/check_components.py, one per row of the Story 1.1 I/O matrix.

Run: uv run --python 3.14 -m unittest discover -s scripts/tests -v
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_components  # noqa: E402

HEADER = textwrap.dedent(
    """\
    # Components

    Example (not a real row):

    ```markdown
    | `infra/example` | terraform root | [ADR-9999](adr/9999-missing.md) |
    ```

    | Component | Kind | Explained by |
    | --- | --- | --- |
    """
)


class CheckComponentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for d in ("infra/bootstrap", "infra/persistent", "infra/ephemeral/core",
                  "infra/ephemeral/gitops", "infra/modules", "gitops/root",
                  "gitops/platform", "gitops/workloads", "docs/adr", "docs/runbooks"):
            (self.root / d).mkdir(parents=True)
            (self.root / d / ".gitkeep").write_text("")
        self.write("infra/workload-identities.yaml", "identities: []\n")
        self.write_components()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    def write_components(self, *rows: str) -> None:
        self.write("docs/components.md", HEADER + "".join(r + "\n" for r in rows))

    def run_check(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check_components.main(["--repo-root", str(self.root)])
        return code, out.getvalue(), err.getvalue()

    # Clean skeleton
    def test_clean_skeleton_passes(self) -> None:
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertIn("components: 0 discovered, all listed", out)
        self.assertEqual(err, "")

    # Listed root
    def test_listed_root_passes(self) -> None:
        self.write("infra/persistent/main.tf", 'terraform {}\n')
        self.write("docs/adr/0002-persistent-layer.md", "# ADR\n")
        self.write_components("| `infra/persistent` | terraform root | [ADR-0002](adr/0002-persistent-layer.md) |")
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertIn("components: 1 discovered, all listed", out)

    # Unlisted root
    def test_unlisted_root_fails(self) -> None:
        self.write("infra/ephemeral/core/main.tf", 'terraform {}\n')
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("unlisted component: infra/ephemeral/core (terraform root)", err)

    # Module dir
    def test_module_dir_is_not_a_root(self) -> None:
        self.write("infra/modules/main.tf", 'variable "z" {}\n')
        self.write("infra/modules/x/main.tf", 'variable "a" {}\n')
        self.write("infra/modules/x/nested/main.tf", 'variable "b" {}\n')
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertIn("components: 0 discovered, all listed", out)

    def test_terraform_cache_dir_is_not_a_root(self) -> None:
        self.write("infra/persistent/main.tf", 'terraform {}\n')
        self.write("infra/persistent/.terraform/modules/vpc/main.tf", 'variable "a" {}\n')
        self.write("docs/adr/0002-persistent-layer.md", "# ADR\n")
        self.write_components("| `infra/persistent` | terraform root | [ADR-0002](adr/0002-persistent-layer.md) |")
        code, _, err = self.run_check()
        self.assertEqual(code, 0, err)

    # Unlisted Argo app
    def test_unlisted_applicationset_fails(self) -> None:
        self.write("gitops/root/apps.yaml", """\
            apiVersion: argoproj.io/v1alpha1
            kind: ApplicationSet
            metadata:
              labels:
                name: not-this-one
              name: workloads
            spec:
              template:
                metadata:
                  name: '{{ .name }}'
            """)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn(
            "unlisted component: argocd/workloads (ApplicationSet in gitops/root/apps.yaml)", err
        )
        self.assertNotIn("not-this-one", err)

    def test_listed_application_passes(self) -> None:
        self.write("gitops/root/root.yaml", """\
            apiVersion: argoproj.io/v1alpha1
            kind: Application
            metadata:
              name: root  # app-of-apps
            """)
        self.write("docs/runbooks/rebuild.md", "# Rebuild\n")
        self.write_components("| `argocd/root` | Application | [Rebuild](runbooks/rebuild.md#argo) |")
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertIn("components: 1 discovered, all listed", out)

    def test_non_argo_kinds_are_ignored(self) -> None:
        self.write("gitops/platform/cm.yaml", """\
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: settings
            data:
              kind: Application
            """)
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertIn("components: 0 discovered, all listed", out)

    # Multi-doc YAML
    def test_multi_document_yaml_discovers_each_app(self) -> None:
        self.write("gitops/platform/apps.yml", """\
            apiVersion: v1
            kind: Namespace
            metadata:
              name: observability
            ---
            apiVersion: argoproj.io/v1alpha1
            kind: Application
            metadata:
              name: alloy
            --- # second app
            apiVersion: argoproj.io/v1alpha1
            kind: Application
            metadata:
              name: "grafana"
            """)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("unlisted component: argocd/alloy (Application in gitops/platform/apps.yml)", err)
        self.assertIn("unlisted component: argocd/grafana (Application in gitops/platform/apps.yml)", err)
        self.assertNotIn("observability", err)
        self.assertIn("components: 2 discovered", err)

    # Broken explainer link
    def test_broken_explainer_link_fails(self) -> None:
        self.write("infra/persistent/main.tf", 'terraform {}\n')
        self.write_components("| `infra/persistent` | terraform root | [ADR-0002](adr/0002-persistent-layer.md) |")
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("missing explainer for infra/persistent: adr/0002-persistent-layer.md", err)
        self.assertNotIn("unlisted component", err)

    def test_row_without_link_fails(self) -> None:
        self.write_components("| `infra/persistent` | terraform root | TODO |")
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("missing explainer for infra/persistent", err)

    def test_example_row_in_code_fence_is_ignored(self) -> None:
        # HEADER holds a fenced example row with a broken link; it must not be parsed.
        code, _, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertNotIn("infra/example", err)

    # Templated name
    def test_templated_name_is_unlisted_with_raw_name(self) -> None:
        self.write("gitops/workloads/app.yaml", """\
            apiVersion: argoproj.io/v1alpha1
            kind: Application
            metadata:
              name: '{{ .x }}'
            """)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn(
            "unlisted component: argocd/{{ .x }} (Application in gitops/workloads/app.yaml)", err
        )

    def test_argo_doc_without_top_level_name_is_unreadable(self) -> None:
        self.write("gitops/root/broken.yaml", """\
            apiVersion: argoproj.io/v1alpha1
            kind: Application
            metadata:
              labels: {name: x}
            """)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn(
            "unreadable component: Application in gitops/root/broken.yaml has no top-level metadata.name",
            err,
        )
        self.assertIn("components: 1 discovered", err)

    def test_tf_json_only_root_is_discovered(self) -> None:
        self.write("infra/ephemeral/core/main.tf.json", '{"terraform": {}}\n')
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("unlisted component: infra/ephemeral/core (terraform root)", err)

    def test_uppercase_yaml_suffix_is_scanned(self) -> None:
        self.write("gitops/root/apps.YAML", """\
            apiVersion: argoproj.io/v1alpha1
            kind: ApplicationSet
            metadata:
              name: workloads
            """)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn(
            "unlisted component: argocd/workloads (ApplicationSet in gitops/root/apps.YAML)", err
        )

    def test_bom_prefixed_manifest_is_read(self) -> None:
        text = textwrap.dedent("""\
            kind: Application
            apiVersion: argoproj.io/v1alpha1
            metadata:
              name: root
            """)
        (self.root / "gitops/root/root.yaml").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("unlisted component: argocd/root (Application in gitops/root/root.yaml)", err)

    def test_missing_components_doc_fails(self) -> None:
        (self.root / "docs/components.md").unlink()
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("missing docs/components.md", err)


if __name__ == "__main__":
    unittest.main()
