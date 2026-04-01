"""YAML-backed configuration for mouse-research using pydantic-settings."""
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_PATH = Path.home() / ".mouse-research" / "config.yaml"

DEFAULT_VAULT_PATH = str(
    Path.home()
    / "Documents"
    / "Obsidian Vault"
    / "01-Aumen-Film-Co"
    / "Projects"
    / "MOUSE"
    / "Research"
)


class VaultSettings(BaseModel):
    path: str = DEFAULT_VAULT_PATH


class OcrSettings(BaseModel):
    primary_engine: str = "glm-ocr"
    ollama_url: str = "http://localhost:11434"
    fallback_engine: str = "tesseract"


class BrowserSettings(BaseModel):
    headless: bool = True
    chrome_executable: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(yaml_file=str(CONFIG_PATH))

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


def _write_default_config() -> None:
    """Write default config.yaml with comments for discoverability."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# mouse-research configuration
# Generated automatically — edit as needed

vault:
  path: "{DEFAULT_VAULT_PATH}"

ocr:
  primary_engine: glm-ocr
  ollama_url: http://localhost:11434
  fallback_engine: tesseract

browser:
  headless: true
  chrome_executable: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome

rate_limit_seconds: 5.0
log_level: INFO
"""
    CONFIG_PATH.write_text(content)


def get_config() -> AppConfig:
    """Load config, creating default config.yaml if it does not exist."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        _write_default_config()
    return AppConfig()
