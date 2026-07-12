# Contributing to Friday

Thank you for considering a contribution to Friday. This project is being built as a serious open-source engineering effort, so clarity, consistency, and maintainability matter as much as feature ideas.

## Guiding expectations

- Prefer clean architecture over quick shortcuts.
- Keep changes scoped and reviewable.
- Preserve the project's intentional boundaries.
- Improve documentation alongside code.
- Treat tests, linting, and typing as part of the implementation.

## Git Flow

Friday follows a lightweight Git Flow model.

### Branches

- `main` — stable, releasable history
- `develop` — integration branch for upcoming work
- `feature/<short-name>` — new work
- `fix/<short-name>` — bug fixes
- `release/<version>` — release preparation when needed

### Workflow

1. Branch from `develop`.
2. Make a focused set of changes.
3. Add or update tests when behavior changes.
4. Run the full quality suite locally.
5. Open a pull request into `develop`.
6. Squash or rebase according to maintainer guidance.

## Coding style

Friday uses automated tooling to keep the codebase consistent.

### Standards

- Python 3.12+
- Black for formatting
- Ruff for linting and import organization
- MyPy for type checking
- Pytest for tests
- Dataclasses for structured configuration objects when appropriate
- `pathlib` over string-based path handling

### Design preferences

- Favor composition over hidden coupling.
- Avoid global state.
- Keep public interfaces small and explicit.
- Add docstrings to public classes.
- Keep modules focused and reasonably small.
- Prefer dependency inversion at system boundaries.

## Pull requests

A high-quality pull request should:

- explain *why* the change is needed
- summarize *what* changed
- describe any architectural implications
- include tests or justify why tests are unnecessary
- pass formatting, linting, typing, and test checks

### PR checklist

- [ ] Code is formatted with Black
- [ ] Ruff passes without errors
- [ ] MyPy passes
- [ ] Pytest passes
- [ ] Documentation has been updated when appropriate
- [ ] Changelog impact has been considered

## Issues

Use GitHub Issues to report bugs, propose improvements, or discuss architecture.

### Before opening an issue

- Search existing issues first.
- Reproduce bugs with the current branch or latest release.
- Provide concise, actionable context.

### Good issue reports include

- expected behavior
- actual behavior
- reproduction steps
- environment details
- logs or screenshots when relevant

## Commit messages

Use clear, imperative commit messages. Conventional Commits are recommended.

### Examples

- `feat: add application bootstrap configuration model`
- `fix: ensure rotating log directory is created before use`
- `docs: expand roadmap for v0.2 architecture goals`
- `test: cover logger singleton behavior`

### Commit message guidance

- Keep the subject line concise.
- Explain intent, not only mechanics.
- Avoid ambiguous messages like `update stuff`.

## Review philosophy

Reviews should be constructive, specific, and architecture-aware. The goal is not only to merge code, but to keep the repository coherent as Friday grows.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Local quality checks

```bash
python -m black --check .
python -m ruff check .
python -m mypy src tests
python -m pytest
```

## Code of collaboration

Be respectful, direct, and generous with context. Friday is intended to be a project that experienced engineers can be proud to build in public.
