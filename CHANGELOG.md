# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

[Unreleased]: https://github.com/OWNER/speedpulse/compare/v0.0.0...HEAD
