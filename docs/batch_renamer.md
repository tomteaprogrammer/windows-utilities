# Batch Renamer
Renames every file in a folder to one base name plus a number (`Photo_001.jpg`, `Photo_002.jpg` ...), oldest file first.

## What it does
- Lists the files directly inside a folder (not subfolders). Names that start with `.` are skipped.
- Sorts them by date modified, oldest first. Files with the same date are sorted by name.
- Shows a preview table: original name, date, new name.
- Renames only after you confirm.
- Keeps each file's extension.
- Safe to run again on files it already numbered.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python renaming\batch_renamer.py`.
2. Click **Browse...** next to **Select Folder:** and choose a folder.
3. Type a name in **New Base Name:** (the default is `MyFile`).
4. Click **Generate Preview** and check the table.
5. Click **Confirm & Rename Files**, then **Yes**.

## Safety notes
- Files are renamed in place. Nothing is deleted or overwritten.
- Renaming happens in two steps: every file first gets a temporary name, then its final name. This stops new names from clashing with old ones.
- If a new name is already used by something that is not in the list (for example a folder), nothing is renamed and the message tells you which name is taken.
- Any problems are listed in the message at the end.
- There is no undo button. Keep the preview in mind, or make a copy of the folder first.

## Troubleshooting
- **"No valid files found in this folder"**: the folder only has subfolders or hidden files.
- **A file has a name like `~renaming_1a2b3c4d_5.tmp`**: the final rename failed and the original name could not be restored either. The message names the file. Rename it by hand.
- **Order looks wrong**: the order uses "Date modified", not "Date taken" or "Date created".

## How it works
The preview reads `os.path.getmtime` for each file and sorts by `(modified time, name)`. The rename uses two passes of `os.rename`: original to a unique temporary name, then temporary to final. A final name is checked before each step, and a failed step puts the original name back.
