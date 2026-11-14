# Contributing to SpeedPulse

Thanks for your interest in improving SpeedPulse! This project accepts
contributions **with maintainer approval**: every PR is reviewed by the
maintainer before it is merged.

## Ground rules

1. **Open an issue first** for anything that is not a small, obvious fix —
   so we can agree on the approach before you invest time.
2. Keep PRs focused: one logical change per PR.
3. Every PR must keep CI green: lint, type-check, and tests on all three OSes.

## Development setup

```bash
git clone https://github.com/rafi138/speedpulse && cd speedpulse
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

- `pytest` — run the suite (GUI tests run offscreen, so they work anywhere)
- `ruff check . && ruff format .` — lint + format
- `pyright src tests` — type-check

## Architecture rules (please respect them)

- `src/speedpulse/core/` must stay **pure Python**: no GUI/Qt imports, ever.
  Anything testable headless belongs there, with tests.
- `src/speedpulse/ui/` is a thin Qt adapter; business logic does not live there.
- Platform-specific behaviour goes through small per-OS implementations behind
  a common interface (see `core/autostart.py` for the pattern).
- Never bundle third-party proprietary binaries (notably the Ookla CLI) — this
  is a hard licence constraint; see `docs/` when it exists.

## Pull requests

- Add tests for behavioural changes; update `CHANGELOG.md` (the *Unreleased*
  section) in the same PR.
- Describe *what* and *why*; link the issue (`Fixes #123`).
- If your change touches platform code, say which OSes you tested on.

## Commit style

Short imperative subject (`sampler: clamp counter wraps`), no strict format
beyond that. We may introduce Conventional Commits tooling later.

## Reporting bugs

Use the bug issue template — include your OS, desktop environment, install
method, and the output of `speedpulse -v` where applicable.
