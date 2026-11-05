# File Type Fixer
Looks inside files that have a wrong or missing extension, works out the real file type, and saves a copy with the correct extension.

## What it does
- Reads the first bytes of each file and compares them with known file signatures: JPG, PNG, GIF, BMP, TIFF, MP3, MP4, WAV, OGG, FLAC, PDF and ZIP.
- Tells Word, Excel and PowerPoint files (`.docx`, `.xlsx`, `.pptx`) apart from plain ZIP files.
- Can use the optional `python-magic` library for more types.
- Copies each file into the destination with the corrected extension, keeping the same subfolders.
- Copies files it cannot identify into an `error_files` folder, with the extension `.unknown`.
- Writes a log file in the destination folder.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer.
- Optional: `pip install python-magic-bin` for better detection. The window shows whether it is installed.

## Install
1. Download the repository and unzip it.
2. Optional: `pip install python-magic-bin`.

## How to use
1. Run `python files\file_type_fixer.py`.
2. Click **Browse...** under **Source Folder (with broken files):**.
3. Click **Browse...** under **Destination Folder (for fixed files):**. Use an empty folder.
4. Click **Process Files**. The progress bar and status line show how far it is.
5. Read the summary, then open the destination folder.

## Safety notes
- The source files are only read. They are never changed, moved or deleted.
- Copies keep the same subfolders as the source, so files with the same name in different folders stay apart.
- An existing file in the destination is never overwritten. The copy gets a number, for example `photo (1).jpg`.
- The log `file_fixer_log_<date>_<time>.txt` is saved in the destination folder.

## Troubleshooting
- **Many files end up in `error_files`**: their type is not in the signature list. Install `python-magic-bin` and run again.
- **A `.zip` was expected to be `.docx`**: the file is a ZIP without the Office parts inside (`[Content_Types].xml` plus a `word/`, `xl/` or `ppt/` folder).
- **The destination is inside the source**: that is allowed. The destination folder is skipped during the scan.

## How it works
Each file's first 8 bytes are matched against a table of magic numbers. For ZIP files, `zipfile` reads the archive's list of names to find the Office Open XML parts. Without a match, `python-magic` (if installed) or `mimetypes` is tried. The work runs in a background thread, and every window update goes through `root.after`.
