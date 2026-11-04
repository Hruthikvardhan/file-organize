"""FileMover: safe file moving with duplicate-name handling and rollback."""

from __future__ import annotations

import errno
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("file_organizer.mover")


class FileMoveError(Exception):
    """A single file could not be moved (the run can continue)."""


class DiskFullError(FileMoveError):
    """The destination disk is full (the run should stop)."""


@dataclass
class Operation:
    """One completed move, stored in the undo log."""

    src: str
    dest: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        """Convert to a JSON-serialisable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Operation":
        """Rebuild an Operation from its dict form."""
        return cls(src=data["src"], dest=data["dest"], timestamp=data.get("timestamp", ""))


class FileMover:
    """Moves files and can reverse those moves."""

    def create_folder_if_not_exists(self, path: Path) -> Path:
        """Create ``path`` (and parents) if needed and return it."""
        path.mkdir(parents=True, exist_ok=True)
        return path

    def rename_if_duplicate(self, dest: Path) -> Path:
        """Return a free file name: ``photo.jpg`` -> ``photo_1.jpg`` -> ``photo_2.jpg``."""
        if not dest.exists():
            return dest
        counter = 1
        while True:
            candidate = dest.with_name(f"{dest.stem}_{counter}{dest.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def move_file(self, src: Path | str, dest: Path | str) -> Operation:
        """Move ``src`` to ``dest`` (renaming on name clash) and return the operation.

        Raises:
            DiskFullError: Destination disk has no space left.
            FileMoveError: Permission denied, file in use, file vanished, other OS errors.
        """
        source, target = Path(src), Path(dest)
        if not source.exists():
            raise FileMoveError(f"Source file no longer exists: {source}")

        final: Path | None = None
        try:
            self.create_folder_if_not_exists(target.parent)
            final = self.rename_if_duplicate(target)
            shutil.move(str(source), str(final))
        except PermissionError as exc:
            # On Windows, WinError 32 means another program has the file open.
            if getattr(exc, "winerror", None) == 32:
                message = f"File is in use by another program: {source}"
            else:
                message = f"Permission denied: {source}"
            logger.error(message)
            raise FileMoveError(message) from exc
        except OSError as exc:
            self._cleanup_partial(source, final)
            if exc.errno == errno.ENOSPC:
                message = f"Disk full while moving {source}"
                logger.error(message)
                raise DiskFullError(message) from exc
            message = f"Could not move {source}: {exc}"
            logger.error(message)
            raise FileMoveError(message) from exc

        logger.info("Moved %s -> %s", source, final)
        return Operation(str(source), str(final), datetime.now().isoformat(timespec="seconds"))

    @staticmethod
    def _cleanup_partial(source: Path, partial: Path | None) -> None:
        """Delete a half-copied destination file if the original is still intact."""
        try:
            if partial and partial.exists() and source.exists():
                partial.unlink()
        except OSError:
            pass

    def rollback(
        self, operations: Iterable[Operation], stop_dir: Path | None = None
    ) -> tuple[int, list[tuple[Operation, str]]]:
        """Reverse operations, newest first.

        Args:
            operations: Moves to undo.
            stop_dir: Empty folders are removed upward until (not including) this folder.

        Returns:
            ``(restored_count, failures)`` where failures is a list of
            ``(operation, reason)`` for moves that could not be reversed.
        """
        restored = 0
        failures: list[tuple[Operation, str]] = []

        for op in reversed(list(operations)):
            moved_file, original = Path(op.dest), Path(op.src)
            if not moved_file.exists():
                failures.append((op, "file no longer at its organized location"))
                logger.error("Rollback: %s is missing", moved_file)
                continue
            try:
                self.create_folder_if_not_exists(original.parent)
                restore_to = self.rename_if_duplicate(original)  # never overwrite
                shutil.move(str(moved_file), str(restore_to))
                restored += 1
                logger.info("Restored %s -> %s", moved_file, restore_to)
                self._remove_empty_parents(moved_file, stop_dir)
            except PermissionError:
                failures.append((op, "permission denied or file in use"))
                logger.error("Rollback permission error: %s", moved_file)
            except OSError as exc:
                failures.append((op, str(exc)))
                logger.error("Rollback failed for %s: %s", moved_file, exc)

        return restored, failures

    @staticmethod
    def _remove_empty_parents(path: Path, stop_dir: Path | None) -> None:
        """Remove now-empty folders above ``path`` without ever touching ``stop_dir``."""
        if stop_dir is None:
            return
        parent = path.parent
        while stop_dir in parent.parents:
            try:
                parent.rmdir()  # only succeeds if the folder is empty
            except OSError:
                break
            parent = parent.parent
