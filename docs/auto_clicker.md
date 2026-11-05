# Auto Clicker
Clicks the left mouse button 10 times a second at the pointer's position, until you stop it.

## What it does
- **Esc** starts clicking. **Esc** again stops it.
- **Ctrl+C** closes the program. It works in any window.
- Clicks wherever the mouse pointer is, every 0.1 seconds.
- Runs in a console window. There is no other window.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer.
- The `pynput` package.

## Install
1. Download the repository and unzip it.
2. Run `pip install -r requirements.txt`.

## How to use
1. Run `python automation\auto_clicker.py`. The console shows "Auto-Clicker Ready!".
2. Move the mouse to the place you want clicked.
3. Press **Esc** to start. Press **Esc** again to stop.
4. Press **Ctrl+C** to close the program.

## Safety notes
- While it runs, the tool clicks whatever is under the pointer. Do not leave it running over buttons such as **Delete** or **Buy**.
- The tool listens to keyboard presses to find Esc and Ctrl+C. It does not save or send anything.
- Pressing Ctrl+C in another program also copies text there as usual.

## Troubleshooting
- **"The package 'pynput' is not installed"**: run `pip install -r requirements.txt`.
- **Clicks do not reach a program**: programs running as administrator ignore clicks from a normal program. Run the console as administrator too.
- **Esc does nothing**: some games and remote desktop windows capture the keyboard. Click on the desktop first.

## How it works
`pynput.keyboard.Listener` watches the keyboard. A background thread calls `pynput.mouse.Controller.click` and sleeps 0.1 seconds between clicks. Ctrl+C is detected by tracking whether Ctrl is held and checking for the C key's virtual-key code.
