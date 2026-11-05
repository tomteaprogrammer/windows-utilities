import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, PanedWindow
import sys
import threading

class FileConsolidatorApp:
    def __init__(self, root):
        """
        Initializes the main application window.
        """
        self.root = root
        self.root.title("Folder Merger")
        self.root.geometry("700x700") # Increased size for better log visibility
        self.root.configure(bg="#f0f0f0")

        self.source_dirs = []
        self.dest_dir = ""
        self.last_operation_log = []

        # --- UI Elements ---
        main_frame = tk.Frame(self.root, padx=15, pady=15, bg="#f0f0f0")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Top section for controls
        controls_frame = tk.Frame(main_frame, bg="#f0f0f0")
        controls_frame.pack(fill=tk.X, side=tk.TOP)

        # Source Directories Section
        source_frame = tk.LabelFrame(controls_frame, text="Parent Directories (contents of their subfolders will be moved)", padx=10, pady=10, bg="#f0f0f0", fg="#333")
        source_frame.pack(fill=tk.X, pady=(0, 10))
        self.source_listbox = tk.Listbox(source_frame, height=5, selectmode=tk.MULTIPLE)
        self.source_listbox.pack(fill=tk.X, expand=True, pady=(0, 5))
        add_source_button = tk.Button(source_frame, text="Add Parent Folder(s)", command=self.add_source_dirs, bg="#4CAF50", fg="white", relief=tk.FLAT)
        add_source_button.pack(side=tk.LEFT, padx=(0, 5))
        remove_source_button = tk.Button(source_frame, text="Remove Selected", command=self.remove_source_dirs, bg="#f44336", fg="white", relief=tk.FLAT)
        remove_source_button.pack(side=tk.LEFT)

        # Destination Directory Section
        dest_frame = tk.LabelFrame(controls_frame, text="Destination Directory", padx=10, pady=10, bg="#f0f0f0", fg="#333")
        dest_frame.pack(fill=tk.X, pady=10)
        self.dest_label = tk.Label(dest_frame, text="No destination selected", bg="#f0f0f0", anchor="w")
        self.dest_label.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 10))
        select_dest_button = tk.Button(dest_frame, text="Select Destination", command=self.select_dest_dir, bg="#2196F3", fg="white", relief=tk.FLAT)
        select_dest_button.pack(side=tk.RIGHT)

        # Action Buttons Frame
        action_frame = tk.Frame(controls_frame, bg="#f0f0f0")
        action_frame.pack(fill=tk.X, pady=10)
        self.move_button = tk.Button(action_frame, text="Move & Merge Contents", command=self.start_move_operation, font=("Arial", 12, "bold"), bg="#FF9800", fg="white", relief=tk.GROOVE, borderwidth=2)
        self.move_button.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=5, padx=(0, 5))
        self.undo_button = tk.Button(action_frame, text="Undo Last Move", command=self.start_undo_operation, font=("Arial", 12, "bold"), bg="#607D8B", fg="white", relief=tk.GROOVE, borderwidth=2, state=tk.DISABLED)
        self.undo_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, ipady=5, padx=(5, 0))

        # PanedWindow for resizeable log areas
        paned_window = PanedWindow(main_frame, orient=tk.VERTICAL, sashrelief=tk.RAISED, bg="#f0f0f0")
        paned_window.pack(fill=tk.BOTH, expand=True, pady=(10,0))

        # Status/Log Section
        log_frame = tk.LabelFrame(paned_window, text="Log", padx=10, pady=10, bg="#f0f0f0", fg="#333")
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        paned_window.add(log_frame, height=200)

        # Error Log Section
        error_log_frame = tk.LabelFrame(paned_window, text="Errors", padx=10, pady=10, bg="#f0f0f0", fg="#c00")
        self.error_log_area = scrolledtext.ScrolledText(error_log_frame, wrap=tk.WORD, state='disabled', height=5, bg="#ffdddd")
        self.error_log_area.pack(fill=tk.BOTH, expand=True)
        paned_window.add(error_log_frame, height=100)

    def _win_path(self, path):
        if sys.platform == 'win32':
            path = os.path.abspath(path)
            if not path.startswith('\\\\?\\'):
                return '\\\\?\\' + path
        return path

    def log(self, message):
        self.root.after(0, self._log_update, message, self.log_area)

    def log_error(self, message):
        self.root.after(0, self._log_update, message, self.error_log_area)

    def _log_update(self, message, text_widget):
        text_widget.config(state='normal')
        text_widget.insert(tk.END, message + "\n")
        text_widget.config(state='disabled')
        text_widget.see(tk.END)

    def add_source_dirs(self):
        directory = filedialog.askdirectory(title="Select a Parent Folder")
        if directory and directory not in self.source_dirs:
            self.source_dirs.append(directory)
            self.source_listbox.insert(tk.END, directory)
            self.log(f"Added parent source: {directory}")

    def remove_source_dirs(self):
        selected_indices = self.source_listbox.curselection()
        for i in sorted(selected_indices, reverse=True):
            removed_dir = self.source_listbox.get(i)
            self.source_listbox.delete(i)
            if removed_dir in self.source_dirs:
                self.source_dirs.remove(removed_dir)
                self.log(f"Removed parent source: {removed_dir}")

    def select_dest_dir(self):
        directory = filedialog.askdirectory(title="Select Destination Folder")
        if directory:
            self.dest_dir = directory
            display_text = self.dest_dir
            if len(display_text) > 50:
                display_text = "..." + display_text[-47:]
            self.dest_label.config(text=display_text)
            self.log(f"Destination set to: {self.dest_dir}")

    def toggle_buttons(self, state):
        self.move_button.config(state=state)
        if state == tk.NORMAL and self.last_operation_log:
             self.undo_button.config(state=tk.NORMAL)
        else:
            self.undo_button.config(state=tk.DISABLED)

    @staticmethod
    def _is_inside(path, folder):
        """True if path is inside folder or is the same folder."""
        path = os.path.normcase(os.path.abspath(path))
        folder = os.path.normcase(os.path.abspath(folder))
        try:
            return os.path.commonpath([path, folder]) == folder
        except ValueError:  # different drives
            return False

    def start_move_operation(self):
        if not self.source_dirs or not self.dest_dir:
            messagebox.showwarning("Warning", "Please select source and destination directories.")
            return
        dest_norm = os.path.normcase(os.path.abspath(self.dest_dir))
        for src_dir in self.source_dirs:
            if (self._is_inside(self.dest_dir, src_dir)
                    and dest_norm != os.path.normcase(os.path.abspath(src_dir))):
                messagebox.showerror(
                    "Destination inside a parent folder",
                    f"The destination is inside this parent folder:\n{src_dir}\n\n"
                    "Its files would be moved into themselves. Choose a destination outside the parent folders.")
                return
        sources = "\n".join(self.source_dirs)
        if not messagebox.askyesno(
                "Confirm Move",
                "The contents of every subfolder in these parent folders will be MOVED:\n\n"
                f"{sources}\n\nInto:\n{self.dest_dir}\n\n"
                "Same-name files get a number added, for example 'name (1).txt'.\n"
                "Emptied folders are removed. You can use 'Undo Last Move' afterwards.\n\n"
                "Start moving now?"):
            return
        self.toggle_buttons(tk.DISABLED)
        threading.Thread(target=self.move_subfolder_contents).start()

    def start_undo_operation(self):
        if not self.last_operation_log:
            messagebox.showinfo("Info", "There is no operation to undo.")
            return
        if messagebox.askyesno("Confirm Undo", "Are you sure you want to undo the last move operation?"):
            self.toggle_buttons(tk.DISABLED)
            threading.Thread(target=self.undo_last_move).start()

    def move_item_recursively(self, source_path, dest_parent_path, operation_log):
        item_name = os.path.basename(source_path)
        dest_path = os.path.join(dest_parent_path, item_name)
        source_path_wp = self._win_path(source_path)
        dest_path_wp = self._win_path(dest_path)

        if os.path.isdir(source_path_wp) and os.path.isdir(dest_path_wp):
            self.log(f"    - Merging into existing folder: '{item_name}'")
            for inner_item_name in os.listdir(source_path_wp):
                original_inner_source = os.path.join(source_path, inner_item_name)
                self.move_item_recursively(original_inner_source, dest_path, operation_log)
            try:
                os.rmdir(source_path_wp)
            except OSError: pass
            return

        final_dest_path = dest_path
        final_dest_path_wp = dest_path_wp
        if os.path.exists(final_dest_path_wp):
            base_name, extension = os.path.splitext(item_name)
            counter = 1
            while os.path.exists(final_dest_path_wp):
                new_name = f"{base_name} ({counter}){extension}"
                final_dest_path = os.path.join(dest_parent_path, new_name)
                final_dest_path_wp = self._win_path(final_dest_path)
                counter += 1
            self.log(f"    - Conflict: Renaming '{item_name}' to '{os.path.basename(final_dest_path)}'")
        
        try:
            shutil.move(source_path_wp, final_dest_path_wp)
            self.log(f"    - Moved: '{os.path.basename(final_dest_path)}'")
            operation_log.append({'source': source_path, 'dest': final_dest_path})
        except Exception as e:
            self.log_error(f"    - Error moving '{item_name}': {e}")

    def move_subfolder_contents(self):
        # Each move is recorded in self.last_operation_log as soon as it happens,
        # so 'Undo Last Move' still works if the run stops part way.
        self.last_operation_log = []
        self.root.after(0, self.undo_button.config, {'state': tk.DISABLED})
        self.log("\n--- Starting Content Move & Merge Operation ---")
        current_operation_log = self.last_operation_log
        error_message = None
        try:
            for src_dir in self.source_dirs:
                src_dir_wp = self._win_path(src_dir)
                if not os.path.isdir(src_dir_wp):
                    self.log_error(f"Warning: Parent directory not found, skipping: {src_dir}")
                    continue
                self.log(f"Processing parent directory: {src_dir}")
                for subfolder_name in os.listdir(src_dir_wp):
                    subfolder_path = os.path.join(src_dir, subfolder_name)
                    subfolder_path_wp = self._win_path(subfolder_path)
                    if os.path.isdir(subfolder_path_wp):
                        self.log(f"  - Processing subfolder: {subfolder_name}")
                        for item_name in os.listdir(subfolder_path_wp):
                            source_item_path = os.path.join(subfolder_path, item_name)
                            self.move_item_recursively(source_item_path, self.dest_dir, current_operation_log)
                    else:
                        self.log(f"  - Skipping top-level file: {subfolder_name}")
        except Exception as e:
            error_message = str(e)
            self.log_error(f"An unexpected error occurred during move: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred during the move operation: {error_message}"))
        finally:
            moved = len(current_operation_log)
            self.log(f"--- Operation Complete: {moved} items moved. ---")
            if error_message is None:
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Content consolidation complete!\n\n{moved} items were moved."))
            self.root.after(0, self.toggle_buttons, tk.NORMAL)

    def undo_last_move(self):
        log_to_undo = self.last_operation_log
        if not log_to_undo:
            self.log("Nothing to undo.")
            self.root.after(0, self.toggle_buttons, tk.NORMAL)
            return
        self.log("\n--- Starting Undo Operation ---")
        total_undone = 0
        error_message = None
        try:
            for move_record in reversed(log_to_undo):
                original_source = move_record['source']
                current_location = move_record['dest']
                original_parent_dir = os.path.dirname(original_source)
                os.makedirs(self._win_path(original_parent_dir), exist_ok=True)
                try:
                    current_location_wp = self._win_path(current_location)
                    original_source_wp = self._win_path(original_source)
                    if os.path.exists(current_location_wp):
                        shutil.move(current_location_wp, original_source_wp)
                        self.log(f"  - Undone: Moved '{os.path.basename(current_location)}' back to '{original_parent_dir}'")
                        total_undone += 1
                    else:
                        self.log_error(f"  - Warning: Cannot find '{current_location}' to undo move. It may have been moved or deleted.")
                except Exception as e:
                    self.log_error(f"  - Error undoing move for '{os.path.basename(current_location)}': {e}")
            self.last_operation_log.clear()
        except Exception as e:
            error_message = str(e)
            self.log_error(f"An unexpected error occurred during undo: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred during the undo operation: {error_message}"))
        finally:
            self.log(f"--- Undo Complete: {total_undone} items moved back. ---")
            if error_message is None:
                self.root.after(0, lambda: messagebox.showinfo("Undo Complete", f"{total_undone} items were moved back to their original locations."))
            self.root.after(0, self.toggle_buttons, tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = FileConsolidatorApp(root)
    root.mainloop()
