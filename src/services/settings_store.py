"""Settings store — load/save Settings model to JSON file in platformdirs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from platformdirs import user_config_dir

from src.models.settings import Settings

logger = logging.getLogger(__name__)

APP_NAME = "whatsapp-notifier"
SETTINGS_FILENAME = "settings.json"


def get_settings_path() -> Path:
    """Return the path to the settings JSON file."""
    config_dir = Path(user_config_dir(APP_NAME))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / SETTINGS_FILENAME


class SettingsStore:
    """Manages loading and saving application settings."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self._settings_path = settings_path or get_settings_path()

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    def load(self) -> Settings:
        """Load settings from JSON file, or create defaults on first run."""
        if not self._settings_path.exists():
            logger.info("Settings file not found, creating defaults")
            settings = Settings()
            self.save(settings)
            return settings

        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
            settings = Settings(**data)
            logger.info("Settings loaded from %s", self._settings_path)
            return settings
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to load settings (%s), using defaults", exc)
            settings = Settings()
            self.save(settings)
            return settings

    def save(self, settings: Settings) -> None:
        """Save settings to JSON file."""
        try:
            data = settings.model_dump(mode="json")
            self._settings_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Settings saved to %s", self._settings_path)
        except OSError as exc:
            logger.error("Failed to save settings: %s", exc)
            raise
