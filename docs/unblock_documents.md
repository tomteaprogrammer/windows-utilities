# Unblock Documents
Finds documents and Microsoft Office files that Windows marked as "This file came from another computer and might be blocked", shows you the list, and removes the mark after a dry run — like ticking **Unblock** in a file's Properties, but for thousands of files at once.

## What it does
- **Scan**: finds every blocked file in a folder and its subfolders, and shows how many folders they are in.
- **Dry run**: checks each ticked file for problems (open in another program, read-only, no permission, already unblocked, gone) and changes nothing.
- **Unblock**: removes the mark from the files that passed the dry run. The button stays grey until a dry run is done.
- Shows where each file came from (the download address saved by Windows), its zone, size and date.
- Lets you preview files, open their folder, filter the list, and export a CSV report.
- Skips macro-enabled Office files unless you turn them on.

## Why not just use PowerShell?
Windows already has a command for this: `Get-ChildItem -Recurse | Unblock-File` in PowerShell. It unblocks every file at once, without showing you anything first. This tool adds:
- a list of what is blocked and where it came from, **before** anything changes,
- a choice of file types, with macro-enabled files left out by default,
- a dry run that finds locked and read-only files,
- per-file and per-folder tick boxes,
- handling of read-only files (the flag is put back afterwards),
- a CSV record of what was changed.

## What you need
- Windows 10 or 11, with files on an NTFS drive.
- Python 3.8 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Double-click **`Unblock Documents.bat`** in the `files` folder. You can also drag a folder onto it to start with that folder filled in. The menu offers:
   - `[1]` Open the window
   - `[2]` Console: scan + dry run only (changes nothing)
   - `[3]` Console: scan, dry run, then ask before unblocking
2. In the window, click **Browse...**, pick a folder, and click **Scan**.
3. Untick any files you do not want. Use **Select all** / **Select none**, the folder rows, or the Space key.
4. Click **Dry run (check selected)** and read the **Dry run** column and the **Log**.
5. Click **Unblock selected** and confirm.
6. Optional: click **Export CSV...** to save a record.

From a Command Prompt:
```
python files\unblock_documents.py                         open the window
python files\unblock_documents.py --path "D:\Downloads"
python files\unblock_documents.py --cli --path D:\Docs --dry-run
python files\unblock_documents.py --cli --path D:\Docs --yes
```

## Settings and options
**File types** (window drop-down or `--types`):

| Choice | Covers |
| --- | --- |
| Microsoft Office files only (`office`) | Word, Excel, PowerPoint, Access, Publisher, Visio, Project, OneNote |
| Office files + documents (`documents`, default) | the above plus PDF, RTF, TXT, CSV, XPS, OpenDocument, EPUB, MSG/EML ... |
| Every file (`all`) | no extension filter. The tool shows a warning when you pick it. |

**Include macro-enabled files (.docm, .xlsm, .pptm, ...)** (or `--include-macros`): **off by default**, in every file-type choice including "Every file". The tool asks you to confirm when you tick it.

**Show other zones too (intranet/trusted)** (or `--include-all-zones`): Explorer only offers Unblock for files from the **Internet** and **Restricted** zones, so only those are counted as blocked. This option also lists files tagged *Local intranet* or *Trusted site*.

**Other console options**: `--no-recurse` (ignore subfolders), `--list` (print every blocked file), `--csv FILE` (write a report), `--dry-run` (stop after the check), `--yes` (skip the "type YES" question). Exit code is 0 on success, 1 if some files could not be unblocked, 2 for a bad folder.

## Safety notes
- **Unblocking removes a safety marker.** Office will open those files without Protected View, and scripts and programs will run without the security warning. Only unblock files you trust.
- **Macro-enabled files are the biggest risk.** Office blocks macros in files from the internet because of this mark. Unblocking a `.docm` or `.xlsm` lets its macros run. That is why they are off by default.
- **"Every file" includes programs and scripts** (`.exe`, `.msi`, `.bat`, `.js` ...). Unblocking them removes the Windows SmartScreen warning.
- Dry run and Unblock act **only on ticked rows that are shown in the list**. Ticked rows hidden by the filter are left out, and the status line says how many.
- While a scan, dry run or unblock is running, the **Dry run** and **Unblock** buttons stay disabled.
- Online-only OneDrive or Google Drive files are **not opened** during the dry run (opening would download them). For those files the "open in another program" check is skipped, and the **Dry run** column says so.
- Paths longer than 260 characters are handled.
- There is no undo. The mark cannot be put back by this tool. Export a CSV first if you want a record.

## Troubleshooting
- **"File is open in another program"**: close the file and run the dry run again.
- **"No write permission"**: run the tool as the file's owner or as administrator.
- **Nothing is found on a USB stick**: FAT32 and exFAT drives cannot store the mark, so their files are never blocked.

## How it works
Windows stores the mark in a hidden NTFS alternate data stream named `Zone.Identifier` (`file.pdf:Zone.Identifier`). The tool reads that stream to get the zone and source address, and removes it with `os.remove`, the same thing Explorer's Unblock checkbox does. The scan, dry run and unblock run in a background thread and report back with `root.after`. Online-only cloud files are detected from `st_file_attributes` without opening them. For testing off Windows, `UNBLOCK_FAKE_ADS=1` makes the tool use `<file>.__Zone.Identifier__` side files instead of real streams.
