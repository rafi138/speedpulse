# SpeedPulse — Project Plan

> Cross-platform internet speed monitor for the system tray: live up/down throughput,
> on-demand & scheduled speed tests, history, and data-usage tracking.
> Founding plan — 2026-11-14. This file is the working reference for v1 development;
> it can later move to `docs/ARCHITECTURE.md` or be retired once the docs site exists.

---

## 1. Product definition

**SpeedPulse** — "the pulse of your connection, in your tray."

| | |
|---|---|
| Repo / PyPI / binary | `speedpulse` (PyPI verified free 2026-11-14; GitHub near-clean — only a ★1 same-niche repo) |
| License | MIT |
| Platforms | Windows 10/11, macOS 13+, Linux (KDE/XFCE/MATE native; GNOME via AppIndicator extension; Wayland via SNI path) |
| Language | Python ≥ 3.11 (CI on 3.11–3.14) |
| Inspiration | ajxv/netspeed-monitor — **discovered to be a GNOME Shell JS extension, not Python**: GNOME-only, 3s /proc polling, no speed test, no tests/CI/packaging. SpeedPulse is a clean-room build that fills every gap. |

**Two distinct promises, clearly separated in UI and docs** (upstream's issue tracker showed users conflating them):
1. **Live throughput** — what your connection is doing *right now* (OS interface counters, no external servers, ~zero cost).
2. **Speed test** — what your line *can do* (downloads/uploads against test servers; scheduled or on demand).

### Competitive landscape (why this project wins)
- **ajxv/netspeed-monitor**: GNOME-only JS extension; no packaging, no tests, no speed test. 
- **NetSpeedTray** (823★, Python/PyQt6): Windows-only, GPL-3.0. Great feature reference (tiered SQLite history, data-cap alerts) — do not copy code (GPL).
- **TrafficMonitor** (Windows/C++), **exelban/stats** (macOS/Swift, "not open contribution"): each single-OS; SpeedPulse is genuinely cross-platform and contribution-friendly.
- **speedtest-tracker** (self-hosted web): defines the history/alerts layer worth borrowing conceptually (scheduled tests, threshold alerts, CSV export).
- **GNOME net-speed extensions**: dozens at <5★ — GNOME users have no good tray-class option; we support them via AppIndicator with honest docs.

---

## 2. Locked decisions

| Decision | Choice | Rationale (research-backed) |
|---|---|---|
| Product shape | Both live throughput + speed tests, phased | User decision; best roadmap for a public repo |
| Packaging tier | Core three: .deb, Windows installer + portable zip, macOS dmg — all auto-built on git tag | User decision |
| License | MIT | User decision |
| Name | **SpeedPulse** (backup: BandPulse) | Delegated; verified free on PyPI, GitHub near-clean. `netbeat`/`netpace` collide with same-niche repos; `netgauge` is Ookla's own engine name |
| GUI stack | **PySide6** (LGPL-3.0, *not* PyQt6 GPL) | QSystemTrayIcon + settings dialogs + notifications + QLocalSocket single-instance in one dependency; pystray is stale (0.19.5, Sep 2023) and menu-only. **API floor 6.8** (Debian 13 freezes 6.8.2) — CI matrix tests 6.8 / 6.10 / latest |
| Live measurement | `psutil.net_io_counters(pernic=True)` delta sampling, 1 s default | Portable, accurate; nowrap handling built in; raw /proc/WMI layers add nothing |
| Python floor | 3.11 (tomllib), CI 3.11–3.14 | 3.10 went EOL 2026-10-01; PySide6 6.12 abi3 wheels cover 3.10–3.15 on all 5 platform targets |
| Type checker | pyright (pinned) | Fast, native to VSCode; exactly one checker per repo policy |
| Config | TOML via `tomllib` + dataclass validation | Stdlib, no pydantic weight |
| History store | stdlib `sqlite3` (WAL), tiered retention | Proven pattern (raw 24 h → minute 30 d → hourly forever) |
| Build backend | hatchling; `src/` layout; `[project.gui-scripts]` | Current standard |

---

## 3. Architecture — pure core, thin UI

Everything testable lives in `core/` with **zero Qt imports**; `ui/` is an adapter.
This is what keeps the 3-OS test matrix green and meaningful.

```
src/speedpulse/
├── app.py                  # composition root: wiring, Qt event loop, graceful shutdown
├── core/                   # NO Qt/GUI imports — pure, headless-testable
│   ├── sampler.py          # psutil polling loop → byte-counter deltas; clamps; nowrap resets
│   ├── interfaces.py       # NIC discovery, virtual-NIC filter (lo/docker/veth/br-/vir/vbox),
│   │                       #   active-interface via default route per OS, VPN opt-in (tun*/wg*)
│   ├── rates.py            # RateCalculator: delta/elapsed, spike guards, optional smoothing
│   ├── units.py            # bits/bytes, SI scaling, label formatting (single source of truth)
│   ├── config.py           # TOML load/save + dataclass schema + defaults + migration
│   ├── metered.py          # tri-state metered detection, per-OS backends (see §4.3)
│   ├── history.py          # SQLite (WAL), tiered retention, aggregation, CSV/JSON export
│   ├── alerts.py           # data-cap thresholds (80/100%), anomaly rules
│   ├── autostart.py        # per-OS enable/disable/is_enabled (see §5)
│   ├── singleinstance.py   # QLocalSocket/QLocalServer connect-or-serve (IPC: "show settings")
│   └── speedtest/
│       ├── base.py         # Backend protocol → TestResult(download, upload, latency, jitter,
│       │                   #   loaded_latency, server, bytes_used, backend, timestamp)
│       ├── cloudflare.py   # DEFAULT: pure-Python HTTP backend (stdlib urllib + threads),
│       │                   #   ramp-up payload sizing, parallel streams, single+multi results
│       ├── ookla.py        # OPTIONAL: detect `speedtest` on PATH → subprocess
│       │                   #   --accept-license --accept-gdpr --format=jsonl; bytes/s→bits/s;
│       │                   #   EULA-gated in settings; NEVER bundled; fixtures in CI, never live
│       ├── librespeed.py   # LibreSpeed protocol client for self-hosted servers
│       └── scheduler.py    # interval (default 6 h, 1 h floor) + jitter; metered-aware skip;
│                           #   per-test byte budget; manual trigger; pause/resume
└── ui/
    ├── tray.py             # QSystemTrayIcon, menu, label updates (only on value change)
    ├── icon_renderer.py    # QPainter text→QIcon; 16 px Win / 22 px X11; DPR-scaled;
    │                       #   light/dark variants; monochrome fallback
    ├── settings_dialog.py  # units, interval, interfaces, backends + Ookla EULA gate, autostart
    ├── history_window.py   # graphs (QtCharts or custom QWidget), usage totals, export
    └── notifications.py    # showMessage baseline (documented best-effort); Windows toasts w/
                            #   AUMID registration as later enhancement
```

**Threading model**: sampler and speed tests run on QThreads/workers emitting signals to the
tray thread; never block the GUI loop. Overlapping-read guard (a new poll is skipped if the
previous read is still in flight) — pattern inherited from the reference extension.

**Dependency policy**: mandatory = `psutil`, `PySide6`. Platform extras (optional install,
graceful degradation without them): `comtypes` (Windows metered), `dbus-next` (Linux metered),
`pyobjc-framework-Network` (macOS metered). The speedtest HTTP backend uses stdlib only.

---

## 4. Measurement design

### 4.1 Live throughput
- Poll `psutil.net_io_counters(pernic=True, nowrap=True)` every 1 s (configurable 1–5 s).
- Rate = Δbytes / Δ(monotonic seconds). Guards: clamp negative deltas to 0; discard first
  sample after start and after any suspend/resume-length gap; cap display at
  `net_if_stats().speed`; `cache_clear()` if users report frozen values.
- Default view: aggregate of active physical NICs (default-route selection). Per-interface
  selection in settings. VPN interfaces (tun*/wg*) **opt-in** — aggregating them double-counts.
- Update the tray label only when the formatted string changes (CPU/battery discipline).

### 4.2 Speed tests — backend strategy (settled by EULA research)
| Backend | Role | Key facts |
|---|---|---|
| **Cloudflare-style HTTP** | **Default.** Pure Python, MIT-clean, works out of the box | Endpoints `speed.cloudflare.com/__down` & `/__up` are *unofficial* — isolate in one module, defensive parsing, graceful failure |
| **Ookla CLI (user-installed)** | Optional accuracy booster (esp. gigabit links) | EULA research verdict: wrapping is *invited* by Ookla ("use Speedtest in your programs…"); the scary "data extraction" sentence is marketing copy, not license text. Binding constraints: **never bundle/redistribute the binary** (EULA §(e)), personal non-commercial use, results stay local, no Ookla branding. Gate behind an explicit EULA-acceptance toggle linking speedtest.net/about/eula. JSON output is **bytes/s** — convert. CI uses JSON fixtures only (the project itself can't accept the EULA on build servers) |
| **LibreSpeed** | Self-hosters / privacy users | Open protocol, LGPL ecosystem; user supplies server URL |

Scheduler etiquette: full test every 6 h default (hard 1 h floor + jitter), per-test byte
budget surfaced to the user, skip on metered connections.

### 4.3 Metered detection (tri-state: yes / no / unknown)
- **Windows**: `INetworkConnectionCost::GetCost` via `comtypes` (no admin; pywin32 unreliable for this interface).
- **Linux**: NetworkManager D-Bus `Metered` property (manager or Device object — *not* Connection.Active) via `dbus-next`; treat YES & GUESS_YES as metered; `nmcli` subprocess fallback; permanently "unknown" on networkd/ConnMan systems.
- **macOS**: `NWPath.isConstrained` / `isExpensive` via `pyobjc-framework-Network` (this API *does* exist, contrary to common belief). Wrap handler bodies in try/except — exceptions inside libdispatch callbacks hard-crash.
- Scheduler: skip full tests on *yes*; run lightweight probe on *unknown*; manual override in settings.

---

## 5. Platform matrix & per-OS plumbing

| Concern | Windows 10/11 | macOS 13+ | Linux |
|---|---|---|---|
| Tray | QSystemTrayIcon, 16 px | native | KDE/XFCE/MATE/Cinnamon native (SNI); **GNOME requires AppIndicator extension — verified supported through GNOME 51** (ship a detection warning + docs table); Wayland works via the SNI/AppIndicator path |
| Autostart | HKCU `...\CurrentVersion\Run` | **LaunchAgent plist written at runtime** (SMAppService only after Developer-ID signing lands; ad-hoc-signed PyInstaller apps hit `kSMErrorInvalidSignature`). Rules: only register from /Applications, detect App Translocation, strip quarantine xattr from the plist (macOS 27 refuses quarantined plists), rewrite on path change, verify real launchd status (BTM can report enabled while launchd fails exit 78) | XDG `~/.config/autostart/*.desktop` |
| Metered | COM `GetCost` | NWPath flags | NM D-Bus / nmcli |
| Notifications | showMessage now; windows-toasts+AUMID later | showMessage | showMessage / org.freedesktop.Notifications |
| First-launch friction | SmartScreen warning (unsigned) | Gatekeeper: "Open Anyway" in Settings or `xattr -cr` (Sequoia removed right-click Open) | none |
| Single instance | QLocalServer/QLocalSocket (portable) | same | same |

---

## 6. Repository layout

```
speedpulse/
├── .github/
│   ├── workflows/ci.yml          # PR: lint+types+tests, 3 OS × py3.11–3.14, fail-fast false
│   ├── workflows/release.yml     # tag v*.*.* → build matrix → draft release
│   ├── ISSUE_TEMPLATE/{bug.yml,feature.yml}
│   └── PULL_REQUEST_TEMPLATE.md
├── src/speedpulse/               # as in §3
├── tests/                        # unit (pure core, mocked OS), fixtures/ (Ookla JSON, NM dbus),
│                                 #   gui/ (pytest-qt, QT_QPA_PLATFORM=offscreen smoke only)
├── packaging/
│   ├── debian/                   # fpm-over-venv recipe (self-contained; system-python3-pyside6
│   │                             #   exists on Debian/Ubuntu/Fedora — slim variant later)
│   ├── windows/{installer.iss}   # Inno Setup
│   ├── macos/                    # dmg steps
│   └── appimage/                 # linuxdeploy + appimagetool over PyInstaller payload
├── docs/{ARCHITECTURE.md, BACKENDS.md, screenshots/}
├── CONTRIBUTING.md               # PR policy: owner review required (see §9)
├── CODE_OF_CONDUCT.md  SECURITY.md  CHANGELOG.md  README.md  LICENSE
├── pyproject.toml  .pre-commit-config.yaml  .gitignore
```

## 7. Code quality & CI

- **ruff** (lint + format), **pyright** (pinned, `basic` → tighten over time), **pre-commit** (ruff hooks + pyright).
- **pytest** + coverage gate on `core/` (strict), pytest-qt offscreen **smoke-only** for `ui/`
  (GUI tests are the flaky part of 3-OS matrices — keep the weight on the pure core).
- CI matrix: ubuntu/windows/macos × Python 3.11–3.14, `fail-fast: false`, `cache: 'pip'`.
- Mocked-OS fixtures: fake D-Bus service (NM `Metered`), COM stub (`GetCost`), Ookla JSON fixtures.
- Versioning: semver + Keep-a-Changelog; every PR must touch CHANGELOG (_bot prompt in template_).

## 8. Release pipeline (tag `v*.*.*` → draft GitHub Release)

| Artifact | Builder | Notes |
|---|---|---|
| `.deb` | ubuntu-latest: venv install → **fpm** | Self-contained (bundles Qt; expect ~100 MB) — the *universal* artifact: Debian 12 and Ubuntu 24.04 ship **no** PySide6 at all, so system-python packaging only works on Debian 13+/Ubuntu 26.04+/Fedora. A slim system-PySide6 `.deb` variant for those newer bases is a later optimization. Ships `.desktop` to `/usr/share/applications`, icons to `/usr/share/icons/hicolor/{16,22,32,48,64,128,256}/apps` |
| AppImage | linuxdeploy + appimagetool over PyInstaller onedir | For non-debian distros — include (cheap once PyInstaller exists) even though tier is "core three" |
| Windows installer + portable zip | windows-latest: PyInstaller `--windowed` onedir + Inno Setup | Strict `--exclude-module` hygiene (QtWebEngine, Qt3D, …) to control size |
| macOS `.dmg` | macos-15 (arm64): PyInstaller `--windowed` → create-dmg | PySide6 6.12 wheels are macosx_14_0 → **declare macOS 14+ for latest PySide6, or pin an older 6.x for macOS 13 — verify wheel deployment targets at scaffold time** |
| sdist + wheel | same tag | PyPI via **OIDC trusted publishing** (`pipx install speedpulse` = zero-friction path) |
| All | sha256 checksums | softprops/action-gh-release **v3**, `draft: true` |

**Signing economics (documented, deferred)**: unsigned v0.x with README workarounds
(SmartScreen "More info → Run anyway"; macOS "Open Anyway" / `xattr -cr`). Funded milestones:
Azure Artifact Signing ($9.99/mo) + Apple Developer Program ($99/yr) → unlocks Homebrew cask,
SMAppService autostart backend, winget reputation.
**Tier-2 later**: winget (WinGet Releaser action), AUR, snap (needs `network-observe`, not
auto-connect — forum request), flatpak last (no traffic-stat portal; D-Bus tray grants discouraged).

## 9. Governance — "contributions with owner approval"

- Branch protection on `main`: require PR + **1 code-owner approval**, dismiss stale approvals,
  required status checks (lint, types, tests, build-smoke).
- `CODEOWNERS`: `@<owner>` on everything; explicit entries for `packaging/`, `.github/workflows/`.
- CONTRIBUTING.md: issues-first for features; small PRs welcome; conventional-commit-lite
  subjects; DCO sign-off; "your PR will be reviewed by the maintainer before merge" stated plainly.
- Templates: bug (OS/version/install-channel/logs), feature (problem statement first).
- SECURITY.md (private vulnerability reporting), Discussions for Q&A/ideas.

## 10. Roadmap

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 — scaffold** | git init, pyproject (hatchling, gui-scripts), ruff/pyright/pytest/pre-commit configs, MIT LICENSE, CI skeleton, README stub, memory of decisions | CI green on empty core |
| **M1 — live throughput MVP** (v0.1.0) | sampler, interfaces, rates, units, config, tray + icon renderer, settings, single-instance, autostart, dark/light icons | Manual run on all 3 OSes; unit tests ≥ 90 % on touched core |
| **M2 — speed tests** (v0.2.0) | cloudflare backend, ookla detect+gate, librespeed, scheduler + metered skip, results notification | Headless `speedpulse --test` works; backend fixtures tested |
| **M3 — history & usage** (v0.3.0) | SQLite tiered retention, history window + graphs, CSV/JSON export, data-cap alerts (80/100 %) | Export matches UI totals; retention prunes correctly |
| **M4 — release maturity** (v1.0.0) | Full release pipeline, polished README (screenshots, install table, GNOME caveat, Ookla legal notes, comparison), docs/ | Tag → draft release with all artifacts + checksums |

## 11. Risk register (top items)

1. **GNOME tray churn** — AppIndicator extension breaks per GNOME release; mitigation: docs table, runtime detection + warning, companion GNOME Shell extension as a *future* separate deliverable.
2. **Unsigned-binary friction** (SmartScreen, Gatekeeper) — documented workarounds now, signing as funded milestone; publish sha256 for every artifact.
3. **Qt bundle weight** (~60–150 MB installers) — PyInstaller exclude hygiene; acceptable for Qt apps; system-PySide6 slim .deb variant later.
4. **Cloudflare endpoints unofficial** — isolated module, defensive failure, pluggable backends.
5. **CPU/battery regressions** — update-on-change labels, throttled redraws, async polling, tiered retention (this category's classic complaint).
6. **GUI test flakiness on 3 OS** — strict coverage on pure core, smoke-only GUI tests.
7. **VPN double-counting** — tun*/wg* opt-in aggregation.
8. **Name/brand confusion** — never use "Speedtest"/Ookla marks; disambiguate `speedtest-cli` (three unrelated projects share that name) in docs.

## 12. Explicitly deferred (parking lot)

Companion GNOME Shell extension · per-process stats · translations (i18n-ready strings from day one, translations later) · Prometheus/InfluxDB export (speedtest-tracker parity) · Apprise-style webhook notifications · SNR/signal info · homebrew cask / winget / AUR / snap / flathub (tier 2) · code signing.
