#!/usr/bin/env python3
"""Automatic File Organizer - main entry point.

Examples:
    python organizer.py --source ~/Downloads
    python organizer.py --source ~/Downloads --mode date --preview
    python organizer.py --undo
    python organizer.py --source ~/Downloads --duplicates
    python organizer.py --source ~/Downloads --schedule 6
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style
from tqdm import tqdm

from config import LOG_DIR, MODES, OPERATIONS_DIR, REPORTS_DIR, Config
from logger import setup_logging
from mover import DiskFullError, FileMover, FileMoveError, Operation
from reporter import ReportGenerator
from scanner import FileInfo, FileScanner
from utils import (
    confirm, format_size, month_name, print_error, print_header,
    print_info, print_success, print_warning,
)

logger = logging.getLogger("file_organizer.organizer")


@dataclass
class PlannedMove:
    """A move that WILL happen (used by preview and by the real run)."""

    info: FileInfo
    folder: Path  # destination folder

    @property
    def destination(self) -> Path:
        """Full target path of the file."""
        return self.folder / self.info.name


class FileOrganizer:
    """Plans, performs and undoes file organization."""

    def __init__(
        self,
        source: Path | str | None,
        dest: Path | str | None = None,
        config: Config | None = None,
        recursive: bool = False,
        operations_dir: Path = OPERATIONS_DIR,
    ) -> None:
        self.config = config or Config()
        self.source: Path | None = Path(source).expanduser().resolve() if source else None
        # Without --dest, files are organized inside the source folder itself.
        self.dest: Path | None = (
            Path(dest).expanduser().resolve() if dest else self.source
        )
        self.recursive = recursive
        self.operations_dir = operations_dir
        self.scanner = FileScanner(self.config)
        self.mover = FileMover()

    # -------------------------------------------------------------- planning
    def _require_source(self) -> Path:
        """Return the source folder or raise if none was given."""
        if self.source is None:
            raise ValueError("A source folder is required for this action")
        return self.source

    def get_destination_folder(self, info: FileInfo, mode: str) -> Path:
        """Work out which folder a file belongs in for the given mode."""
        assert self.dest is not None
        year, month = str(info.modified.year), month_name(info.modified)

        if mode == "type":
            return self.dest / info.category
        if mode == "date":
            return self.dest / year / month
        if mode == "size":
            if info.size < self.config.small_limit_bytes:
                label = "Small"
            elif info.size > self.config.large_limit_bytes:
                label = "Large"
            else:
                label = "Medium"
            return self.dest / label
        if mode == "combined":
            return self.dest / info.category / year / month
        raise ValueError(f"Unknown mode '{mode}'. Choose from: {', '.join(MODES)}")

    def _make_plan(self, mode: str) -> list[PlannedMove]:
        """Scan the source and decide where every file will go."""
        source = self._require_source()
        if mode not in MODES:
            raise ValueError(f"Unknown mode '{mode}'. Choose from: {', '.join(MODES)}")

        skip: list[Path] = []
        if self.dest and self.dest != source and source in self.dest.parents:
            skip.append(self.dest)  # don't re-scan an output folder inside the source

        files = self.scanner.scan_directory(source, self.recursive, skip_dirs=skip)
        plan = []
        for info in files:
            folder = self.get_destination_folder(info, mode)
            if info.path.parent == folder:  # already in the right place
                continue
            plan.append(PlannedMove(info, folder))
        return plan

    # --------------------------------------------------------------- preview
    def preview_organize(self, mode: str = "type") -> list[PlannedMove]:
        """Show what WOULD happen without touching any file; returns the plan."""
        plan = self._make_plan(mode)
        print_header(f"Preview ({mode} mode)")
        if not plan:
            print_info("Nothing to organize.")
            return plan

        sizes: Counter[str] = Counter()
        counts: Counter[str] = Counter()
        folders: Counter[Path] = Counter()
        for move in plan:
            counts[move.info.category] += 1
            sizes[move.info.category] += move.info.size
            folders[move.folder] += 1

        print(f"{Style.BRIGHT}{len(plan)} files will be moved\n")
        print(f"{Style.BRIGHT}By category")
        for category in sorted(counts):
            print(f"  {category:<14}{counts[category]:>6} files  {format_size(sizes[category]):>10}")

        if mode != "type":
            print(f"\n{Style.BRIGHT}Destination folders")
            assert self.dest is not None
            for folder in sorted(folders):
                print(f"  {os.path.relpath(folder, self.dest):<28}{folders[folder]:>6} files")

        print(f"\n{Style.BRIGHT}Sample moves")
        for move in plan[:10]:
            print(f"  {move.info.name}  {Fore.CYAN}->{Style.RESET_ALL}  {move.folder}")
        if len(plan) > 10:
            print(f"  ... and {len(plan) - 10} more")
        return plan

    # -------------------------------------------------------------- organize
    def organize(
        self,
        mode: str = "type",
        plan: list[PlannedMove] | None = None,
        show_progress: bool = True,
    ) -> ReportGenerator:
        """Move the files and save an undo log. Returns the run report."""
        source = self._require_source()
        if plan is None:
            plan = self._make_plan(mode)

        report = ReportGenerator(source, self.dest, mode)
        operations: list[Operation] = []
        logger.info("Organizing %s in '%s' mode (%d files)", source, mode, len(plan))

        for move in tqdm(plan, desc="Organizing", unit="file", disable=not show_progress):
            try:
                operations.append(self.mover.move_file(move.info.path, move.destination))
                report.record_move(move.info)
            except DiskFullError as exc:
                report.record_error(str(exc))
                print_error("Disk is full - stopping. Free some space and run again.")
                break
            except FileMoveError as exc:
                report.record_error(str(exc))

        if operations:
            self._save_operation_log(operations, mode)
        report.finish()
        return report

    # ------------------------------------------------------------ operation log
    def _save_operation_log(self, operations: list[Operation], mode: str) -> Path:
        """Write the undo log for this run as JSON."""
        self.operations_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.operations_dir / f"ops_{stamp}.json"
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "source": str(self.source),
            "dest": str(self.dest),
            "mode": mode,
            "operations": [op.to_dict() for op in operations],
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        logger.info("Saved operation log %s", path)
        return path

    def _latest_log(self) -> Path | None:
        """Return the newest not-yet-undone operation log, if any."""
        if not self.operations_dir.exists():
            return None
        logs = sorted(self.operations_dir.glob("ops_*.json"))
        return logs[-1] if logs else None

    # ------------------------------------------------------------------ undo
    def undo_organize(self, assume_yes: bool = False) -> bool:
        """Reverse the most recent organize run. Returns True if everything was restored."""
        log_path = self._latest_log()
        if log_path is None:
            print_warning("Nothing to undo - no operation log found.")
            return False

        try:
            with log_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            operations = [Operation.from_dict(item) for item in data["operations"]]
        except (OSError, ValueError, KeyError) as exc:
            print_error(f"Could not read operation log {log_path.name}: {exc}")
            logger.error("Bad operation log %s: %s", log_path, exc)
            return False

        print_header("Undo last run")
        print(f"Run from   : {data.get('timestamp')}")
        print(f"Source     : {data.get('source')}")
        print(f"Mode       : {data.get('mode')}")
        print(f"Files      : {len(operations)}")
        if not assume_yes and not confirm("Move all these files back?"):
            print_info("Undo cancelled.")
            return False

        stop_dir = Path(data["dest"]) if data.get("dest") else None
        restored, failures = self.mover.rollback(operations, stop_dir)
        print_success(f"Restored {restored} of {len(operations)} files.")

        if failures:
            for op, reason in failures[:10]:
                print_error(f"  {Path(op.dest).name}: {reason}")
            # Keep only the failed moves so a later --undo can retry them.
            data["operations"] = [op.to_dict() for op, _ in failures]
            with log_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            return False

        # Rename so the *previous* run becomes the next one that can be undone.
        log_path.rename(log_path.with_suffix(".undone"))
        return True

    # ------------------------------------------------------------ duplicates
    def handle_duplicates(
        self, keep: str | None = None, assume_yes: bool = False
    ) -> ReportGenerator:
        """Find duplicate files, show them, and optionally delete extras.

        Args:
            keep: ``'newest'`` or ``'oldest'`` to delete the others; ``None`` asks.
            assume_yes: Skip the final delete confirmation.
        """
        source = self._require_source()
        files = self.scanner.scan_directory(source, recursive=True)
        groups = self.scanner.find_duplicates(files)
        report = ReportGenerator(source, self.dest, "duplicates")
        report.set_duplicates(groups)

        print_header("Duplicate files")
        if not groups:
            print_success("No duplicates found.")
            report.finish()
            return report

        for number, group in enumerate(groups.values(), start=1):
            print(f"{Style.BRIGHT}Group {number}{Style.RESET_ALL} ({format_size(group[0].size)} each)")
            for info in sorted(group, key=lambda f: f.modified):
                print(f"  {info.modified:%Y-%m-%d %H:%M}  {info.path}")

        if keep is None:
            try:
                choice = input(
                    f"\n{Fore.YELLOW}Delete duplicates? Keep [n]ewest, [o]ldest or [s]kip: "
                ).strip().lower()
            except EOFError:
                choice = "s"
            keep = {"n": "newest", "o": "oldest"}.get(choice[:1])
        if keep is None:
            print_info("No files deleted.")
            report.finish()
            return report

        victims: list[FileInfo] = []
        for group in groups.values():
            ordered = sorted(group, key=lambda f: f.modified)  # oldest first
            keeper = ordered[-1] if keep == "newest" else ordered[0]
            victims.extend(f for f in group if f.path != keeper.path)

        total = sum(v.size for v in victims)
        print(f"\n{len(victims)} files ({format_size(total)}) will be deleted, keeping the {keep} copy.")
        if not assume_yes and not confirm("Permanently delete them?"):
            print_info("No files deleted.")
            report.finish()
            return report

        for victim in tqdm(victims, desc="Deleting", unit="file"):
            try:
                victim.path.unlink()
                report.record_deleted(victim)
                logger.info("Deleted duplicate %s", victim.path)
            except OSError as exc:
                message = f"Could not delete {victim.path}: {exc}"
                logger.error(message)
                report.record_error(message)
        report.finish()
        return report


# ---------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    """Create the command line parser."""
    parser = argparse.ArgumentParser(
        description="Automatically organize files into folders (with preview, undo and scheduling).",
    )
    parser.add_argument("--source", help="folder to organize (e.g. ~/Downloads)")
    parser.add_argument("--dest", help="where to put organized files (default: inside --source)")
    parser.add_argument("--mode", choices=MODES, help="type (default), date, size or combined")
    parser.add_argument("--preview", action="store_true", help="show the plan and ask before moving")
    parser.add_argument("--undo", action="store_true", help="reverse the last organize run")
    parser.add_argument("--duplicates", action="store_true", help="find (and optionally delete) duplicates")
    parser.add_argument("--keep", choices=("newest", "oldest"), help="with --duplicates: which copy to keep")
    parser.add_argument("--schedule", type=float, metavar="HOURS", help="run automatically every HOURS hours")
    parser.add_argument("--recursive", action="store_true", help="also organize files inside sub-folders")
    parser.add_argument("--yes", "-y", action="store_true", help="skip confirmation questions")
    parser.add_argument("--config", help="path to a custom config.json")
    parser.add_argument("--add-category", action="append", metavar="NAME=ext1,ext2",
                        help="add a category or extensions to one (saved in config)")
    parser.add_argument("--exclude", action="append", metavar="FOLDER",
                        help="add a folder name to ignore (saved in config)")
    parser.add_argument("--report", choices=("txt", "json", "both"), help="also export the final report")
    parser.add_argument("--verbose", action="store_true", help="log debug details")
    return parser


def export_report(report: ReportGenerator, fmt: str) -> None:
    """Write the report to the reports folder in the requested format(s)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt in ("txt", "both"):
        print_info(f"Report saved: {report.export_to_txt(REPORTS_DIR / f'report_{stamp}.txt')}")
    if fmt in ("json", "both"):
        print_info(f"Report saved: {report.export_to_json(REPORTS_DIR / f'report_{stamp}.json')}")


def apply_config_changes(args: argparse.Namespace, config: Config) -> bool:
    """Handle --add-category / --exclude. Returns True if the config changed."""
    changed = False
    for spec in args.add_category or []:
        name, sep, exts = spec.partition("=")
        extensions = [e for e in exts.split(",") if e.strip()]
        if not sep or not name.strip() or not extensions:
            raise ValueError(f"Invalid --add-category '{spec}'. Use NAME=ext1,ext2")
        config.add_category(name.strip(), extensions)
        print_success(f"Category '{name.strip()}' now handles: {', '.join(extensions)}")
        changed = True
    for folder in args.exclude or []:
        config.add_exclude(folder)
        print_success(f"Folder '{folder}' will be ignored")
        changed = True
    if changed:
        config.save()
    return changed


def run_scheduled(organizer: FileOrganizer, mode: str, hours: float) -> None:
    """Organize now, then repeat every ``hours`` hours until Ctrl+C."""
    import schedule  # imported here so other commands work even without it

    if hours <= 0:
        raise ValueError("--schedule needs a positive number of hours")

    def job() -> None:
        try:
            print_info(f"[{datetime.now():%Y-%m-%d %H:%M}] Scheduled run starting")
            organizer.organize(mode).print_stats()
        except Exception as exc:  # keep the scheduler alive no matter what
            logger.exception("Scheduled run failed")
            print_error(f"Scheduled run failed: {exc}")

    job()
    schedule.every(hours).hours.do(job)
    print_success(f"Scheduled every {hours:g} hour(s). Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)


def main(argv: list[str] | None = None) -> int:
    """Program entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    config = Config(args.config)
    setup_logging(LOG_DIR, config.log_retention_days, args.verbose)

    try:
        changed = apply_config_changes(args, config)
        if changed and not (args.source or args.undo):
            return 0

        if args.undo:
            return 0 if FileOrganizer(None, config=config).undo_organize(args.yes) else 1

        if not args.source:
            parser.error("--source is required (or use --undo)")

        mode = args.mode or config.default_mode
        organizer = FileOrganizer(args.source, args.dest, config, args.recursive)

        if args.duplicates:
            report = organizer.handle_duplicates(args.keep, args.yes)
        elif args.schedule is not None:
            run_scheduled(organizer, mode, args.schedule)
            return 0
        else:
            if args.preview:
                plan = organizer.preview_organize(mode)
                if not plan:
                    return 0
                if not args.yes and not confirm("\nProceed with these moves?"):
                    print_info("Cancelled - no files were moved.")
                    return 0
                report = organizer.organize(mode, plan=plan)
            else:
                report = organizer.organize(mode)

        report.print_stats()
        if args.report:
            export_report(report, args.report)
        return 1 if report.errors else 0

    except (FileNotFoundError, NotADirectoryError) as exc:
        print_error(str(exc))
        logger.error(str(exc))
        return 1
    except PermissionError as exc:
        print_error(f"Permission denied: {exc}")
        logger.error("Permission denied: %s", exc)
        return 1
    except ValueError as exc:
        print_error(str(exc))
        return 2
    except KeyboardInterrupt:
        print_warning("\nStopped by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
