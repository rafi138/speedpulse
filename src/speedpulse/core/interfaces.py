"""Interface classification and selection.

Naming follows what the OS reports via psutil: ``eth0``, ``wlp3s0``,
``Ethernet``, ``Wi-Fi``, ``vEthernet (WSL)``, ``utun3``, ...
"""

from __future__ import annotations

import re
import subprocess

VIRTUAL_PREFIXES = (
    "docker",  # docker0, docker_gwbridge
    "veth",  # veth1a2b3c
    "br-",  # br-a1b2c3 (docker bridges)
    "virbr",  # virbr0 (libvirt NAT bridge)
    "vir",  # vnet*, virbr* catch-all used by the reference project
    "vbox",  # vboxnet0
    "vmnet",  # vmnet1 (VMware host virtual)
    "vethernet",  # vEthernet (WSL / Default Switch) — compared lowercased
    "ifb",  # ifb0 (Intermediate Functional Block)
    "nat",  # nat64/cli NAT interfaces on some distros
)

LOOPBACK_EXACT = frozenset({"lo", "lo0", "lo1", "lo2", "lo3", "loopback"})
LOOPBACK_PREFIXES = ("loopback",)  # Windows: "Loopback Pseudo-Interface 1"

VPN_PREFIXES = (
    "tun",  # tun0/tun1 (OpenVPN, generic TUN devices)
    "tap",  # tap0
    "wg",  # wg0, wg-quick names
    "ppp",  # ppp0 (dial-in / some mobile helpers)
    "utun",  # macOS utun0..utunN (system + VPN tunnels)
    "ipsec",  # ipsec0
    "gretap",  # GRE tunnels
)


def _matches(name: str, prefixes: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return lowered.startswith(prefixes)


def is_loopback(name: str) -> bool:
    lowered = name.lower()
    return lowered in LOOPBACK_EXACT or lowered.startswith(LOOPBACK_PREFIXES)


def is_virtual(name: str) -> bool:
    return is_loopback(name) or _matches(name, VIRTUAL_PREFIXES)


def is_vpn(name: str) -> bool:
    return _matches(name, VPN_PREFIXES)


def physical_interfaces(names: list[str]) -> list[str]:
    """Names of physical interfaces (no loopback, virtual, or tunnels), sorted."""
    return sorted(n for n in names if not is_virtual(n) and not is_vpn(n))


def selectable_interfaces(names: list[str]) -> list[str]:
    """Interfaces a user may toggle in settings: physical plus VPN tunnels."""
    return sorted(n for n in names if not is_virtual(n) or is_vpn(n))


def select_interfaces(
    names: list[str],
    *,
    include_vpn: bool = False,
    excluded: set[str] | None = None,
) -> list[str]:
    """Which interfaces contribute to the aggregate rate.

    Default: every physical interface. VPN/tunnel interfaces only when
    ``include_vpn`` (aggregating them with their carrier double-counts
    traffic). ``excluded`` removes explicit user choices; exclusions are
    honoured last so users can silence anything, virtual interfaces included.
    """
    excluded = excluded or set()
    selected = [
        n for n in names if (not is_virtual(n) and not is_vpn(n)) or (include_vpn and is_vpn(n))
    ]
    return sorted(n for n in selected if n not in excluded)


_ROUTE_DEV_RE = re.compile(r"dev\s+(\S+)")


def default_route_interface(timeout: float = 2.0) -> str | None:
    """Best-effort name of the interface carrying the default route.

    Returns ``None`` when it cannot be determined (unsupported OS,
    missing tools, no route). Never raises.
    """
    import sys

    if sys.platform == "win32":
        return None  # GetBestInterface needs ctypes; fine to leave None on Windows.
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["route", "-n", "get", "default"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            match = re.search(r"interface:\s+(\S+)", out.stdout)
        else:
            out = subprocess.run(
                ["ip", "route", "get", "1.1.1.1"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            match = _ROUTE_DEV_RE.search(out.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return match.group(1) if match else None
