# Google Drive File Transfer
Finds Google Docs, Sheets, Slides and other Google link files (`.gdoc`, `.gsheet` ...) in a folder and copies or moves them all into one folder.

## What it does
- Scans a folder and all subfolders for `.gdoc`, `.gsheet`, `.gslides`, `.gdraw`, `.gform`, `.gmap`, `.gshortcut` and `.gdlink` files.
- Lists them with name, extension, size and full path.
- Double-click a row to open that file (it opens in your browser through Google Drive for desktop).
- Copies (the default) or moves all listed files into one destination folder.
- Adds a number when a name is already taken, for example `Budget (1).gsheet`.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.
- Google Drive for desktop, if you want to open the files.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python google-drive\google_drive_file_transfer.py`.
2. Click **1. Select Folder to Scan** and choose a folder. The list fills when the scan is done.
3. Keep **Copy** selected (recommended), or choose **Move (Cut)**.
4. Click **2. Transfer Google Files** and choose the destination folder.

## Safety notes
- **Copy is the default and the safe choice.**
- A `.gdoc` or `.gsheet` file is only a small link to a document stored in Google Drive. If the file is inside a synced Google Drive folder, **moving it out can remove the document from Google Drive**, because Drive sees it as deleted. The tool shows this warning and asks before any move.
- All files go into one destination folder (subfolders are not kept). Existing files are never overwritten.
- A copied link file still points to the same online document. It is not a separate backup of the document's contents.

## Troubleshooting
- **No files found**: the folder has no Google link files, or Google Drive for desktop is set to show them only online.
- **Double-click does nothing**: Google Drive for desktop must be installed and signed in to open these files.
- **Errors during transfer**: the message lists the first errors. The full list is printed in the console window.

## How it works
The scan runs `os.walk` in a background thread and collects plain data, and the Treeview is filled on the main thread with `root.after`. Transfers use `shutil.copy2` or `shutil.move`, with a loop that finds a free `name (n).ext` before each file.
