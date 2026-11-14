import tomllib

from speedpulse.core.config import Settings, UnitsConfig, _dump_toml, load, save


def test_missing_file_returns_defaults(tmp_path):
    loaded = load(tmp_path / "nope.toml")
    assert loaded == Settings()


def test_roundtrip_preserves_everything(tmp_path):
    settings = Settings()
    settings.units.use_bits = True
    settings.units.binary_units = True
    settings.display.theme = "dark"
    settings.sampler.interval_seconds = 2.5
    settings.sampler.max_gap_seconds = 4.0
    settings.sampler.include_vpn = True
    settings.sampler.excluded_interfaces = ["eth0", "vEthernet (WSL)"]
    settings.autostart = True

    path = tmp_path / "config.toml"
    save(path, settings)
    assert load(path) == settings


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("this is [ not toml", encoding="utf-8")
    assert load(path) == Settings()


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[units]\nuse_bits = true\nfuture_option = "whatever"\n[no_such_section]\nx = 1\n',
        encoding="utf-8",
    )
    loaded = load(path)
    assert loaded.units.use_bits is True
    assert loaded == Settings(units=UnitsConfig(use_bits=True))


def test_interval_is_clamped(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[sampler]\ninterval_seconds = 50.0\n", encoding="utf-8")
    assert load(path).sampler.interval_seconds == 10.0

    path.write_text("[sampler]\ninterval_seconds = 0.01\n", encoding="utf-8")
    assert load(path).sampler.interval_seconds == 0.25


def test_invalid_types_fall_back(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[units]\nuse_bits = "yes"\n[sampler]\ninclude_vpn = 1\n',
        encoding="utf-8",
    )
    loaded = load(path)
    assert loaded.units.use_bits is False
    assert loaded.sampler.include_vpn is False


def test_dump_is_valid_toml():
    settings = Settings()
    settings.sampler.excluded_interfaces = ["eth0"]
    data = tomllib.loads(_dump_toml(settings))
    assert data["version"] == 1
    assert data["units"]["use_bits"] is False
    assert data["sampler"]["excluded_interfaces"] == ["eth0"]


def test_empty_string_list_round_trips(tmp_path):
    settings = Settings()
    path = tmp_path / "config.toml"
    save(path, settings)
    assert load(path).sampler.excluded_interfaces == []
