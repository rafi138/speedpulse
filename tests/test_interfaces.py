import pytest

from speedpulse.core.interfaces import (
    default_route_interface,
    is_loopback,
    is_virtual,
    is_vpn,
    physical_interfaces,
    select_interfaces,
    selectable_interfaces,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("lo", True),
        ("lo0", True),
        ("Loopback Pseudo-Interface 1", True),
        ("eth0", False),
        ("wlan0", False),
        ("wlp3s0", False),
        ("enp0s3", False),
        ("Ethernet", False),
        ("Wi-Fi", False),
        ("docker0", True),
        ("veth1a2b3c", True),
        ("br-a1b2c3", True),
        ("virbr0", True),
        ("vboxnet0", True),
        ("vmnet1", True),
        ("vEthernet (WSL)", True),
        ("vethernet (Default Switch)", True),
        ("ifb0", True),
    ],
)
class TestIsVirtual:
    def test_classification(self, name, expected):
        assert is_virtual(name) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("lo", True),
        ("lo0", True),
        ("lo2", True),
        ("eth0", False),
        ("lorem0", False),  # 'lo' is exact-match only
    ],
)
class TestIsLoopback:
    def test_classification(self, name, expected):
        assert is_loopback(name) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("tun0", True),
        ("tap9", True),
        ("wg0", True),
        ("wg-office", True),
        ("utun3", True),
        ("ppp0", True),
        ("ipsec0", True),
        ("eth0", False),
        ("docker0", False),
        ("wlan0", False),
    ],
)
class TestIsVpn:
    def test_classification(self, name, expected):
        assert is_vpn(name) is expected


NAMES = ["eth0", "wlan0", "tun0", "docker0", "lo"]


class TestSelection:
    def test_default_excludes_vpn_and_virtual(self):
        assert select_interfaces(NAMES) == ["eth0", "wlan0"]

    def test_include_vpn(self):
        assert select_interfaces(NAMES, include_vpn=True) == ["eth0", "tun0", "wlan0"]

    def test_user_exclusion_wins(self):
        assert select_interfaces(NAMES, excluded={"eth0"}) == ["wlan0"]

    def test_user_can_exclude_vpn_even_when_included(self):
        result = select_interfaces(NAMES, include_vpn=True, excluded={"tun0"})
        assert result == ["eth0", "wlan0"]

    def test_physical_interfaces_never_include_virtual(self):
        assert physical_interfaces(NAMES) == ["eth0", "wlan0"]

    def test_selectable_interfaces_show_physical_and_vpn(self):
        assert selectable_interfaces(NAMES) == ["eth0", "tun0", "wlan0"]


class TestDefaultRoute:
    def test_never_raises(self):
        result = default_route_interface(timeout=1.0)
        assert result is None or isinstance(result, str)
