"""Configuration handling for the File Organizer.

Loads categories and settings from ``config.json``. If the file is missing
it is created from built-in defaults; if it is corrupt the defaults are used
so the tool never crashes because of a bad config.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("file_organizer.config")

# Folder where logs, operation logs (for undo) and reports are stored.
DATA_DIR: Path = Path.home() / ".file_organizer"
LOG_DIR: Path = DATA_DIR / "logs"
OPERATIONS_DIR: Path = DATA_DIR / "operations"
REPORTS_DIR: Path = DATA_DIR / "reports"

# config.json lives next to the scripts by default.
DEFAULT_CONFIG_PATH: Path = Path(__file__).resolve().parent / "config.json"

MODES: tuple[str, ...] = ("type", "date", "size", "combined")

DEFAULT_CONFIG: dict[str, Any] = {
    "categories": {
        "Images": ["jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "ico", "tiff"],
        "Videos": ["mp4", "avi", "mkv", "mov", "wmv", "flv", "webm"],
        "Audio": ["mp3", "wav", "flac", "aac", "ogg", "m4a"],
        "Documents": ["pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx", "csv"],
        "Code": ["py", "java", "js", "html", "css", "cpp", "c", "json", "xml", "sql"],
        "Archives": ["zip", "rar", "tar", "gz", "7z"],
        "Executables": ["exe", "msi", "dmg", "pkg", "deb"],
    },
    "default_category": "Others",
    "exclude_folders": ["node_modules", ".git", "__pycache__"],
    "skip_extensions": ["crdownload", "part", "tmp", "download", "partial"],
    "size_limits_mb": {"small": 1, "large": 100},
    "log_retention_days": 7,
    "default_mode": "type",
}


def _normalize_ext(ext: str) -> str:
    """Return an extension in canonical form: lowercase, no leading dot."""
    return ext.strip().lower().lstrip(".")


class Config:
    """Holds user configuration and answers category questions."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path: Path = Path(path).expanduser() if path else DEFAULT_CONFIG_PATH
        self.data: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._ext_map: dict[str, str] = {}
        self.load()

    # ------------------------------------------------------------------ I/O
    def load(self) -> None:
        """Load config from disk, falling back to defaults on any problem."""
        if not self.path.exists():
            logger.info("Config %s not found - creating it with defaults", self.path)
            try:
                self.save()
            except OSError as exc:
                logger.warning("Could not write default config: %s", exc)
        else:
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if not isinstance(loaded, dict):
                    raise ValueError("top-level JSON value must be an object")
                self.data.update(loaded)
            except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
                logger.error("Invalid config %s (%s) - using defaults", self.path, exc)
                self.data = copy.deepcopy(DEFAULT_CONFIG)
        self._build_extension_map()

    def save(self) -> None:
        """Write the current configuration back to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)
            handle.write("\n")

    def _build_extension_map(self) -> None:
        """Create a fast extension -> category lookup table."""
        self._ext_map = {}
        for category, extensions in self.data.get("categories", {}).items():
            for ext in extensions:
                self._ext_map[_normalize_ext(ext)] = category

    # ------------------------------------------------------------ accessors
    @property
    def categories(self) -> dict[str, list[str]]:
        """Mapping of category name -> list of extensions."""
        return self.data["categories"]

    @property
    def default_category(self) -> str:
        """Category used for extensions that match nothing else."""
        return str(self.data.get("default_category", "Others"))

    @property
    def exclude_folders(self) -> set[str]:
        """Lower-cased folder names that are never scanned."""
        return {str(name).lower() for name in self.data.get("exclude_folders", [])}

    @property
    def skip_extensions(self) -> set[str]:
        """Extensions of files that are skipped (e.g. unfinished downloads)."""
        return {_normalize_ext(e) for e in self.data.get("skip_extensions", [])}

    @property
    def small_limit_bytes(self) -> int:
        """Files smaller than this are 'Small'."""
        return int(self.data["size_limits_mb"].get("small", 1) * 1024 * 1024)

    @property
    def large_limit_bytes(self) -> int:
        """Files larger than this are 'Large'."""
        return int(self.data["size_limits_mb"].get("large", 100) * 1024 * 1024)

    @property
    def log_retention_days(self) -> int:
        """How many days of log files to keep."""
        return int(self.data.get("log_retention_days", 7))

    @property
    def default_mode(self) -> str:
        """Organization mode used when --mode is not given."""
        mode = str(self.data.get("default_mode", "type"))
        return mode if mode in MODES else "type"

    # ------------------------------------------------------------- queries
    def get_category(self, extension: str) -> str:
        """Return the category for an extension ('Others' if unknown)."""
        return self._ext_map.get(_normalize_ext(extension), self.default_category)

    # ------------------------------------------------------------ mutation
    def add_category(self, name: str, extensions: list[str]) -> None:
        """Add a category, or extend it if it already exists.

        An extension can only belong to one category, so it is removed from
        any other category first.
        """
        cleaned = [_normalize_ext(e) for e in extensions if _normalize_ext(e)]
        for other, exts in self.categories.items():
            if other != name:
                self.categories[other] = [e for e in exts if _normalize_ext(e) not in cleaned]
        existing = self.categories.setdefault(name, [])
        for ext in cleaned:
            if ext not in existing:
                existing.append(ext)
        self._build_extension_map()

    def add_exclude(self, folder_name: str) -> None:
        """Add a folder name to the exclusion list."""
        excludes = self.data.setdefault("exclude_folders", [])
        if folder_name.lower() not in {e.lower() for e in excludes}:
            excludes.append(folder_name)
