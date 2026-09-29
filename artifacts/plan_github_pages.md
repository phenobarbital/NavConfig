# GitHub Pages documentation and usage

## Plan

1. Extend the existing static site in `site/`, retaining the documentation and
   adding a dedicated, runnable usage guide with shared CSS and navigation.
2. Check examples against `navconfig/kardex.py`, the loaders and CLI; correct
   inaccurate accessor examples and explain initialization and environment selection.
3. Add a dependency-free site link checker and run it for pull requests and before
   the existing GitHub Pages deployment from `main`.
4. Document local preview and Pages setup; point package metadata to the site.
5. Validate local links, Python snippets and the quickstart in an isolated temporary
   project. Save validation output under `artifacts/logs/`.

## Assumptions and risks

- `site/index.html` and `.github/workflows/pages.yml` already exist; extend them.
- No `CONTEXT.md` or nested `AGENTS.md` was found.
- Keep static HTML/CSS and use Python's standard library for validation and preview;
  no additional dependencies or application changes are needed.
- Preserve the existing `main` publishing branch. GitHub Pages must use GitHub Actions
  as its source; remote enablement and deployment have not been verified locally.
- Documentation must reflect the implementation, including keyword-only use of
  `fallback` in examples and the limits of file override behavior.
- A new branch was offered. Work continues on the existing branch unless requested.

## Validation results

- Two HTML pages passed local link, fragment and duplicate ID checks.
- All eight tagged Python snippets passed syntax checks and executed successfully
  against the local package in an isolated temporary project.
- CLI scaffolding, expected quickstart output, typed INI results, logging setup and
  production environment creation passed.
- Workflow YAML parsing, deployment dependencies, Black formatting, import sorting
  and `git diff --check` passed.
- Reviewed the usage page in headless Chrome at 390 × 844 pixels.
- Logs are in `artifacts/logs/site-*.log`. No remote deployment was performed.
