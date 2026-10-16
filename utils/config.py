"""Configuration loading, validation, and persistence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from utils.paths import data_root, resource_root


class Config:
    def __init__(self, values: dict[str, Any], user_path: Path) -> None:
        self.values = values
        self.user_path = user_path

    def get(self, dotted_key: str, default: Any = None) -> Any:
        value: Any = self.values
        for part in dotted_key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def set(self, dotted_key: str, value: Any) -> None:
        target = self.values
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    def save(self) -> None:
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.user_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        temporary.replace(self.user_path)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Config:
    default_path = resource_root() / "config.json"
    defaults = json.loads(default_path.read_text(encoding="utf-8"))
    user_path = data_root() / "config.json"
    if user_path.exists():
        try:
            user_values = json.loads(user_path.read_text(encoding="utf-8"))
            defaults = _merge(defaults, user_values)
        except (OSError, json.JSONDecodeError):
            user_path.rename(user_path.with_suffix(".invalid.json"))
    return Config(defaults, user_path)
