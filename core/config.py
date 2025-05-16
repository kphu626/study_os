from pathlib import Path
import json
from typing import Optional

from pydantic import BaseModel, Field

CONFIG_FILE_PATH = Path("config/app_settings.json")


class AppConfig(BaseModel):
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    notes_path: Path = Field(default_factory=lambda: Path("data") / "notes.json")
    tasks_path: Path = Field(default_factory=lambda: Path("data") / "tasks.json")
    flashcards_path: Path = Field(
        default_factory=lambda: Path("data") / "flashcards.json"
    )
    progress_path: Path = Field(default_factory=lambda: Path("data") / "progress.json")

    assets_dir: Path = Field(default_factory=lambda: Path("data") / "assets")

    # Display settings
    # Will be set by ThemeManager default if None
    theme_name: Optional[str] = None
    # Will be set by ThemeManager default if None
    font_name: Optional[str] = None
    # Will be set by ThemeManager default if None
    font_size: Optional[int] = None

    def save_config(self):
        """Save current configuration to disk (synchronously)."""
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        json_data = self.model_dump_json(indent=2)
        try:
            with open(CONFIG_FILE_PATH, "w") as f:
                f.write(json_data)
            print(f"[AppConfig] Configuration saved to {CONFIG_FILE_PATH}")
        except Exception as e:
            print(f"[AppConfig] Error saving config synchronously: {e}")

    @staticmethod
    def load_config() -> "AppConfig":
        """Load configuration from disk, or return default if not found/invalid."""
        if CONFIG_FILE_PATH.exists():
            try:
                with open(CONFIG_FILE_PATH, "r") as f:
                    data = json.load(f)
                config = AppConfig(**data)
                print(f"[AppConfig] Configuration loaded from {CONFIG_FILE_PATH}")
                return config
            except json.JSONDecodeError:
                print(
                    f"[AppConfig] Error decoding JSON from {CONFIG_FILE_PATH}. Using default config."
                )
            except Exception as e:  # Catch other Pydantic validation errors or issues:
                print(f"[AppConfig] Error loading config: {e}. Using default config.")
        else:
            print(
                f"[AppConfig] Config file {CONFIG_FILE_PATH} not found. Using default config."
            )

        # Ensure data directory exists for a new default config
        default_config = AppConfig()
        default_config.data_dir.mkdir(parents=True, exist_ok=True)
        default_config.assets_dir.mkdir(parents=True, exist_ok=True)
        # Attempt to save the new default config immediately so it exists for next time.
        # This is a synchronous call for simplicity during initial load.
        try:
            CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE_PATH, "w") as f:
                f.write(default_config.model_dump_json(indent=2))
            print(
                f"[AppConfig] Default configuration created and saved to {CONFIG_FILE_PATH}"
            )
        except Exception as e:
            print(f"[AppConfig] Error saving initial default config: {e}")

        return default_config


# Ensure AppConfig fields are Paths as intended after Pydantic initialization
# This is usually handled by Pydantic if types are correct, but explicit conversion can be added if needed.
# For example, in a post-init or validator if complex Path logic was required.
