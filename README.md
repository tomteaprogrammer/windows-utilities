# Windows Utilities

A collection of small Python tools for Windows that rename, copy, sort, check and clean up files and folders, plus a few desktop helpers.

Each tool is a single Python file. Most open a simple window. Each one has its own short manual in the `docs` folder.

## The tools

| Folder | Tool | What it does | Manual |
| --- | --- | --- | --- |
| `renaming/` | `onedrive_name_fixer.py` | Finds file and folder names that Windows or OneDrive will not accept, shows a preview, renames them, and can undo. | [docs/onedrive_name_fixer.md](docs/onedrive_name_fixer.md) |
| `renaming/` | `batch_renamer.py` | Renames every file in a folder to `Name_001`, `Name_002` ... in date order, with a preview. | [docs/batch_renamer.md](docs/batch_renamer.md) |
| `folders/` | `drive_inventory.py` | Saves a list of every file in a folder, then compares two lists to show missing, moved and new files. Read-only. | [docs/drive_inventory.md](docs/drive_inventory.md) |
| `folders/` | `folder_merger.py` | Moves the contents of many subfolders into one folder, with undo. | [docs/folder_merger.md](docs/folder_merger.md) |
| `folders/` | `folder_structure_analyzer.py` | Makes a CSV and a tree-view text report of a folder's structure. | [docs/folder_structure_analyzer.md](docs/folder_structure_analyzer.md) |
| `folders/` | `folder_structure_creator.py` | Creates a whole folder tree from an indented text file. | [docs/folder_structure_creator.md](docs/folder_structure_creator.md) |
| `folders/` | `folder_content_lister.py` | Writes a text list of the folders and files directly inside a folder. | [docs/folder_content_lister.md](docs/folder_content_lister.md) |
| `files/` | `file_type_fixer.py` | Copies files with wrong or missing extensions and gives each copy the correct extension. | [docs/file_type_fixer.md](docs/file_type_fixer.md) |
| `files/` | `nested_zip_unzipper.py` | Extracts every zip in a folder tree and sets aside zips that contain more zips. | [docs/nested_zip_unzipper.md](docs/nested_zip_unzipper.md) |
| `files/` | `unblock_documents.py` | Finds documents that Windows marked as "came from another computer" and unblocks them after a dry run. | [docs/unblock_documents.md](docs/unblock_documents.md) |
| `copying/` | `robocopy_gui.py` | A window for the Windows `robocopy` command, with live output and a log. | [docs/robocopy_gui.md](docs/robocopy_gui.md) |
| `google-drive/` | `google_drive_file_transfer.py` | Finds Google Docs/Sheets/Slides link files (`.gdoc`, `.gsheet` ...) and copies or moves them to one folder. | [docs/google_drive_file_transfer.md](docs/google_drive_file_transfer.md) |
| `system/` | `long_paths_toggle.py` | Shows, turns on or turns off the Windows "long paths" setting. | [docs/long_paths_toggle.md](docs/long_paths_toggle.md) |
| `automation/` | `auto_clicker.py` | Clicks the left mouse button 10 times a second until you stop it. | [docs/auto_clicker.md](docs/auto_clicker.md) |
| `automation/` | `auto_pager.py` | Presses Page Down at a set speed, for hands-free reading. | [docs/auto_pager.md](docs/auto_pager.md) |
| `automation/` | `clipboard_collector.py` | Records text you copy into a table and saves it as CSV. | [docs/clipboard_collector.md](docs/clipboard_collector.md) |

## What you need

- Windows 10 or Windows 11.
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/). Tick "Add python.exe to PATH" during setup.
- Most tools need nothing else. A few need one extra package (see `requirements.txt`).

## Install

1. Download this repository (green **Code** button, then **Download ZIP**) and unzip it.
2. Open a Command Prompt in the unzipped folder.
3. Run `pip install -r requirements.txt`. This is only needed for the auto clicker, auto pager, clipboard collector, and the command-line mode of the OneDrive name fixer.

## How to use

1. Open the manual for the tool you want from the table above.
2. Start the tool with `python <folder>\<tool>.py`, for example `python renaming\batch_renamer.py`. You can also double-click the `.py` file.

## Safety notes

- Tools that rename, move or change settings show what they will do and ask before they do it.
- Existing files are not overwritten. When a name is taken, the tool adds a number to the new name.
- Each manual has its own "Safety notes" section that explains what that tool changes and how to undo it.

## How it works

All tools are plain Python 3 scripts. The windows use tkinter, the GUI library that ships with Python. Long tasks run in a background thread, and the window is only updated from the main thread (through `root.after` or a queue), so the windows stay responsive. File work uses the standard library (`os`, `shutil`, `zipfile`, `csv`, `sqlite3`), and Windows features are reached through `subprocess` (robocopy, Explorer) and `winreg`.

## License

MIT. See [LICENSE](LICENSE).
