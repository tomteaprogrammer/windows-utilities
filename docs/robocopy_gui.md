# Robocopy GUI
A simple window for the fast Windows `robocopy` copy command: pick two folders, choose a few options, and watch the copy live.

## What it does
- Copies a folder to another place with `robocopy`, using many threads for speed.
- Shows the exact command before it runs (**Command preview**).
- Shows robocopy's output live while it copies, and saves a log file.
- Lets you cancel a running copy.
- Stops you from copying a folder into itself.
- Explains the result using robocopy's exit code.

## What you need
- Windows 10 or 11 (robocopy is built into Windows).
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python copying\robocopy_gui.py`.
2. Click **Browse** next to **Source** and **Destination**.
3. Choose **Copy source contents into destination** or **Create source folder inside destination**.
4. Change any options, and check the **Command preview**.
5. Click **Start robocopy**. Watch **Live robocopy output**. Click **Cancel** to stop.

## Settings and options
- **Include empty folders (/E)**: on by default. Off uses `/S`.
- **Show file names in log**: off adds `/NFL /NDL`.
- **Save log in the logs folder**: on by default. Adds `/LOG+:` and `/TEE` (so the output still shows in the window).
- **Threads (/MT)** 1–128 (default 32), **Retries (/R)** (default 1), **Wait seconds (/W)** (default 1).
- **Restartable mode /Z**, **Unbuffered /J**, **Copy permissions /COPY:DATS**.
- **MIRROR destination /MIR (deletes extras)**: makes the destination an exact copy of the source.

## Safety notes
- Normal copies add and update files in the destination. Files in the destination with the same name are replaced by robocopy when the source copy is different.
- **/MIR deletes** files and folders in the destination that are not in the source. The window shows a red warning, and asks twice: when you tick the box and when you start.
- Both folder boxes must be filled in. An empty box is never treated as "the current folder".
- Log files are saved in a `logs` folder next to the script, named `robocopy_<date>_<time>.log`.

## Troubleshooting
- **Exit code 1, 2 or 3**: success. 1 = files copied, 2 = extra files in the destination, 3 = both. Codes 0–7 are not errors.
- **Exit code 8 or higher**: some files failed. Look for "ERROR" in the output or log. Often the file is in use or access is denied.
- **Strange characters in the output**: the output is read in the console (OEM) code page. If names still look wrong, check the log file.

## How it works
The window builds a robocopy argument list from the options and runs it with `subprocess.Popen` in a background thread. Output lines are decoded with Python's `oem` codec (the console code page robocopy writes in) and passed to the window through a `queue.Queue` that `root.after` polls. Cancel sends `CTRL_BREAK_EVENT` to robocopy's process group, then kills it after two seconds if needed.
