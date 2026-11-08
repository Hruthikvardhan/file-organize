# 🗂️ File Organizer

A cross-platform **command-line tool** that cleans up a messy folder (like `Downloads`) by sorting files into tidy sub-folders by **type**, **date**, **size** or a **combination** of type and date.

It is built to be safe on a real folder: it can **preview** everything first, it **never overwrites** a file, and **every run can be undone**. It also finds duplicate files, runs on a schedule and writes logs and reports.

Works on **Windows, macOS and Linux** with **Python 3.10+**.

---

## 📸 Example output

```text
$ python organizer.py --source ~/Downloads --mode combined --preview

Preview (combined mode)
=======================
5 files will be moved

By category
  Audio              1 files         2 B
  Documents          2 files         6 B
  Images             1 files         4 B
  Others             1 files      1.9 MB

Destination folders
  Audio/2026/November              1 files
  Documents/2026/November          2 files
  Images/2026/November             1 files
  Others/2026/November             1 files

Sample moves
  song.mp3  ->  ~/Downloads/Audio/2026/November
  p.jpg     ->  ~/Downloads/Images/2026/November
  ...

Proceed with these moves? [y/N]: y
Organizing: 100%|██████████| 5/5

Report
======
Mode            : combined
Files organized : 5
Total size      : 1.9 MB
Errors: 0
```

---

## ✨ Features

### 📁 Organization modes

| Mode | Result | Example |
| --- | --- | --- |
| `type` (default) | One folder per category | `Downloads/Images/` |
| `date` | Year / month of last modification | `Downloads/2026/November/` |
| `size` | Small (< 1 MB), Medium (1-100 MB), Large (> 100 MB) | `Downloads/Medium/` |
| `combined` | Category + year + month | `Downloads/Images/2026/November/` |

### 🛡️ Safety

- **Preview mode** - see exactly what will happen, then confirm with Y/N (default is No)
- **Undo** - every run saves a JSON operation log; `--undo` reverses the last run completely (run it again to go back one more run)
- **Never overwrites** - a name clash becomes `photo_1.jpg`, `photo_2.jpg` ...
- **Skips** hidden files, system files (`desktop.ini`, `Thumbs.db`, `.DS_Store`), symlinks, unfinished downloads (`.crdownload`, `.part`, `.tmp`) and excluded folders (`node_modules`, `.git`, ...)

### 🔍 Duplicate finder

- Groups identical files using **MD5** (only files with the same size are hashed)
- Shows each group with modified dates
- Deletes the extras and keeps the **newest** or **oldest** copy (asks first)

### ⏰ Scheduling

- `--schedule 6` organizes now and then **every 6 hours** (decimals allowed)
- A failed run is logged and never stops the scheduler

### ⚙️ Custom configuration

- Add your own categories and extensions, exclude folders, change size limits - all in `config.json`
- `--add-category "Ebooks=epub,mobi"` and `--exclude Projects` save to the config for you
- A corrupt config falls back to safe defaults

### 📝 Logging and reports

- `organizer.log` records every operation with a timestamp; `errors.log` records errors only
- Daily rotation, the last **7 days** are kept
- End-of-run report: files organized, per-category count and size, total size, duplicates found, errors
- `--report txt|json|both` saves the report to a file

### 🎨 Nice to use

- `tqdm` progress bars and `colorama` coloured output (works on every OS)
- Clear error messages for: permission denied, file in use, disk full, folder not found

---

## 🛠 Tech stack

| Technology | Purpose |
| --- | --- |
| Python 3.10+ | Language |
| `os`, `pathlib`, `shutil` | Scanning and moving files |
| `argparse` | Command-line interface |
| `logging` | Rotating log files |
| `json` | Config, undo logs, reports |
| `hashlib` | MD5 for duplicate detection |
| `datetime`, `re` | Dates and text handling |
| `schedule` | Run every X hours |
| `colorama` | Coloured output |
| `tqdm` | Progress bars |

---

## 🧩 Classes

| Class | File | Responsibility |
| --- | --- | --- |
| `FileScanner` | `scanner.py` | `scan_directory`, `get_file_info`, `get_file_type`, `find_duplicates` |
| `FileMover` | `mover.py` | `move_file`, `rename_if_duplicate`, `create_folder_if_not_exists`, `rollback` |
| `FileOrganizer` | `organizer.py` | `organize`, `preview_organize`, `undo_organize`, duplicate handling |
| `ReportGenerator` | `reporter.py` | `generate_summary`, `print_stats`, `export_to_txt`, `export_to_json` |
| `Config` | `config.py` | Loads and updates `config.json` |

---

## 📁 Folder structure

```
file_organizer/
├── organizer.py      # Main entry point: argparse + FileOrganizer
├── scanner.py        # FileScanner
├── mover.py          # FileMover
├── reporter.py       # ReportGenerator
├── config.py         # Config (reads config.json)
├── logger.py         # Rotating log files
├── utils.py          # Helpers (sizes, MD5, hidden files, colours)
├── config.json       # Categories and settings (edit me!)
├── requirements.txt
└── README.md
```

Files the tool writes (in your home folder):

```
~/.file_organizer/
├── logs/         organizer.log, errors.log
├── operations/   ops_<date>_<time>.json   (undo history)
└── reports/      report_<date>_<time>.txt / .json
```

---

## 🚀 Getting started

### Prerequisites

- Python 3.10 or newer
- pip

### Installation

```bash
# 1. Go into the project folder
cd file_organizer

# 2. (Recommended) create a virtual environment
python -m venv venv
# Windows:   venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# 3. Install the three packages
pip install -r requirements.txt
```

---

## 💻 Usage

```bash
python organizer.py --source ~/Downloads                  # organize by type
python organizer.py --source ~/Downloads --dest ~/Organized
python organizer.py --source ~/Downloads --mode date
python organizer.py --source ~/Downloads --mode size
python organizer.py --source ~/Downloads --mode combined
python organizer.py --source ~/Downloads --preview        # show plan, ask Y/N
python organizer.py --undo                                # reverse the last run
python organizer.py --source ~/Downloads --duplicates     # find duplicates
python organizer.py --source ~/Downloads --duplicates --keep newest
python organizer.py --source ~/Downloads --schedule 6     # every 6 hours
```

> 💡 First time? Start with `--preview`.

### All options

| Option | Description |
| --- | --- |
| `--source PATH` | Folder to organize |
| `--dest PATH` | Where to put the organized folders (default: inside the source) |
| `--mode` | `type` (default), `date`, `size`, `combined` |
| `--preview` | Show what will happen and ask before moving |
| `--undo` | Reverse the most recent run |
| `--duplicates` | Find duplicate files (MD5) and optionally delete extras |
| `--keep newest\|oldest` | With `--duplicates`: which copy to keep |
| `--schedule HOURS` | Run now, then every HOURS hours (Ctrl+C to stop) |
| `--recursive` | Also organize files inside sub-folders |
| `--yes`, `-y` | Skip confirmation questions |
| `--config PATH` | Use a different config file |
| `--add-category NAME=ext1,ext2` | Add a category or extensions (saved) |
| `--exclude FOLDER` | Never scan this folder name (saved) |
| `--report txt\|json\|both` | Also export the final report |
| `--verbose` | Log debug details |

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Finished with errors (or folder not found / nothing to undo) |
| 2 | Bad input (wrong option value, missing `--source`) |
| 130 | Stopped with Ctrl+C |

---

## ⚙️ Configuration (`config.json`)

```json
{
  "categories": {
    "Images": ["jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "ico", "tiff"],
    "Documents": ["pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx", "csv"]
  },
  "default_category": "Others",
  "exclude_folders": ["node_modules", ".git", "__pycache__"],
  "skip_extensions": ["crdownload", "part", "tmp", "download", "partial"],
  "size_limits_mb": { "small": 1, "large": 100 },
  "log_retention_days": 7,
  "default_mode": "type"
}
```

(The real file contains all eight categories - see `config.json`.)

---

## 🧩 Key technical concepts

### 1. Plan first, then act

`FileOrganizer` builds a list of `PlannedMove` objects before touching a single file. Preview simply prints that plan; a real run executes it. This is what makes preview and undo easy.

### 2. Undo via an operation log

Every moved file is recorded as `{src, dest, timestamp}` and saved as JSON - even if you press Ctrl+C halfway. `--undo` reads the newest log and moves every file back, newest move first, without overwriting anything.

### 3. Fast duplicate detection

Files with a unique size cannot be duplicates, so only same-size files are hashed. Hashing reads 1 MB chunks, so even huge files use almost no memory.

### 4. Defensive error handling

Custom exceptions (`FileMoveError`, `DiskFullError`) let one bad file be skipped while a full disk stops the run cleanly. Bad config or log folders never crash the tool.

---

## 🧪 Testing

A full manual test plan is in `4_manual_testing.txt` (85 test cases) together with a script that builds a ready-made test folder.

---

## 🔮 Future enhancements

- [ ] Real-time folder watching (instead of a timer)
- [ ] Unit tests with `pytest`
- [ ] Detect file type from content, not just the extension
- [ ] Choose which older run to undo
- [ ] Simple GUI

---

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

---

<p align="center">Built with ❤️ in Python</p>
