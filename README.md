# SpeedPulse

> The pulse of your connection, in your tray. Live network throughput for
> Windows, macOS and Linux — with speed tests on the way.

**Status: early development (v0.1).** SpeedPulse lives in your system tray
and shows your real-time download/upload throughput, measured from the OS's
interface counters — no external servers involved.

## Features (v0.1)

- **Live throughput** — aggregate down/up rates updated every second
- **Floating widget** — a large, draggable, always-on-top desktop display
  for when the tray slot is too small; resizable, position remembered
- **Adjustable tray text** — two-line (square) or side-by-side (wide)
  layout, 0.6x–2x text size
- **Per-interface control** — physical interfaces by default; virtual
  interfaces (docker, bridges, loopback) filtered out; VPN tunnels opt-in
- **Bits or bytes** — Mbps or MB/s, decimal or 1024-based units
- **Dark & light panels** — outlined tray text that stays legible anywhere
- **Launch at startup** — app-managed autostart, no installer tricks
- **Single instance** — starting it twice just focuses the running app
- **Settings that persist** — plain TOML in your config directory

## Roadmap

| Release | Scope |
|---|---|
| v0.1 (in progress) | Live throughput tray app |
| v0.2 | Speed tests: built-in HTTP backend, optional Ookla CLI integration (never bundled), LibreSpeed for self-hosters; scheduled + on-demand |
| v0.3 | History with graphs, data-usage totals, data-cap alerts, CSV/JSON export |
| v1.0 | Polished installers: `.deb`, Windows installer + portable, macOS dmg — all built by CI from a git tag |

## Install

**PyPI (once the v0.1.0 publish job has run):**

```bash
pip install speedpulse        # or: pipx install speedpulse
```

**From the GitHub releases** (preferred for end users): grab the `.deb`,
Windows installer/portable, or macOS dmg from the
[releases page](https://github.com/rafi138/speedpulse/releases).

**From source:**

```bash
git clone https://github.com/rafi138/speedpulse
cd speedpulse
python -m venv .venv && source .venv/bin/activate
pip install -e .
speedpulse
```

- Linux (GNOME): tray icons require the *AppIndicator and KStatusNotifierItem
  Support* extension (pre-installed on Ubuntu). KDE, Xfce, Cinnamon, MATE
  and most other desktops show tray icons natively.
- Windows/macOS: no extra requirements.

## Platform notes

- **GNOME**: see above — this is a GNOME Shell limitation, not a SpeedPulse
  one. SpeedPulse detects when the tray icon cannot be shown and logs a hint.
- **Unsigned builds**: until code signing is set up, Windows may show a
  SmartScreen prompt and macOS Gatekeeper requires *System Settings →
  Privacy & Security → Open Anyway* on first launch.

## Development

```bash
pip install -e ".[dev]"
pre-commit install
pytest            # pure-core tests + offscreen GUI smoke tests
ruff check . && ruff format --check .
pyright src tests
```

The codebase is strictly split: `src/speedpulse/core/` is pure Python
(headless-testable, no GUI imports); `src/speedpulse/ui/` is a thin Qt
adapter layer. See [PLAN.md](PLAN.md) for the full architecture and roadmap.

## Contributing

Contributions are welcome — please open an issue first for anything beyond
small fixes. PRs are reviewed by the maintainer before merging; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
