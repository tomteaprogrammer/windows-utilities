# Folder Structure Analyzer
Scans a folder and saves reports that show every folder and file, how deep it is, its size and its date — useful before reorganizing a messy drive.

## What it does
- Walks the folder and all subfolders.
- Saves a CSV with type, depth, name, relative path, size, date modified and full path for every item.
- Saves a TXT tree view (with `├──`, `└──` and `│` lines) of the whole structure.
- Saves a log of the run next to the reports.
- Can skip files with chosen extensions.
- Shows the deepest level found when it finishes.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python folders\folder_structure_analyzer.py`.
2. Click **Browse...** next to **Folder to Analyze:**.
3. Click **Browse...** next to **Save Reports To:** and choose where the reports go. If you leave it empty, the tool asks when you start.
4. Optional: tick **Ignore specific file extensions:** and edit the list.
5. Click **Start Analysis**. Click **Stop** to end early.

## Settings and options
- **Ignore specific file extensions:** comma-separated list. The default is `.DS_Store, .tmp, .log, Thumbs.db`.

## Safety notes
- Read-only for the folder you analyze. Nothing in it is changed.
- Three new files are saved in the folder you chose: `<folder>_Analysis_<date>_<time>.csv`, `.txt` and `.log`. The date and time in the name keep older reports from being replaced.

## Troubleshooting
- **"Cannot access file" warnings**: you do not have permission to read those files. They are left out of the reports.
- **Excel shows odd characters in the CSV**: open Excel first and use **Data > From Text/CSV**, choosing UTF-8.
- **The scan is slow**: very large folders take time. Watch the status line for the item count.

## How it works
`os.walk` runs in a background thread and collects one dictionary per item. The CSV is written with `csv.DictWriter`. The tree view is built from the relative paths of all items and drawn with an explicit stack, folders before files, so the `├──` / `└──` / `│` prefixes are correct at every level. Settings are read from the window before the thread starts, and progress goes back through `root.after`.
