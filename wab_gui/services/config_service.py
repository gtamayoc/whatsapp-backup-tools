"""
Configuration manager for wab_gui.
Reads/writes 100% compatible TOML configs for wab-archiver and manages local presets in .wab_gui_profiles/.
"""

from __future__ import annotations
import os
import tomllib
from pathlib import Path
from typing import Dict, Any, List

# Standard keys supported by wab-archiver
VALID_CONFIG_KEYS = {
    'output', 'msgstore', 'e2e_key', 'wa_root', 'contacts', 'log',
    'business', 'timezone', 'since', 'ios_backup', 'ios_password', 'ios_contacts',
    'pull_media', 'staging',
}

PROFILES_DIR = Path(".wab_gui_profiles")


class ConfigService:
    """Service to load, save, export, and manage configuration presets."""

    @classmethod
    def ensure_profiles_dir(cls) -> Path:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        return PROFILES_DIR

    @classmethod
    def list_presets(cls) -> List[str]:
        d = cls.ensure_profiles_dir()
        return sorted([f.stem for f in d.glob("*.toml")])

    @classmethod
    def load_toml(cls, file_path: str | Path) -> Dict[str, Any]:
        p = Path(file_path)
        if not p.is_file():
            return {}
        try:
            with open(p, "rb") as f:
                data = tomllib.load(f)
            # Normalize wa_root if string or list
            if "wa_roots" in data and "wa_root" not in data:
                data["wa_root"] = data.pop("wa_roots")
            return {k: v for k, v in data.items() if k in VALID_CONFIG_KEYS}
        except Exception:
            return {}

    @classmethod
    def save_toml(cls, file_path: str | Path, config: Dict[str, Any]) -> bool:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Archivo de configuración generado por wab-gui",
            "# Compatible al 100% con wab-archiver",
            ""
        ]

        for k, v in sorted(config.items()):
            if k not in VALID_CONFIG_KEYS or v is None or v == "":
                continue

            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            elif isinstance(v, list):
                # Array of strings
                formatted_items = ", ".join(f'"{item.replace(chr(92), "/")}"' for item in v)
                lines.append(f"{k} = [{formatted_items}]")
            else:
                # String path
                clean_str = str(v).replace("\\", "/")
                lines.append(f'{k} = "{clean_str}"')

        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return True
        except Exception:
            return False

    @classmethod
    def save_preset(cls, preset_name: str, config: Dict[str, Any]) -> bool:
        d = cls.ensure_profiles_dir()
        dest = d / f"{preset_name}.toml"
        return cls.save_toml(dest, config)

    @classmethod
    def load_preset(cls, preset_name: str) -> Dict[str, Any]:
        d = cls.ensure_profiles_dir()
        src = d / f"{preset_name}.toml"
        return cls.load_toml(src)
