import os
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

class FileRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Batch File Renamer (Smart Sort)")
        self.root.geometry("900x600")

        # Data storage
        self.file_map = [] # Stores tuples of (original_path, new_path)
        self.target_folder = ""

        # --- UI LAYOUT ---

        # 1. Top Section: Inputs
        frame_top = tk.Frame(root, pady=15)
        frame_top.pack(fill="x", padx=15)

        # Folder Selection
        tk.Label(frame_top, text="Select Folder:").grid(row=0, column=0, sticky="w")
        self.entry_path = tk.Entry(frame_top, width=60)
        self.entry_path.grid(row=0, column=1, padx=10)
        btn_browse = tk.Button(frame_top, text="Browse...", command=self.browse_folder)
        btn_browse.grid(row=0, column=2)

        # Base Name Input
        tk.Label(frame_top, text="New Base Name:").grid(row=1, column=0, sticky="w", pady=10)
        self.entry_name = tk.Entry(frame_top, width=60)
        self.entry_name.grid(row=1, column=1, padx=10, pady=10)
        self.entry_name.insert(0, "MyFile") # Default text

        # Preview Button
        btn_preview = tk.Button(frame_top, text="Generate Preview", command=self.generate_preview, bg="#e1e1e1", padx=10)
        btn_preview.grid(row=1, column=2, padx=10)

        # 2. Middle Section: Preview Table (Treeview)
        frame_list = tk.Frame(root)
        frame_list.pack(fill="both", expand=True, padx=15, pady=5)

        columns = ("old_name", "date", "new_name")
        self.tree = ttk.Treeview(frame_list, columns=columns, show="headings")
        
        self.tree.heading("old_name", text="Original Filename")
        self.tree.heading("date", text="Date Modified")
        self.tree.heading("new_name", text="New Filename (Preview)")

        self.tree.column("old_name", width=300)
        self.tree.column("date", width=180)
        self.tree.column("new_name", width=300)

        # Scrollbar for the table
        scrollbar = ttk.Scrollbar(frame_list, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        # 3. Bottom Section: Execute Button
        frame_bottom = tk.Frame(root, pady=15)
        frame_bottom.pack(fill="x", padx=15)

        self.status_label = tk.Label(frame_bottom, text="Ready. Please select a folder.", fg="grey")
        self.status_label.pack(side=tk.LEFT)

        self.btn_rename = tk.Button(frame_bottom, text="Confirm & Rename Files", command=self.start_rename, state=tk.DISABLED, bg="lightblue", font=("Arial", 10, "bold"), padx=10)
        self.btn_rename.pack(side=tk.RIGHT)

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder_selected)
            self.target_folder = folder_selected
            self.status_label.config(text="Folder selected. Enter a base name and click 'Generate Preview'.", fg="black")

    def generate_preview(self):
        folder = self.entry_path.get()
        base_name = self.entry_name.get()

        # Input Validation
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Error", "Please select a valid folder.")
            return
        if not base_name:
            messagebox.showerror("Error", "Please enter a base name.")
            return

        # Clear existing table data
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.file_map = []

        # Gather Files
        try:
            files = []
            for f in os.listdir(folder):
                full_path = os.path.join(folder, f)
                # Filter: Must be a file, ignoring hidden files like .DS_Store
                if os.path.isfile(full_path) and not f.startswith('.'):
                    mtime = os.path.getmtime(full_path)
                    # We store: (Full Path, Filename, Time)
                    files.append((full_path, f, mtime))
            
            if not files:
                messagebox.showwarning("Warning", "No valid files found in this folder.")
                return

            # --- SORTING LOGIC ---
            # 1. Sort by Time (x[2]) Oldest -> Newest
            # 2. Tie-Breaker: If times are equal, Sort by Filename (x[1]) Alphabetically
            files.sort(key=lambda x: (x[2], x[1]))

            # Create Preview Data
            for index, (full_path, original_filename, mtime) in enumerate(files):
                _, ext = os.path.splitext(original_filename)
                
                # Create new name: BaseName_001.ext
                new_filename = f"{base_name}_{index + 1:03d}{ext}"
                new_full_path = os.path.join(folder, new_filename)
                
                # Format date string for the GUI table
                date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

                # Insert into GUI table
                self.tree.insert("", tk.END, values=(original_filename, date_str, new_filename))
                
                # Add to execution list
                self.file_map.append((full_path, new_full_path))

            self.status_label.config(text=f"Preview generated for {len(files)} files. Review list above.", fg="blue")
            self.btn_rename.config(state=tk.NORMAL) # Enable the rename button

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred scanning files:\n{e}")

    def start_rename(self):
        if not self.file_map:
            return
        
        # Confirmation Dialog
        confirm = messagebox.askyesno("Confirm Rename", f"Are you sure you want to rename {len(self.file_map)} files?\n\nThis cannot be undone easily.")
        if not confirm:
            return

        count, errors = self.rename_two_phase(self.file_map)
        # Reset UI after completion
        self.file_map = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.btn_rename.config(state=tk.DISABLED)
        
        # Success Message
        msg = f"Successfully renamed {count} files."
        if errors:
            shown = "\n".join(errors[:15])
            more = f"\n...and {len(errors) - 15} more." if len(errors) > 15 else ""
            msg += f"\n\n{len(errors)} problems:\n{shown}{more}"
            messagebox.showwarning("Completed with Errors", msg)
            self.status_label.config(text=f"Renamed {count} files. {len(errors)} problems (see message).", fg="red")
        else:
            messagebox.showinfo("Success", msg)
            self.status_label.config(text="Renaming complete.", fg="green")

    @staticmethod
    def rename_two_phase(file_map):
        """Renames files in two steps so new names never collide with old names.

        Step 1 gives every file a unique temporary name. Step 2 gives each file its
        final name. This makes it safe to run again on files that are already numbered
        (for example MyFile_002 -> MyFile_001). Existing files are never overwritten.
        Returns (renamed_count, list_of_error_messages).
        """
        errors = []
        pending = [(old, new) for old, new in file_map if old != new]
        if not pending:
            return 0, errors

        # Stop before changing anything if a final name is taken by something that is not in the list
        # (for example a folder or a hidden file with that name).
        sources = {os.path.normcase(old) for old, _ in file_map}
        for _, new in pending:
            if os.path.exists(new) and os.path.normcase(new) not in sources:
                errors.append(f"'{os.path.basename(new)}' already exists and is not in the list. Nothing was renamed.")
        if errors:
            return 0, errors

        # Step 1: original name -> temporary name
        tag = uuid.uuid4().hex[:8]
        staged = []
        for index, (old, new) in enumerate(pending):
            temp = os.path.join(os.path.dirname(old), f"~renaming_{tag}_{index}.tmp")
            try:
                os.rename(old, temp)
                staged.append((old, temp, new))
            except OSError as e:
                errors.append(f"{os.path.basename(old)}: {e}")

        # Step 2: temporary name -> final name
        count = 0
        for old, temp, new in staged:
            try:
                if os.path.exists(new):
                    raise FileExistsError(f"'{os.path.basename(new)}' already exists")
                os.rename(temp, new)
                count += 1
            except OSError as e:
                try:
                    os.rename(temp, old)  # put the original name back
                    errors.append(f"{os.path.basename(old)}: {e}. Kept its original name.")
                except OSError:
                    errors.append(f"{os.path.basename(old)}: {e}. It is now named '{os.path.basename(temp)}'.")
        return count, errors

if __name__ == "__main__":
    root = tk.Tk()
    app = FileRenamerApp(root)
    root.mainloop()