"""
Configuration management for genealogy-extractors.

Config file location: ~/.genealogy-extractors/config.json

If no config file exists, defaults to SQLite database.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Config directory and file
CONFIG_DIR = Path.home() / ".genealogy-extractors"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default configuration (SQLite, no external dependencies)
DEFAULT_CONFIG = {
    "database": {
        "type": "sqlite",  # "sqlite" or "postgresql"
        # SQLite settings (used when type="sqlite")
        "sqlite_path": str(CONFIG_DIR / "genealogy.db"),
        # PostgreSQL settings (used when type="postgresql")
        "host": "localhost",
        "port": 5432,
        "database": "genealogy",
        "user": "postgres",
        "password": ""
    },
    "api": {
        "endpoint": "",
        "key": ""
    },
    "chrome": {
        "debug_port": 9222,
        "debug_host": "127.0.0.1"
    }
}

_config: Optional[Dict[str, Any]] = None


def _ensure_config_dir():
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load configuration from file, or return defaults."""
    global _config
    
    if _config is not None:
        return _config
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
            # Merge with defaults (user config takes precedence)
            _config = _deep_merge(DEFAULT_CONFIG.copy(), user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[CONFIG] Warning: Failed to load {CONFIG_FILE}: {e}")
            print("[CONFIG] Using default configuration (SQLite)")
            _config = DEFAULT_CONFIG.copy()
    else:
        _config = DEFAULT_CONFIG.copy()
    
    return _config


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_database_config() -> Dict[str, Any]:
    """Get database configuration."""
    return load_config()["database"]


def get_api_config() -> Dict[str, Any]:
    """Get API configuration."""
    return load_config()["api"]


def get_chrome_config() -> Dict[str, Any]:
    """Get Chrome CDP configuration."""
    return load_config()["chrome"]


def is_postgresql() -> bool:
    """Check if using PostgreSQL."""
    return get_database_config().get("type", "sqlite") == "postgresql"


def get_sqlite_path() -> str:
    """Get SQLite database path."""
    _ensure_config_dir()
    return get_database_config().get("sqlite_path", str(CONFIG_DIR / "genealogy.db"))


def create_example_config():
    """Create an example config file."""
    _ensure_config_dir()
    example = CONFIG_DIR / "config.example.json"
    
    example_config = {
        "database": {
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "genealogy",
            "user": "postgres",
            "password": "your_password_here"
        },
        "api": {
            "endpoint": "https://your-kindred-instance.com/api/graphql",
            "key": "your_api_key_here"
        }
    }
    
    with open(example, "w") as f:
        json.dump(example_config, f, indent=2)
    
    print(f"[CONFIG] Created example config at {example}")
    print(f"[CONFIG] Copy to {CONFIG_FILE} and edit with your settings")

