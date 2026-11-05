# Auto Pager
Presses the Page Down key for you at a steady speed, for hands-free reading of long documents and web pages.

## What it does
- Presses Page Down again and again in the window you are reading.
- A slider sets the time between presses, from 0.1 to 2 seconds (default 0.7).
- **Start Paging**, then **Pause** and **Resume** with the same button.
- **Ctrl+Alt+Down** starts, pauses and resumes from any window.
- **Esc** closes the tool from any window.
- The small window stays on top of other windows.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer.
- The `keyboard` package.

## Install
1. Download the repository and unzip it.
2. Run `pip install -r requirements.txt`.

## How to use
1. Run `python automation\auto_pager.py`.
2. Set the speed with the **Interval** slider.
3. Click in the document or web page you want to read.
4. Press **Ctrl+Alt+Down** (or click **Start Paging**, then click back into the document).
5. Press **Ctrl+Alt+Down** again to pause or resume.
6. Press **Esc** or close the window to quit.

## Safety notes
- Page Down goes to whichever window is active. Pause before you switch to another program.
- The `keyboard` package watches all key presses to find the two hotkeys. Nothing is saved or sent.
- Esc and Ctrl+Alt+Down still reach other programs as normal.

## Troubleshooting
- **"The package 'keyboard' is not installed"**: run `pip install -r requirements.txt`.
- **Nothing scrolls**: the document window must be active. Click inside it after you start.
- **Hotkeys do not work in one program**: programs running as administrator do not receive keys from a normal program. Run the tool as administrator too.

## How it works
The `keyboard` package sends the Page Down key and registers the global hotkeys. A background thread does the key presses and reads the interval from a plain number that the slider updates on the main thread. Hotkey presses are put on a `queue.Queue` that the tkinter main loop reads every 100 ms, so the window is only changed on the main thread.
