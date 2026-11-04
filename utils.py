"""Small shared helpers: formatting, hashing, hidden-file checks, console output."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

# autoreset=True makes every print return to the default colour automatically.
colorama_init(autoreset=True)

MONTH_NAMES: tuple[str, ...] = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# File names that belong to the operating system or file managers.
SYSTEM_FILE_NAMES: frozenset[str] = frozenset({
    "desktop.ini", "thumbs.db", "ehthumbs.db", ".ds_store", ".localized",
    "pagefile.sys", "hiberfil.sys", "swapfile.sys", "ntuser.dat",
})

# Windows file attribute bits (see GetFileAttributes docs).
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4


# ------------------------------------------------------------- formatting
def format_size(num_bytes: float) -> str:
    """Convert a byte count into a human readable string (e.g. ``1.5 MB``)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - loop always returns


def month_name(moment: datetime) -> str:
    """Return the English month name (locale independent, so folders are stable)."""
    return MONTH_NAMES[moment.month - 1]


# ---------------------------------------------------------------- hashing
def md5_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute the MD5 digest of a file, reading it in chunks.

    Reading in 1 MB chunks keeps memory usage tiny even for multi-GB files.
    MD5 is fine here: we only detect identical files, not defend against attackers.
    """
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------ hidden/system files
def _windows_attributes(path: Path) -> int:
    """Return Windows file attribute flags (0 on other platforms)."""
    try:
        return getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return 0


def is_hidden(path: Path) -> bool:
    """True for dot-files (Mac/Linux) and files with the Windows hidden flag."""
    return path.name.startswith(".") or bool(_windows_attributes(path) & FILE_ATTRIBUTE_HIDDEN)


def is_system_file(path: Path) -> bool:
    """True for well-known OS files and files with the Windows system flag."""
    return (
        path.name.lower() in SYSTEM_FILE_NAMES
        or bool(_windows_attributes(path) & FILE_ATTRIBUTE_SYSTEM)
    )


# ------------------------------------------------------------ user prompts
def confirm(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question and return the answer.

    Non-interactive sessions (no stdin) get the default instead of crashing.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        try:
            answer = input(f"{Fore.YELLOW}{prompt}{suffix}{Style.RESET_ALL}").strip().lower()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.")


# -------------------------------------------------------- coloured output
def print_info(message: str) -> None:
    """Print a neutral informational line in cyan."""
    print(f"{Fore.CYAN}{message}")


def print_success(message: str) -> None:
    """Print a success line in green."""
    print(f"{Fore.GREEN}{message}")


def print_warning(message: str) -> None:
    """Print a warning line in yellow."""
    print(f"{Fore.YELLOW}{message}")


def print_error(message: str) -> None:
    """Print an error line in red (to stderr)."""
    print(f"{Fore.RED}{message}", file=sys.stderr)


def print_header(title: str) -> None:
    """Print a bold section header with an underline."""
    print(f"\n{Style.BRIGHT}{Fore.MAGENTA}{title}")
    print(f"{Fore.MAGENTA}{'=' * len(title)}")
