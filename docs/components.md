# Components

This file maps every component of the platform to the document that explains it (NFR-6).
A component is either:

- a **Terraform root**: a directory under `infra/` that directly holds `*.tf` files, except
  anything under `infra/modules/`. Its id is its path, for example `infra/persistent`.
- an **Argo CD app**: a YAML document under `gitops/` whose top-level `kind` is `Application` or
  `ApplicationSet`. Its id is `argocd/<metadata.name>`, for example `argocd/workloads`.

`scripts/check_components.py` runs on every PR (the `components` job of `pr-plan`). It fails, naming
the component, when a component exists but has no row here, or when a row's link points at a file
that does not exist. Add the row in the same PR that adds the component.

## Row format

One row per component:

- **Component**: the id, in backticks.
- **Kind**: `terraform root`, `Application` or `ApplicationSet`.
- **Explained by**: a markdown link, relative to this `docs/` directory, to the ADR or runbook
  that explains the component.

Example (not a real row):

```markdown
| `infra/persistent` | terraform root | [ADR-0002](adr/0002-persistent-layer.md) |
```

## Map

| Component | Kind | Explained by |
| --- | --- | --- |
