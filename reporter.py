"""ReportGenerator: collects statistics and presents / exports them."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from colorama import Fore, Style

from scanner import FileInfo
from utils import format_size, print_header


class ReportGenerator:
    """Accumulates results of one run and renders a final report."""

    def __init__(self, source: Path | None, dest: Path | None, mode: str) -> None:
        self.source = source
        self.dest = dest
        self.mode = mode
        self.category_counts: dict[str, int] = defaultdict(int)
        self.category_sizes: dict[str, int] = defaultdict(int)
        self.files_organized = 0
        self.total_size = 0
        self.errors: list[str] = []
        self.duplicate_groups: dict[str, list[FileInfo]] = {}
        self.deleted_files = 0
        self.freed_bytes = 0
        self._started = time.perf_counter()
        self._duration = 0.0

    # ----------------------------------------------------------- recording
    def record_move(self, info: FileInfo) -> None:
        """Count one successfully organized file."""
        self.files_organized += 1
        self.total_size += info.size
        self.category_counts[info.category] += 1
        self.category_sizes[info.category] += info.size

    def record_error(self, message: str) -> None:
        """Remember an error message for the report."""
        self.errors.append(message)

    def record_deleted(self, info: FileInfo) -> None:
        """Count a duplicate that was deleted."""
        self.deleted_files += 1
        self.freed_bytes += info.size

    def set_duplicates(self, groups: dict[str, list[FileInfo]]) -> None:
        """Store the duplicate groups found by the scanner."""
        self.duplicate_groups = groups

    def finish(self) -> None:
        """Stop the run timer."""
        self._duration = time.perf_counter() - self._started

    # ------------------------------------------------------------- summary
    def generate_summary(self) -> dict[str, Any]:
        """Return all statistics as a JSON-friendly dictionary."""
        dup_files = sum(len(group) for group in self.duplicate_groups.values())
        wasted = sum(g[0].size * (len(g) - 1) for g in self.duplicate_groups.values())
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": str(self.source) if self.source else None,
            "destination": str(self.dest) if self.dest else None,
            "mode": self.mode,
            "duration_seconds": round(self._duration, 2),
            "files_organized": self.files_organized,
            "total_size_bytes": self.total_size,
            "total_size": format_size(self.total_size),
            "categories": {
                name: {
                    "count": self.category_counts[name],
                    "size_bytes": self.category_sizes[name],
                    "size": format_size(self.category_sizes[name]),
                }
                for name in sorted(self.category_counts)
            },
            "duplicates": {
                "groups": len(self.duplicate_groups),
                "files": dup_files,
                "wasted_bytes": wasted,
                "wasted": format_size(wasted),
                "deleted": self.deleted_files,
                "freed": format_size(self.freed_bytes),
            },
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }

    # -------------------------------------------------------------- output
    def print_stats(self) -> None:
        """Print a coloured report to the terminal."""
        summary = self.generate_summary()
        print_header("Report")
        print(f"Mode            : {summary['mode']}")
        print(f"Files organized : {Style.BRIGHT}{Fore.GREEN}{summary['files_organized']}")
        print(f"Total size      : {summary['total_size']}")
        print(f"Duration        : {summary['duration_seconds']} s")

        if summary["categories"]:
            print(f"\n{Style.BRIGHT}Per category")
            for name, data in summary["categories"].items():
                print(f"  {name:<14}{data['count']:>6} files  {data['size']:>10}")

        dup = summary["duplicates"]
        if dup["groups"]:
            print(f"\n{Fore.YELLOW}Duplicates: {dup['groups']} groups, {dup['files']} files, "
                  f"{dup['wasted']} wasted")
        if dup["deleted"]:
            print(f"{Fore.GREEN}Deleted {dup['deleted']} duplicates, freed {dup['freed']}")

        if summary["errors"]:
            print(f"\n{Fore.RED}Errors: {summary['error_count']}")
            for message in summary["errors"][:10]:
                print(f"{Fore.RED}  - {message}")
            if summary["error_count"] > 10:
                print(f"{Fore.RED}  ... and {summary['error_count'] - 10} more (see errors.log)")
        else:
            print(f"\n{Fore.GREEN}Errors: 0")

    def export_to_txt(self, path: Path | str) -> Path:
        """Write a plain-text report and return its path."""
        summary = self.generate_summary()
        lines = [
            "FILE ORGANIZER REPORT",
            "=====================",
            f"Generated : {summary['generated_at']}",
            f"Source    : {summary['source']}",
            f"Dest      : {summary['destination']}",
            f"Mode      : {summary['mode']}",
            f"Duration  : {summary['duration_seconds']} s",
            "",
            f"Files organized : {summary['files_organized']}",
            f"Total size      : {summary['total_size']}",
            "",
            "Per category:",
        ]
        for name, data in summary["categories"].items():
            lines.append(f"  {name:<14}{data['count']:>6} files  {data['size']:>10}")
        dup = summary["duplicates"]
        lines += [
            "",
            f"Duplicates: {dup['groups']} groups, {dup['files']} files, {dup['wasted']} wasted",
            f"Deleted duplicates: {dup['deleted']} (freed {dup['freed']})",
            "",
            f"Errors: {summary['error_count']}",
        ]
        lines += [f"  - {message}" for message in summary["errors"]]

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out

    def export_to_json(self, path: Path | str) -> Path:
        """Write the full summary as JSON and return its path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            json.dump(self.generate_summary(), handle, indent=2)
        return out
