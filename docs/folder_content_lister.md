# Folder Content Lister
Makes a text file that lists the folders and files directly inside a folder.

## What it does
- Lists the top level of a folder only (no subfolders).
- Puts folders first, then loose files, each in alphabetical order.
- Prints the list in the console window.
- Saves it as `_folder_contents.txt` in the chosen folder.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python folders\folder_content_lister.py`.
2. Click **Pick Folder** and choose a folder.
3. Open `_folder_contents.txt` in that folder.

## Safety notes
- Adds one text file to the folder you choose. Nothing else is changed.
- An existing list is never replaced. A second run saves `_folder_contents (1).txt`, then `(2)`, and so on.

## Troubleshooting
- **"Could not process folder"**: you do not have permission to write in that folder. Pick a folder you own.
- **The list includes `_folder_contents.txt`**: a list from an earlier run is a file in the folder too. Delete old lists if you do not need them.

## How it works
`os.scandir` reads the folder once, entries are split into folders and files, sorted, and written as UTF-8 text. The file is opened in exclusive-create mode (`"x"`) after a free name is found, so an existing file can never be overwritten.
