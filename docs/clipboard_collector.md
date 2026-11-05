# Clipboard Collector
Records each piece of text you copy into a table, in one or two columns, and saves the table as a CSV file for Excel.

> **Warning:** while monitoring is on, the tool records **everything** you copy, including passwords, card numbers and private messages. Stop monitoring before you copy anything private.

## What it does
- Checks the clipboard twice a second while monitoring is on.
- Adds each new piece of copied text to the table.
- **Two-column mode** (default): the first copy goes in Column A, the next in Column B, then a new row. Good for collecting pairs such as name and email.
- **Use Single Column**: every copy goes in its own row.
- **Save to CSV** saves the table.
- Ignores what was already on the clipboard when you start.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer.
- The `pyperclip` package.

## Install
1. Download the repository and unzip it.
2. Run `pip install -r requirements.txt`.

## How to use
1. Run `python automation\clipboard_collector.py`.
2. Optional: tick **Use Single Column**.
3. Click **Start Monitoring**.
4. Copy text in any program (Ctrl+C). Each copy appears in the table.
5. Click **Stop Monitoring** when you are done.
6. Click **Save to CSV** and choose a file name.
7. Click **Clear Data** to start a new list.

## Safety notes
- The data is kept only in the window until you save it. Nothing is sent anywhere.
- Saved CSV files contain everything that was copied while monitoring was on. Check the table before you save or share it.
- Changing between one and two columns clears the table (the tool asks first).

## Troubleshooting
- **"The package 'pyperclip' is not installed"**: run `pip install -r requirements.txt`.
- **The same text copied twice appears once**: the tool only adds text that differs from the last copy.
- **Accented letters look wrong in Excel**: use **Data > From Text/CSV** in Excel and choose UTF-8.

## How it works
A background thread polls `pyperclip.paste()` every 0.5 seconds and hands new text to the main thread with `root.after`, where it is added to the table. The CSV is written with Python's built-in `csv` module.
