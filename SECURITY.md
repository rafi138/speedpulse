# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| latest release on `main` | ✅ |
| older tagged releases | ❌ |

## Reporting a vulnerability

Please report vulnerabilities **privately** via GitHub's *Report a
vulnerability* button on the Security tab (private security advisory). Do not
open a public issue for security problems.

You will get a response within a few days, and credit in the release notes
unless you prefer to remain anonymous.

## Scope notes

SpeedPulse reads local OS network statistics and (from v0.2) performs
internet speed tests. It does not collect telemetry, and speed-test results
never leave your machine. Vulnerabilities that would matter include: local
privilege escalation via config/autostart files, remote code execution via
speed-test backend responses, and unauthorised network egress.
