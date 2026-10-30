# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Explainability check (NFR-6).

Fails when a Terraform root under infra/ or an Argo CD Application/ApplicationSet under
gitops/ has no row in docs/components.md, or when a row's explainer link points at a file
that does not exist.

Standard library only. YAML is read with regular expressions rather than a YAML parser,
because gitops/ holds Go-templated manifests that are not always valid YAML.

Usage: uv run --python 3.14 scripts/check_components.py [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

COMPONENTS_DOC = Path("docs") / "components.md"
ARGO_KINDS = ("Application", "ApplicationSet")

_DOC_SEPARATOR = re.compile(r"^---(?:\s.*)?$")
_TOP_LEVEL_KIND = re.compile(r"^kind:\s*(.*)$")
_TOP_LEVEL_METADATA = re.compile(r"^metadata:\s*(?:#.*)?$")
_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|([^|]*)\|(.*)\|\s*$")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass(frozen=True)
class Component:
    id: str
    description: str  # e.g. "terraform root" or "ApplicationSet in gitops/root/apps.yaml"


@dataclass(frozen=True)
class Row:
    id: str
    link: str | None


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scalar(raw: str) -> str:
    """Return a YAML scalar's value: trailing comment and surrounding quotes removed."""
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end != -1 else value[1:]
    return re.sub(r"\s+#.*$", "", value).strip()


def discover_terraform_roots(root: Path) -> list[Component]:
    infra = root / "infra"
    if not infra.is_dir():
        return []
    modules = infra / "modules"
    dirs = set()
    for tf in infra.rglob("*"):
        if not tf.is_file() or not tf.name.endswith((".tf", ".tf.json")):
            continue
        parent = tf.parent
        if parent == modules or modules in parent.parents:
            continue
        if any(part.startswith(".terraform") for part in parent.relative_to(infra).parts):
            continue
        dirs.add(parent)
    return [Component(_rel(d, root), "terraform root") for d in sorted(dirs)]


def _split_documents(text: str) -> list[list[str]]:
    docs: list[list[str]] = [[]]
    for line in text.splitlines():
        if _DOC_SEPARATOR.match(line):
            docs.append([])
        else:
            docs[-1].append(line)
    return docs


def _metadata_name(lines: list[str]) -> str | None:
    """Return the top-level metadata.name of one YAML document, or None."""
    for i, line in enumerate(lines):
        if not _TOP_LEVEL_METADATA.match(line):
            continue
        indent = None
        for child in lines[i + 1 :]:
            stripped = child.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not child[:1].isspace():
                break  # back at top level: metadata block ended
            current = len(child) - len(child.lstrip())
            if indent is None:
                indent = current
            if current != indent:
                continue  # nested deeper (labels, annotations, ...)
            match = re.match(r"name:\s*(.*)$", stripped)
            if match:
                return _scalar(match.group(1))
        return None
    return None


def discover_argo_apps(root: Path) -> list[tuple[Component, str | None]]:
    """Return (component, error) pairs; error is set when metadata.name is unreadable."""
    gitops = root / "gitops"
    if not gitops.is_dir():
        return []
    found: list[tuple[Component, str | None]] = []
    files = sorted(p for p in gitops.rglob("*") if p.is_file() and p.suffix.lower() in (".yaml", ".yml"))
    for path in files:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        rel = _rel(path, root)
        for lines in _split_documents(text):
            kind = None
            for line in lines:
                match = _TOP_LEVEL_KIND.match(line)
                if match:
                    kind = _scalar(match.group(1))
                    break
            if kind not in ARGO_KINDS:
                continue
            name = _metadata_name(lines)
            if not name:
                found.append(
                    (Component("argocd/?", f"{kind} in {rel}"),
                     f"unreadable component: {kind} in {rel} has no top-level metadata.name")
                )
                continue
            found.append((Component(f"argocd/{name}", f"{kind} in {rel}"), None))
    return found


def parse_rows(doc: Path) -> list[Row]:
    rows: list[Row] = []
    fence: str | None = None
    for line in doc.read_text(encoding="utf-8").splitlines():
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        match = _ROW.match(line.strip())
        if not match:
            continue
        link = _LINK.search(match.group(3))
        rows.append(Row(match.group(1).strip(), link.group(1) if link else None))
    return rows


def check(root: Path) -> tuple[int, list[str]]:
    """Return (number of discovered components, list of problems)."""
    problems: list[str] = []
    components = discover_terraform_roots(root)
    unreadable = 0
    for component, error in discover_argo_apps(root):
        if error:
            unreadable += 1
            problems.append(error)
        else:
            components.append(component)

    doc = root / COMPONENTS_DOC
    if not doc.is_file():
        problems.append(f"missing {COMPONENTS_DOC.as_posix()}")
        rows: list[Row] = []
    else:
        rows = parse_rows(doc)

    listed = {row.id for row in rows}
    for component in components:
        if component.id not in listed:
            problems.append(f"unlisted component: {component.id} ({component.description})")

    for row in rows:
        if row.link is None:
            problems.append(f"missing explainer for {row.id}: no link in 'Explained by'")
            continue
        target = row.link.split("#", 1)[0]
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
            problems.append(f"missing explainer for {row.id}: {row.link} (must be a relative file link)")
            continue
        if not (doc.parent / target).is_file():
            problems.append(f"missing explainer for {row.id}: {target}")

    total = len(components) + unreadable
    return total, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    total, problems = check(root)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"components: {total} discovered, {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"components: {total} discovered, all listed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
