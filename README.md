# File Organizer

A command-line tool that sorts a messy folder (like Downloads) into tidy
sub-folders by **type**, **date**, **size** or a **combination**. It can preview
changes, undo the last run, find duplicate files and run on a schedule.

Works on Windows, macOS and Linux with Python 3.10+.

## Install

```bash
cd file_organizer
python -m venv venv
# Windows:  venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Only three small packages are used: `schedule`, `colorama`, `tqdm`.

## Usage

```bash
python organizer.py --source ~/Downloads                 # organize by type
python organizer.py --source ~/Downloads --dest ~/Organized
python organizer.py --source ~/Downloads --mode date     # 2026/April/...
python organizer.py --source ~/Downloads --mode size     # Small / Medium / Large
python organizer.py --source ~/Downloads --mode combined # Images/2026/April/...
python organizer.py --source ~/Downloads --preview       # show plan, ask Y/N
python organizer.py --undo                               # reverse the last run
python organizer.py --source ~/Downloads --duplicates    # find duplicates
python organizer.py --source ~/Downloads --duplicates --keep newest
python organizer.py --source ~/Downloads --schedule 6    # every 6 hours
```

### All options

| Option | Meaning |
|---|---|
| `--source PATH` | Folder to organize |
| `--dest PATH` | Output folder (default: inside the source) |
| `--mode` | `type` (default), `date`, `size`, `combined` |
| `--preview` | Show what will happen and ask before moving |
| `--undo` | Reverse the most recent run (repeat to go further back) |
| `--duplicates` | Group identical files (MD5), optionally delete extras |
| `--keep newest\|oldest` | With `--duplicates`: which copy to keep |
| `--schedule HOURS` | Run now, then every HOURS hours (Ctrl+C to stop) |
| `--recursive` | Also organize files inside sub-folders |
| `--yes`, `-y` | Skip confirmation questions |
| `--config PATH` | Use a different config file |
| `--add-category NAME=ext1,ext2` | Add a category/extensions (saved) |
| `--exclude FOLDER` | Never scan this folder name (saved) |
| `--report txt\|json\|both` | Export the final report |
| `--verbose` | Debug-level logging |

Examples of customising:

```bash
python organizer.py --add-category "Ebooks=epub,mobi,azw3"
python organizer.py --exclude Projects
```

## Where things are stored

Everything the tool writes lives in `~/.file_organizer/`:

- `logs/organizer.log` - every operation (7 days kept)
- `logs/errors.log` - errors only (7 days kept)
- `operations/ops_*.json` - undo logs, one per run
- `reports/` - exported reports

## Safety

- Hidden files, system files (`desktop.ini`, `.DS_Store`...), symlinks and
  unfinished downloads (`.crdownload`, `.part`, `.tmp`) are skipped.
- Existing files are never overwritten: name clashes become `name_1.ext`, `name_2.ext`.
- Every run writes an undo log. Use `--preview` the first time.
- Deleting duplicates is permanent (always asks first unless `--yes`).

## Project layout

```
organizer.py   CLI + FileOrganizer (plan / preview / organize / undo / duplicates)
scanner.py     FileScanner (scan, file info, type lookup, MD5 duplicates)
mover.py       FileMover (move, rename on clash, create folders, rollback)
reporter.py    ReportGenerator (summary, terminal stats, txt/json export)
config.py      Config loading and category lookup
logger.py      Rotating log files
utils.py       Helpers (sizes, hashing, hidden files, coloured output)
config.json    Categories and settings
```
