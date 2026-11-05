import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class GoogleDriveFileMoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Drive File Transfer")
        self.root.geometry("950x600")

        # The exact Google Drive extensions to target
        self.gdrive_extensions = ('.gdoc', '.gsheet', '.gslides', '.gdraw', '.gform', '.gmap', '.gshortcut', '.gdlink')

        # --- Top Control Panel ---
        top_frame = tk.Frame(root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn_scan = tk.Button(
            top_frame, 
            text="1. Select Folder to Scan", 
            command=self.scan_folder,
            font=("Arial", 10, "bold"),
            bg="#e0e0e0"
        )
        self.btn_scan.pack(side=tk.LEFT, padx=5)

        # Mode Selection Variables and Radio Buttons (Copy is the safe default)
        self.transfer_mode = tk.StringVar(value="copy")

        self.radio_move = tk.Radiobutton(
            top_frame, 
            text="Move (Cut)", 
            variable=self.transfer_mode, 
            value="move",
            font=("Arial", 10)
        )
        self.radio_move.pack(side=tk.LEFT, padx=(15, 5))

        self.radio_copy = tk.Radiobutton(
            top_frame, 
            text="Copy", 
            variable=self.transfer_mode, 
            value="copy",
            font=("Arial", 10)
        )
        self.radio_copy.pack(side=tk.LEFT, padx=5)

        self.btn_transfer = tk.Button(
            top_frame, 
            text="2. Transfer Google Files", 
            command=self.transfer_files,
            font=("Arial", 10, "bold"),
            bg="#d4edda" 
        )
        self.btn_transfer.pack(side=tk.LEFT, padx=15)

        self.lbl_status = tk.Label(top_frame, text="Waiting for folder selection...", fg="gray")
        self.lbl_status.pack(side=tk.LEFT, padx=15)

        # --- Treeview Setup ---
        mid_frame = tk.Frame(root)
        mid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tree_scroll = tk.Scrollbar(mid_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(mid_frame, yscrollcommand=tree_scroll.set, selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        # Define Columns
        self.tree['columns'] = ("Type", "Size", "FullPath")
        
        # Format Columns
        self.tree.column("#0", width=300, minwidth=150) 
        self.tree.column("Type", width=80, minwidth=60, anchor=tk.CENTER)
        self.tree.column("Size", width=100, minwidth=80, anchor=tk.E)
        self.tree.column("FullPath", width=400, minwidth=200)

        # Assign Headings
        self.tree.heading("#0", text="Google File Name", anchor=tk.W)
        self.tree.heading("Type", text="Extension", anchor=tk.CENTER)
        self.tree.heading("Size", text="Size", anchor=tk.CENTER)
        self.tree.heading("FullPath", text="Full Path", anchor=tk.W)

        # Bind double-click event to open the file directly
        self.tree.bind("<Double-1>", self.open_file)

    def format_size(self, size_in_bytes):
        if size_in_bytes < 1024:
            return f"{size_in_bytes} B"
        elif size_in_bytes < 1024**2:
            return f"{size_in_bytes/1024:.2f} KB"
        elif size_in_bytes < 1024**3:
            return f"{size_in_bytes/(1024**2):.2f} MB"
        else:
            return f"{size_in_bytes/(1024**3):.2f} GB"

    def scan_folder(self):
        source_folder = filedialog.askdirectory(title="Select Folder to Scan")
        if not source_folder:
            return

        self.tree.delete(*self.tree.get_children())
        self.lbl_status.config(text=f"Scanning: {source_folder}", fg="blue")
        self.btn_scan.config(state=tk.DISABLED)
        self.btn_transfer.config(state=tk.DISABLED)

        # Scan in a worker thread so the window does not freeze on large folders
        threading.Thread(target=self._scan_worker, args=(source_folder,), daemon=True).start()

    def _scan_worker(self, source_folder):
        """Runs in a worker thread. Only plain data is collected here; the Treeview is filled on the main thread."""
        found = []
        error = None
        try:
            for dirpath, _, filenames in os.walk(source_folder):
                for filename in filenames:
                    if filename.lower().endswith(self.gdrive_extensions):
                        full_path = os.path.join(dirpath, filename)
                        
                        try:
                            file_size = os.path.getsize(full_path)
                            formatted_size = self.format_size(file_size)
                        except OSError:
                            formatted_size = "Unknown"

                        _, ext = os.path.splitext(filename)
                        found.append((filename, ext.lower(), formatted_size, full_path))
        except Exception as e:
            error = str(e)
        self.root.after(0, self._scan_finished, found, error)

    def _scan_finished(self, found, error):
        for filename, ext, formatted_size, full_path in found:
            self.tree.insert("", "end", text=filename, values=(ext, formatted_size, full_path))
        self.btn_scan.config(state=tk.NORMAL)
        self.btn_transfer.config(state=tk.NORMAL)
        if error:
            self.lbl_status.config(text=f"Scan stopped. Found {len(found)} Google Drive files.", fg="red")
            messagebox.showerror("Error", f"An error occurred during scanning:\n{error}")
        else:
            self.lbl_status.config(text=f"Found {len(found)} Google Drive files.", fg="green")

    def open_file(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return

        item_values = self.tree.item(selected_item[0], 'values')
        if not item_values:
            return

        file_path = item_values[2] 

        if os.path.exists(file_path):
            try:
                os.startfile(os.path.normpath(file_path))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{str(e)}")
        else:
            messagebox.showwarning("Not Found", "The selected file could not be found. It may have been moved.")

    def get_unique_dest_path(self, dest_folder, filename):
        """Generates a unique filename by appending (1), (2), etc., if a collision occurs."""
        base_name, ext = os.path.splitext(filename)
        dest_path = os.path.join(dest_folder, filename)
        
        counter = 1
        while os.path.exists(dest_path):
            new_name = f"{base_name} ({counter}){ext}"
            dest_path = os.path.join(dest_folder, new_name)
            counter += 1
            
        return dest_path

    def transfer_files(self):
        all_items = self.tree.get_children()
        
        if not all_items:
            messagebox.showinfo("Empty", "There are no files listed to transfer.")
            return

        action_verb = "Move" if self.transfer_mode.get() == "move" else "Copy"
        
        dest_folder = filedialog.askdirectory(title=f"Select Destination Folder to {action_verb} Google Files")
        if not dest_folder:
            return

        if self.transfer_mode.get() == "move":
            if not messagebox.askyesno(
                    "Warning: Move",
                    f"You chose MOVE for {len(all_items)} Google files.\n\n"
                    "Files like .gdoc and .gsheet are links to documents stored in Google Drive. "
                    "If they are inside a synced Google Drive folder, moving them out of it can "
                    "REMOVE the documents from Google Drive (Drive treats it as a delete).\n\n"
                    "Copy is the safer choice.\n\n"
                    "Move them anyway?",
                    icon=messagebox.WARNING):
                return

        self.lbl_status.config(text=f"{action_verb}ing files to {dest_folder}...", fg="orange")
        self.root.update()

        success_count = 0
        error_count = 0
        error_messages = []
        mode = self.transfer_mode.get()

        for item in all_items:
            file_path = self.tree.item(item, 'values')[2]
            file_name = self.tree.item(item, 'text')
            
            if os.path.exists(file_path):
                safe_dest_path = self.get_unique_dest_path(dest_folder, file_name)
                
                try:
                    if mode == "move":
                        shutil.move(file_path, safe_dest_path)
                    elif mode == "copy":
                        shutil.copy2(file_path, safe_dest_path)
                    
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"{file_name}: {str(e)}")

        self.tree.delete(*self.tree.get_children())
        
        action_past_tense = "Moved" if mode == "move" else "Copied"
        
        if error_count == 0:
            status_message = f"{action_past_tense} {success_count} Google files successfully."
            self.lbl_status.config(text=status_message, fg="green")
            messagebox.showinfo("Transfer Complete", status_message)
        else:
            print(f"\n--- {action_verb.upper()} ERRORS ---")
            for err in error_messages:
                print(err)
            print("-------------------\n")

            status_message = f"{action_past_tense} {success_count} files successfully.\n\nFailed to {action_verb.lower()} {error_count} files.\n\nError Details:\n"
            status_message += "\n".join(error_messages[:8]) 
            
            if len(error_messages) > 8:
                status_message += f"\n...and {len(error_messages) - 8} more errors. Check the command line window for the full list."

            self.lbl_status.config(text=f"{action_past_tense} {success_count} files. {error_count} errors.", fg="red")
            messagebox.showwarning("Transfer Completed with Errors", status_message)

if __name__ == "__main__":
    root = tk.Tk()
    app = GoogleDriveFileMoverApp(root)
    root.mainloop()