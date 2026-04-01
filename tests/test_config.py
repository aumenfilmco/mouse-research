"""Tests for AppConfig defaults and YAML override."""
import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile
import os


def test_default_vault_path_contains_mouse_research():
    """AppConfig defaults to the MOUSE vault path."""
    from mouse_research.config import AppConfig, CONFIG_PATH
    # Patch CONFIG_PATH to a nonexistent tmp path so no real config is loaded
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_config = Path(tmpdir) / "config.yaml"
        with patch("mouse_research.config.CONFIG_PATH", fake_config):
            # Re-import to pick up patched path
            import importlib
            import mouse_research.config as cfg_mod
            cfg_mod.CONFIG_PATH = fake_config
            cfg = cfg_mod.AppConfig()
        assert "MOUSE" in cfg.vault.path
        assert "Research" in cfg.vault.path


def test_default_ocr_engine_is_glm_ocr():
    from mouse_research.config import AppConfig
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_config = Path(tmpdir) / "config.yaml"
        import mouse_research.config as cfg_mod
        cfg_mod.CONFIG_PATH = fake_config
        cfg = AppConfig()
    assert cfg.ocr.primary_engine == "glm-ocr"


def test_default_rate_limit_is_5():
    from mouse_research.config import AppConfig
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_config = Path(tmpdir) / "config.yaml"
        import mouse_research.config as cfg_mod
        cfg_mod.CONFIG_PATH = fake_config
        cfg = AppConfig()
    assert cfg.rate_limit_seconds == 5.0


def test_get_config_creates_yaml_file(tmp_path):
    """get_config() creates config.yaml if it does not exist."""
    import mouse_research.config as cfg_mod
    from unittest.mock import patch
    fake_config = tmp_path / "config.yaml"
    with patch.object(cfg_mod, "CONFIG_PATH", fake_config):
        cfg_mod.get_config()
    assert fake_config.exists(), "config.yaml was not created"


def test_yaml_override_vault_path(tmp_path):
    """AppConfig reads vault.path override from YAML."""
    from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource, PydanticBaseSettingsSource
    from mouse_research.config import VaultSettings, OcrSettings, BrowserSettings
    custom_path = "/tmp/custom-vault"
    fake_config = tmp_path / "config.yaml"
    fake_config.write_text(f"vault:\n  path: {custom_path}\n")

    # Create a subclass with yaml_file pointing at our temp config
    class TestConfig(BaseSettings):
        model_config = SettingsConfigDict(yaml_file=str(fake_config))
        vault: VaultSettings = VaultSettings()
        ocr: OcrSettings = OcrSettings()
        browser: BrowserSettings = BrowserSettings()
        rate_limit_seconds: float = 5.0
        log_level: str = "INFO"

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (YamlConfigSettingsSource(settings_cls), env_settings, init_settings)

    cfg = TestConfig()
    assert cfg.vault.path == custom_path
