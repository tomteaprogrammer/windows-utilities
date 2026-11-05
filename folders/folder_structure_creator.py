import os
import tkinter as tk
from tkinter import filedialog, messagebox

ILLEGAL_CHARACTERS = '<>:"/\\|?*'
RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
}

def find_problems(lines):
    """Checks every line before anything is created. Returns a list of problem messages."""
    problems = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        name = line.strip()
        if line.startswith(' '):
            problems.append(f"Line {number}: '{name}' is indented with spaces. Use the Tab key for indentation.")
        bad = sorted({ch for ch in name if ch in ILLEGAL_CHARACTERS or ord(ch) < 32})
        if bad:
            shown = ' '.join(repr(ch) for ch in bad)
            problems.append(f"Line {number}: '{name}' contains characters Windows does not allow: {shown}")
        if name.endswith('.'):
            problems.append(f"Line {number}: '{name}' ends with a period. Windows does not allow this.")
        if name.split('.')[0].strip().upper() in RESERVED_NAMES:
            problems.append(f"Line {number}: '{name}' is a reserved Windows name.")
    return problems

def create_folders_from_txt(file_path, dest_dir):
    try:
        # utf-8-sig also removes the hidden BOM mark that Notepad can add at the start of the file
        with open(file_path, 'r', encoding='utf-8-sig') as file:
            lines = file.readlines()

        # Check every line first, so nothing is created when the file has a problem
        problems = find_problems(lines)
        if problems:
            shown = "\n".join(problems[:20])
            more = f"\n...and {len(problems) - 20} more." if len(problems) > 20 else ""
            return False, f"No folders were created. Please fix these lines first:\n\n{shown}{more}"

        # This list keeps track of the parent directories for each indentation level
        path_stack = [dest_dir] 

        for line in lines:
            # Skip empty lines or lines containing only spaces/tabs
            if not line.strip():
                continue 

            # Count the number of leading tabs to determine folder depth
            depth = len(line) - len(line.lstrip('\t'))
            
            # Remove leading/trailing whitespace ('&' is allowed by Windows and is kept)
            folder_name = line.strip()

            # Adjust the stack to match the current folder depth
            path_stack = path_stack[:depth + 1]

            # Join the current parent path with the new folder name
            current_parent = path_stack[-1]
            new_folder_path = os.path.join(current_parent, folder_name)

            # Create the folder (exist_ok=True prevents errors if the folder already exists)
            os.makedirs(new_folder_path, exist_ok=True)

            # Add this new folder to the stack to act as a parent for the next line
            path_stack.append(new_folder_path)

        return True, "Folders created successfully."
    except Exception as e:
        return False, str(e)

def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
    if file_path:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, file_path)

def select_dest():
    dest_dir = filedialog.askdirectory()
    if dest_dir:
        dest_entry.delete(0, tk.END)
        dest_entry.insert(0, dest_dir)

def run_creation():
    file_path = file_entry.get()
    dest_dir = dest_entry.get()

    if not file_path or not dest_dir:
        messagebox.showwarning("Missing Information", "Please select both a text file and a destination folder.")
        return

    success, message = create_folders_from_txt(file_path, dest_dir)
    if success:
        messagebox.showinfo("Success", message)
    else:
        messagebox.showerror("Error", f"Failed to create folders:\n{message}")

# --- GUI Setup ---
root = tk.Tk()
root.title("Folder Structure Creator")
root.geometry("450x200")

# Text File Selection
tk.Label(root, text="Text File:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
file_entry = tk.Entry(root, width=40)
file_entry.grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="Browse...", command=select_file).grid(row=0, column=2, padx=10, pady=10)

# Destination Selection
tk.Label(root, text="Destination:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
dest_entry = tk.Entry(root, width=40)
dest_entry.grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="Browse...", command=select_dest).grid(row=1, column=2, padx=10, pady=10)

# Run Button
tk.Button(root, text="Create Folders", command=run_creation, bg="#e0e0e0").grid(row=2, column=1, pady=20)

root.mainloop()