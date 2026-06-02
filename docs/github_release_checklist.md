# GitHub Release Checklist

Use this checklist before pushing the repository publicly.

## Repository Hygiene

- [ ] Run `git status --short` and review every modified or untracked file.
- [ ] Keep generated `.blend`, `.blend1`, render output, local workspaces, and
      model weights out of the repository.
- [ ] Confirm `.env` is not committed.
- [ ] Confirm `.env.example` contains placeholders only.
- [ ] Confirm any third-party assets have compatible licenses.

## Validation

- [ ] Create a fresh virtual environment.
- [ ] Run `python -m pip install -e ".[dev]"`.
- [ ] Run `python -m pytest tests/ -v`.
- [ ] Package the Blender add-on with `python scripts/package_addon.py`.
- [ ] Install the generated add-on zip in Blender and click **Start Bridge**.
- [ ] Run `connect_blender` from an MCP client.

## GitHub Setup

- [ ] Push to `main`.
- [ ] Confirm the CI workflow passes.
- [ ] Add repository description, topics, and website link in GitHub settings.
- [ ] Enable Dependabot alerts.
- [ ] Add a first release tag, for example `v0.2.0`.

Suggested GitHub topics:

`blender`, `mcp`, `model-context-protocol`, `3d`, `ai`, `image-to-3d`,
`python`, `addon`, `generative-ai`
