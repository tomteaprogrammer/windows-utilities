# Long Paths Toggle
Shows whether the Windows "Enable Win32 long paths" setting is on, and turns it on or off from a small console menu.

## What it does
- Shows the current status (enabled or disabled) without asking for administrator rights.
- **1) Enable long paths** sets `LongPathsEnabled` to 1.
- **2) Disable long paths** sets it to 0.
- Asks for administrator rights only when you choose to change the setting.

## What you need
- Windows 10 (version 1607 or newer) or Windows 11.
- Python 3.10 or newer. No extra packages.
- An administrator account to change the setting.

## Install
1. Download the repository and unzip it.

## How to use
1. Run `python system\long_paths_toggle.py`.
2. Read **Current status** at the top of the menu.
3. Type `1` to enable or `2` to disable, and press Enter.
4. If you are not running as administrator, type `y` to restart the tool as administrator and confirm the Windows prompt. Then choose the option again in the new window.
5. Type `4` to exit.

## Safety notes
- This changes a Windows setting in the registry: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled`.
- To undo, run the tool again and choose the other option.
- **The change does not affect programs that are already open.** Close and restart them, or sign out and back in. Some programs need a full restart of Windows.
- Turning it on only lets programs that support long paths use them. Older programs keep the 260-character limit.

## Troubleshooting
- **"Access denied"**: the tool is not running as administrator. Choose the option again and type `y` when asked.
- **Status still shows the old value in another window**: choose **3) Show status** to read it again.
- **A program still fails on long paths**: that program does not support them, even with the setting on.

## How it works
The status is read with `winreg.QueryValueEx` using read-only access, which needs no administrator rights. Writing uses `winreg.SetValueEx` with a `REG_DWORD`. `ctypes` calls `IsUserAnAdmin` to check rights and `ShellExecuteW` with the `runas` verb to restart the script elevated. `winreg` is imported only after the script has checked that it runs on Windows.
