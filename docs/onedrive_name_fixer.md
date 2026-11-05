# OneDrive Name Fixer
Finds file and folder names that Windows or OneDrive will not accept, shows you the list, and renames them only after you agree.

## What it does
- Scans a folder and all its subfolders for names with `< > : " / | ? *`, names that start or end with a space or a period, and reserved names such as `CON`, `PRN` or `LPT1`.
- Shows a preview of every planned rename. Nothing is renamed until you click **Yes**.
- Replaces each bad character with `_`. Adds `_` in front of reserved names.
- Saves a text log and an undo file (CSV) in the folder you scanned.
- **Undo a Previous Run...** renames the items back by using the undo file.
- Handles paths longer than 260 characters.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer.
- No extra packages for the window. The command-line mode (used only when tkinter is missing) needs `tqdm`.

## Install
1. Download the repository and unzip it.
2. Optional, for command-line mode: `pip install -r requirements.txt`.

## How to use
1. Run `python renaming\onedrive_name_fixer.py`.
2. Optional: tick **Also replace "~" with "_"** or **Also change ".." to "."**.
3. Click **Select Folder and Start Scan** and choose a folder.
4. Read the preview in the **Processing Log** box.
5. Click **Yes** to rename, or **No** to stop. When it finishes, a message shows where the log and undo file were saved.

## Settings and options
- **Also replace "~" with "_"**: off by default. Windows and OneDrive accept `~`, but some older programs do not.
- **Also change ".." to "."**: off by default. Windows and OneDrive accept double periods.

## Safety notes
- The tool renames files and folders. Nothing is deleted.
- If the new name is already taken, a number is added (for example `report-1.txt`).
- Two files are saved in the root of the folder you scanned:
  - `renamed_files_log_<date>_<time>.txt` – a list of every rename and every error.
  - `renamed_files_undo_<date>_<time>.csv` – the old and new path of every item that was renamed. It is written as each rename happens.
- To undo: click **Undo a Previous Run...**, choose the `renamed_files_undo_....csv` file, and click **Yes**. Items whose old name is in use again are skipped and listed in the log.

## Troubleshooting
- **"Could not rename ... Access is denied"**: the file is open in another program, or you do not have permission. Close the program and scan again.
- **Nothing found, but OneDrive still shows errors**: OneDrive can also reject very long paths or files that are too large. This tool only fixes names.
- **Undo skipped some items**: the item was moved or renamed after the run, or something else now uses the old name.

## How it works
The scan uses `os.walk` in a background thread and builds a rename plan first. The plan is run deepest path first, so a folder is renamed only after everything inside it. On Windows every path gets the `\\?\` long-path prefix. Each successful rename is written to a CSV right away, and undo replays that CSV in reverse order.
