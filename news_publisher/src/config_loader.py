import json
import os


REQUIRED_SECTIONS = [
    "news", "translation", "formatting",
    "whatsapp", "facebook", "scheduler",
    "storage", "logging",
]


def load_config(config_path: str = "config.json") -> dict:
    """Load config.json and do basic structural validation."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: '{config_path}'.\n"
            "Copy config.json.example to config.json and fill in your credentials."
        )

    with open(config_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)

    missing = [k for k in REQUIRED_SECTIONS if k not in config]
    if missing:
        raise ValueError(f"Config is missing required sections: {missing}")

    return config
