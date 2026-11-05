import os
import tkinter as tk
from tkinter import filedialog, messagebox

def process_folder():
    # 1. Open the folder picker GUI
    folder_path = filedialog.askdirectory(title="Select a Folder")
    
    if not folder_path:
        return  # Exit if the user closes the dialog without picking a folder

    try:
        folders = []
        files = []

        # 2. Scan only the top level (no nested folders/recursion)
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if entry.is_dir():
                    folders.append(entry.name)
                elif entry.is_file():
                    files.append(entry.name)

        # Sort alphabetically for a clean list
        folders.sort()
        files.sort()

        # 3. Format the text output
        output_lines = [f"Contents of: {folder_path}\n"]
        
        output_lines.append("--- FOLDERS ---")
        if folders:
            for f in folders:
                output_lines.append(f"[DIR]  {f}")
        else:
            output_lines.append("(No folders found)")

        output_lines.append("\n--- LOOSE FILES ---")
        if files:
            for f in files:
                output_lines.append(f"[FILE] {f}")
        else:
            output_lines.append("(No loose files found)")

        final_text = "\n".join(output_lines)

        # 4. Print to console
        print(final_text)

        # 5. Save to a .txt file in the chosen folder
        #    An existing list is never replaced: a number is added instead,
        #    for example "_folder_contents (1).txt".
        txt_filename = os.path.join(folder_path, "_folder_contents.txt")
        counter = 1
        while os.path.exists(txt_filename):
            txt_filename = os.path.join(folder_path, f"_folder_contents ({counter}).txt")
            counter += 1
        with open(txt_filename, "x", encoding="utf-8") as f:
            f.write(final_text)

        messagebox.showinfo(
            "Success", 
            f"List printed to console and saved as:\n{os.path.basename(txt_filename)}\n\nin the selected folder."
        )

    except Exception as e:
        messagebox.showerror("Error", f"Could not process folder:\n{e}")

# --- Set up the GUI Window ---
root = tk.Tk()
root.title("Folder Content Lister")
root.geometry("300x120")
root.eval('tk::PlaceWindow . center') # Center the window

instruction = tk.Label(root, text="Select a folder to generate a text list\nof its immediate folders and files.", pady=10)
instruction.pack()

btn = tk.Button(root, text="Pick Folder", command=process_folder, padx=20, pady=5)
btn.pack()

# Start the application
root.mainloop()