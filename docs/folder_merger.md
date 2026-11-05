# Folder Merger
Moves everything inside the subfolders of one or more "parent" folders into a single destination folder, and can undo the move.

## What it does
- For each parent folder, takes every subfolder and moves the items inside it into the destination.
- When a folder with the same name already exists in the destination, the contents are merged into it.
- When a file with the same name exists, the moved file gets a number, for example `report (1).pdf`.
- Files lying directly in a parent folder are skipped.
- **Undo Last Move** moves everything back.
- Shows a log and a separate list of errors.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python folders\folder_merger.py`.
2. Click **Add Parent Folder(s)** for each parent folder. Use **Remove Selected** to take one off the list.
3. Click **Select Destination**.
4. Click **Move & Merge Contents**. Read the summary and click **Yes**.
5. If the result is not what you wanted, click **Undo Last Move** before you close the window.

## Example
Parent folder `Downloads` has subfolders `Batch1` and `Batch2`. With destination `All`, the files from `Downloads\Batch1` and `Downloads\Batch2` all end up in `All`.

## Safety notes
- Files are **moved**, not copied. The tool asks before it starts.
- Existing files are never overwritten. A number is added to the moved file instead.
- Folders that become empty after a merge are removed.
- The destination cannot be inside a parent folder. The tool refuses this, because files would be moved into themselves.
- Each move is recorded as it happens, so **Undo Last Move** also works when a run stops part way.
- The undo list is kept in memory only. It is lost when you close the window.

## Troubleshooting
- **"Error moving ...: Access is denied"**: the file is open in another program. Close it and run again.
- **Undo says it cannot find a file**: that file was moved or deleted after the merge.
- **A whole subfolder was not moved**: only the contents of subfolders are moved. Add the folder above it as the parent folder.

## How it works
The move runs in a background thread. `shutil.move` moves each item, and a recursive function merges folders that already exist in the destination. Windows paths get the `\\?\` prefix for long paths. Log lines and message boxes are passed to the main thread with `root.after`, because tkinter widgets must only be changed on the main thread.
