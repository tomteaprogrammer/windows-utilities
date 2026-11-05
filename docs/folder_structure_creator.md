# Folder Structure Creator
Creates a whole tree of folders in one step from a simple text file, where indentation shows which folder goes inside which.

## What it does
- Reads a `.txt` file with one folder name per line.
- Uses **Tab** indentation to place a folder inside the folder above it.
- Checks every line before creating anything, and lists any problems.
- Creates the folders in the destination you choose.
- Leaves folders that already exist as they are.

## What you need
- Windows 10 or 11.
- Python 3.10 or newer. No extra packages.

## Install
1. Download the repository and unzip it.

## How to use
1. Write a text file in Notepad. Press the **Tab** key once for each level (spaces do not count as indentation):
   ```
   Clients
   	Smith & Co
   		Invoices
   		Letters
   	Jones
   Templates
   ```
2. Run `python folders\folder_structure_creator.py`.
3. Click **Browse...** next to **Text File:** and choose your file.
4. Click **Browse...** next to **Destination:** and choose where the tree should go.
5. Click **Create Folders**.

## Safety notes
- The tool only creates folders. It never deletes, moves or renames anything.
- If any line has a problem, nothing is created. The message lists each problem line, such as:
  - characters Windows does not allow: `< > : " / \ | ? *`
  - a name that ends with a period
  - a reserved name such as `CON`, `PRN`, `AUX`, `NUL`, `COM1` or `LPT1`
  - a line indented with spaces instead of tabs
- `&` is allowed and kept as it is.

## Troubleshooting
- **Everything ends up at the top level**: the file uses spaces. Replace them with Tab characters.
- **A folder lands under the wrong parent**: check that each line has exactly one more Tab than its parent.
- **Strange characters in folder names**: save the text file as UTF-8 (the default in Notepad).

## How it works
The file is read with the `utf-8-sig` encoding, which also removes the hidden byte-order mark Notepad can add. Each line's depth is its count of leading tabs. A stack holds the current parent path for each depth, and `os.makedirs(..., exist_ok=True)` creates each folder. A validation pass runs over all lines first.
