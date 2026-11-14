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


def test_exotic_strings_round_trip(tmp_path):
    settings = Settings()
    settings.sampler.excluded_interfaces = ['eth"0', "nün", "back\\slash"]
    path = tmp_path / "config.toml"
    save(path, settings)
    text = path.read_text(encoding="utf-8")
    assert "nün" in text  # literal UTF-8, never JSON surrogate-pair escapes
    assert load(path) == settings


def test_save_leaves_no_temp_file_behind(tmp_path):
    path = tmp_path / "config.toml"
    save(path, Settings())
    assert list(tmp_path.iterdir()) == [path]


def test_tray_layout_validation(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[display]\nlayout = "wide"\n', encoding="utf-8")
    assert load(path).display.layout == "wide"

    path.write_text('[display]\nlayout = "diagonal"\n', encoding="utf-8")
    assert load(path).display.layout == "stacked"  # invalid -> default


def test_text_scale_is_clamped(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[display]\ntext_scale = 5.0\n", encoding="utf-8")
    assert load(path).display.text_scale == 2.0

    path.write_text("[display]\ntext_scale = 0.05\n", encoding="utf-8")
    assert load(path).display.text_scale == 0.6


def test_display_options_round_trip(tmp_path):
    settings = Settings()
    settings.display.layout = "wide"
    settings.display.text_scale = 1.5
    path = tmp_path / "config.toml"
    save(path, settings)
    assert load(path).display == settings.display


def test_widget_config_round_trip_and_clamps(tmp_path):
    settings = Settings()
    settings.widget.enabled = True
    settings.widget.font_pt = 42
    settings.widget.x = 150
    settings.widget.y = -80
    settings.widget.width = 320
    settings.widget.height = 110
    path = tmp_path / "config.toml"
    save(path, settings)
    assert load(path).widget == settings.widget

    path.write_text(
        "[widget]\nfont_pt = 500\nwidth = 99999\nheight = 1\nx = -99999\n", encoding="utf-8"
    )
    loaded = load(path).widget
    assert loaded.font_pt == 96  # clamped to MAX_WIDGET_FONT_PT
    assert loaded.width == 1200
    assert loaded.height == 50
    assert loaded.x == -10000
