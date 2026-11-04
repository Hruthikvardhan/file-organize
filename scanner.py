"""FileScanner: discovers files, describes them and finds duplicates."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

from config import Config
from utils import is_hidden, is_system_file, md5_hash

logger = logging.getLogger("file_organizer.scanner")


@dataclass(frozen=True)
class FileInfo:
    """Immutable description of one file."""

    path: Path
    name: str
    extension: str  # lowercase, without the dot ("" if none)
    size: int  # bytes
    modified: datetime
    category: str


class FileScanner:
    """Scans folders and gathers information about the files inside."""

    def __init__(self, config: Config) -> None:
        self.config = config

    # ------------------------------------------------------------ filters
    def _should_skip_file(self, path: Path) -> bool:
        """Skip hidden files, system files, symlinks and unfinished downloads."""
        if path.is_symlink():
            return True
        if is_hidden(path) or is_system_file(path):
            return True
        return path.suffix.lower().lstrip(".") in self.config.skip_extensions

    def _should_skip_dir(self, path: Path, skip_dirs: set[Path]) -> bool:
        """Skip hidden, excluded and explicitly ignored directories."""
        if path.name.lower() in self.config.exclude_folders:
            return True
        if is_hidden(path) or path.is_symlink():
            return True
        try:
            return path.resolve() in skip_dirs
        except OSError:
            return True

    # ------------------------------------------------------------ scanning
    def scan_directory(
        self,
        path: Path | str,
        recursive: bool = False,
        skip_dirs: Iterable[Path] | None = None,
    ) -> list[FileInfo]:
        """Return a FileInfo for every eligible file in ``path``.

        Args:
            path: Directory to scan.
            recursive: Also descend into sub-folders.
            skip_dirs: Extra directories to ignore (e.g. the destination folder).

        Raises:
            FileNotFoundError: If the directory does not exist.
            NotADirectoryError: If ``path`` is a file.
        """
        root = Path(path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Source folder not found: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Source is not a folder: {root}")

        ignored = set()
        for directory in skip_dirs or []:
            try:
                ignored.add(Path(directory).resolve())
            except OSError:
                continue

        def on_error(error: OSError) -> None:
            logger.warning("Cannot read folder %s: %s", getattr(error, "filename", "?"), error)

        results: list[FileInfo] = []
        for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
            current = Path(dirpath)
            # Editing dirnames in place tells os.walk which folders to enter.
            dirnames[:] = [d for d in dirnames if not self._should_skip_dir(current / d, ignored)]
            for filename in filenames:
                file_path = current / filename
                if self._should_skip_file(file_path):
                    logger.debug("Skipping %s", file_path)
                    continue
                try:
                    results.append(self.get_file_info(file_path))
                except OSError as exc:
                    logger.warning("Cannot read %s: %s", file_path, exc)
            if not recursive:
                break

        logger.info("Scanned %s: %d eligible files", root, len(results))
        return results

    def get_file_info(self, path: Path | str) -> FileInfo:
        """Collect name, extension, size, modified date and category of a file."""
        file_path = Path(path)
        stats = file_path.stat()
        extension = file_path.suffix.lower().lstrip(".")
        return FileInfo(
            path=file_path,
            name=file_path.name,
            extension=extension,
            size=stats.st_size,
            modified=datetime.fromtimestamp(stats.st_mtime),
            category=self.get_file_type(extension),
        )

    def get_file_type(self, extension: str) -> str:
        """Map an extension to its category name ('Others' if unknown)."""
        return self.config.get_category(extension)

    # ---------------------------------------------------------- duplicates
    def find_duplicates(
        self, files: list[FileInfo], show_progress: bool = True
    ) -> dict[str, list[FileInfo]]:
        """Group files with identical content using MD5 hashes.

        Optimisation: files with a unique size cannot be duplicates, so only
        files that share a size are actually hashed. Empty files are ignored.

        Returns:
            Mapping of ``md5 -> [files]`` containing only groups of 2+ files.
        """
        by_size: dict[int, list[FileInfo]] = defaultdict(list)
        for info in files:
            if info.size > 0:
                by_size[info.size].append(info)

        candidates = [info for group in by_size.values() if len(group) > 1 for info in group]
        by_hash: dict[str, list[FileInfo]] = defaultdict(list)

        iterator = tqdm(candidates, desc="Hashing files", unit="file", disable=not show_progress)
        for info in iterator:
            try:
                by_hash[md5_hash(info.path)].append(info)
            except OSError as exc:
                logger.error("Could not hash %s: %s", info.path, exc)

        duplicates = {h: group for h, group in by_hash.items() if len(group) > 1}
        logger.info("Found %d duplicate groups", len(duplicates))
        return duplicates
