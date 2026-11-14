# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-15

### Fixed

- The bundled Qt xcb platform plugin requires the xcb-util library family
  at runtime; PyInstaller does not bundle them and the deb did not declare
  them all, so the app could fail to start on X11 sessions on minimal
  systems. The deb now declares the complete set, CI bundles it, and a new
  X11 boot smoke test guards it.
- macOS bundle ships the SpeedPulse icon (.icns) and version metadata.

### Added

- Floating widget (large draggable on-desktop rates display), tray layout
  and text size options — see the 0.1.0 unreleased notes below for detail.

## [Unreleased]

### Added

- **Floating widget**: draggable, resizable, always-on-top desktop display
  with large green/blue rates — for panels whose tray slot is too small to
  hold legible tray text. Enable from the tray menu or Settings; position
  and size are remembered.
- **Tray layout & text size options**: choose between two-line (square) and
  side-by-side (wide, text-width-sized) tray text, and scale the tray text
  size from 0.6x to 2x in Settings.
- Live download/upload throughput in the system tray, sampled from OS
  interface counters with suspend/resume and counter-reset guards.
- Per-interface selection with automatic filtering of loopback and virtual
  interfaces (docker, bridges, veth, VMware/VirtualBox); VPN tunnels opt-in.
- Bits-per-second or bytes-per-second display, decimal or 1024-based units.
- Tray text rendered with a contrasting outline for legibility on light and
  dark panels; HiDPI-aware rendering.
- Settings dialog: units, update interval, interface selection, tray text
  colour, launch-at-login.
- Launch-at-login support: XDG autostart (Linux), HKCU Run key (Windows),
  LaunchAgent plist (macOS, App-Translocation-safe).
- Single-instance enforcement via OS-level advisory file locks.
- Configuration as TOML with safe defaults, clamping and forward-compatible
  parsing; corrupt or partial config files never crash the app.
- Test suite: pure-core unit tests plus offscreen GUI smoke tests; CI across
  Linux/Windows/macOS on Python 3.11–3.14 with ruff and pyright gates.

[Unreleased]: https://github.com/rafi138/speedpulse/compare/v0.1.0...HEAD
