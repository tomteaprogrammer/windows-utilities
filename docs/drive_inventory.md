# Drive Inventory
Saves a list of every file in a folder, and compares two of those lists to show which files are missing, moved or new — for example after copying a drive to a new computer.

## What it does
- **Scan**: reads the name, size, dates and folder of every file and saves them in one inventory file (`.db`).
- **Compare**: takes an OLD and a NEW inventory and sorts the changes into three tabs: **Missing**, **Moved** and **New / leftover**.
- Shows which files are "online-only" cloud files (**In cloud** column).
- Double-click a row to open its location in File Explorer. Right-click to copy the full path.
- **Export all to CSV...** saves the full result.
- Read-only: it never opens file contents, so it never changes a file and never makes an online-only cloud file download.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python folders\drive_inventory.py`.
2. On the **1. Scan a folder** tab, click **Browse...** next to **Folder to scan:**.
3. Choose where to save the file in **Save inventory as:** and type a name in **This computer's name:**.
4. Click **Start Scan**. Click **Cancel** to stop a scan.
5. Do the same on the other computer (or later on the same one), saving under a different name.
6. On the **2. Compare** tab, choose the **OLD inventory** and the **NEW inventory** and click **Compare**.
7. Read the **Missing**, **Moved** and **New / leftover** tabs. Use **Search file name:** to filter.

## Settings and options
- **Skip hidden folders**: on by default. Skips hidden folders and folders whose name starts with a dot, such as Google Drive cache folders.
- **Also ignore these folder names**: one name per line. `*` and `?` wildcards work, for example `cache*`.

## How files are matched (the Moved rule)
- Two files count as the same file when they have the **same file name and the exact same size**. Dates are not used.
- Same name and size, same folder: **unchanged** (not shown).
- Same name and size, different folder: **Moved**.
- If several files share the same name and size, the old-only paths and the new-only paths are each sorted alphabetically and paired in that order. Any extra old paths are **Missing**, and extra new paths are **New**. With many identical copies, this pairing can differ from what really happened.

## Safety notes
- Scanning and comparing only read file information. No file is changed, moved or deleted.
- If the inventory file already exists, the tool asks before replacing it. Click **No** to choose another name.
- A cancelled scan removes its incomplete inventory file.

## Troubleshooting
- **Very many files show as Moved or Missing**: check that you scanned the same top folder on both computers. Paths are compared relative to the scanned folder.
- **A tab label ends with `*`**: the tab shows only the first 20,000 rows. Use **Export all to CSV...** for the full list.
- **Double-click opens only a folder**: the file is not on this computer, so the nearest existing folder is opened.

## How it works
The scan walks the folder with `os.scandir` in a background thread and writes rows to SQLite in batches of 10,000. It reads `st_file_attributes` to spot online-only files without opening them. The compare reads both databases sorted by (name, size) and merges them in one pass, like a merge join, so memory use stays low even for millions of files. Results reach the window through a `queue.Queue` polled by `root.after`.
