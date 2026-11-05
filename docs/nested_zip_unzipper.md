# Nested Zip Unzipper
Goes through a folder and all its subfolders, extracts every zip file, and sets aside the zips that contain more zips so you can check them by hand.

## What it does
- Finds every `.zip` file in the chosen folder and its subfolders.
- A zip **without** zips inside: extracted into a new folder with the zip's name, next to the zip. The zip is then moved to a `delete` folder.
- A zip **with** zips inside: moved to a `review` folder and listed in a window at the end, with an **Open in Explorer** button for each one.
- Writes problems (damaged zips, locked files, blocked folders) to `error_log.txt`.
- **Undo Previous Run in a Folder** puts the zips back and removes what was extracted.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python files\nested_zip_unzipper.py`.
2. Click **Process Zips in a Folder** and choose the top folder.
3. Read the summary and click **Yes** to start. The console window shows each folder as it is checked.
4. If some zips contain zips, a window lists them. Click **Open in Explorer** to look at one, then **Close**.
5. When you are happy with the result, delete the `delete` folder yourself.
6. To reverse a run, start the tool again, click **Undo Previous Run in a Folder**, and choose the same top folder.

## Safety notes
- Nothing is deleted by the process step. Zips are only moved into `delete` or `review` inside the chosen folder.
- Zips are extracted into a **new** folder (`name`, or `name_1` if that is taken), so existing files are never replaced.
- Every action is written to `undo_log.jsonl` in the chosen folder as it happens, so a run that stops part way can still be undone.
- Undo removes only the files the tool extracted, and only empty folders the tool made. It moves each zip back unless a file with that name is there again.
- Shortcuts and symbolic links to other folders are not followed.

## Troubleshooting
- **"BLOCKED BY WINDOWS: Cannot read folder"**: you do not have permission for that folder. It is listed in `error_log.txt`.
- **BadZipFile in the error log**: the zip is damaged or not really a zip. It is left where it was.
- **"No undo log found"**: choose the same top folder you processed. The undo file is `undo_log.jsonl` in that folder.

## How it works
`os.walk` crawls the tree (skipping the `delete` and `review` folders it creates). `zipfile` reads each archive's name list to spot nested zips, and extracts members one by one with `ZipFile.extract`, which also blocks paths that try to escape the target folder. Every action is appended to a JSON Lines undo log and flushed straight away. Windows paths use the `\\?\` (or `\\?\UNC\`) long-path prefix.
