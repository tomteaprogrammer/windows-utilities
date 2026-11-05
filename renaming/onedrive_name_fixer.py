# -*- coding: utf-8 -*-
r"""
OneDrive Name Fixer

Description:
This script provides a responsive graphical user interface (GUI) to select a folder.
It scans files in a background thread to prevent the UI from freezing. It
recursively scans all files and subdirectories to find any items containing
characters or names that are illegal in Microsoft Windows and OneDrive, shows
a preview list of the planned renames, and only renames after you click Yes.
A text log and a CSV of old -> new names are saved in the root of the
selected folder. The CSV can be used with "Undo a Previous Run" to rename
the items back.

Features:
- Long Path Support (Windows): Automatically handles file paths longer than 260
  characters by using the Windows `\\?\` prefix, preventing "path not found" errors.
- Safe Two-Phase Renaming: First, scans the entire directory to create a "rename plan",
  then executes the plan from the deepest items up. This prevents errors caused
  by renaming parent directories before their contents.
- Validation: Checks for illegal characters (<>:"/|?*), leading/trailing
  spaces and periods, and reserved system names (CON, PRN, AUX, etc.).
  Optional rules (off by default): replace "~" and collapse ".." into ".".
- Multithreading: Long-running file operations are handled in a separate thread
  to keep the GUI responsive.
- Real-time Progress: The GUI and CLI both display live progress.
- Robust File Handling: Uses os.walk for deep scanning and handles potential
  renaming collisions by appending a number.
- Logging: Prints progress to the console and GUI, and saves a log file and an
  undo CSV for each run.
"""

import os
import sys
import csv
import datetime
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext
    GUI_ENABLED = True
except ImportError:
    GUI_ENABLED = False

# --- Core Logic ---

ILLEGAL_CHARACTERS = r'<>:"/|?*'
POTENTIALLY_PROBLEMATIC_CHARS = r'~'
RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6',
    'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6',
    'LPT7', 'LPT8', 'LPT9'
}
REPLACEMENT_CHAR = '_'
LOG_PREFIX = 'renamed_files_log'
UNDO_PREFIX = 'renamed_files_undo'

def normalize_path_for_windows(path):
    r"""
    On Windows, prepends the `\\?\` prefix to an absolute path to handle long path names.
    On other OSes, returns the path unmodified.
    """
    if sys.platform == 'win32':
        path = os.path.abspath(path)
        if path.startswith('\\\\?\\'):
            return path
        if path.startswith('\\\\'):
            return '\\\\?\\UNC\\' + path[2:]
        return '\\\\?\\' + path
    return path

def sanitize_name(name, replace_tilde=False, collapse_dots=False):
    """Performs a comprehensive sanitization of a filename or directory name.

    replace_tilde and collapse_dots are optional rules (off by default):
    "~" and ".." are allowed by Windows and OneDrive today.
    """
    base_name, extension = os.path.splitext(name)
    sanitized_base = base_name
    chars = ILLEGAL_CHARACTERS + (POTENTIALLY_PROBLEMATIC_CHARS if replace_tilde else '')
    for char in chars:
        sanitized_base = sanitized_base.replace(char, REPLACEMENT_CHAR)

    if collapse_dots:
        while '..' in sanitized_base:
            sanitized_base = sanitized_base.replace('..', '.')

    sanitized_base = sanitized_base.strip(' .')

    if sanitized_base.upper() in RESERVED_NAMES:
        sanitized_base = REPLACEMENT_CHAR + sanitized_base
    if not sanitized_base:
        sanitized_base = "renamed_file"
    return sanitized_base + extension

def get_unique_path(path):
    """Appends a number to a path if it already exists to make it unique."""
    # Use normalized path for existence check to support long paths
    if not os.path.exists(normalize_path_for_windows(path)):
        return path
    directory, filename = os.path.split(path)
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{name}-{counter}{ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(normalize_path_for_windows(new_path)):
            return new_path
        counter += 1

def _unique_output_path(directory, prefix, ext):
    """Returns a timestamped file path in directory that does not exist yet."""
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return get_unique_path(os.path.join(directory, f"{prefix}_{stamp}{ext}"))

def scan_directory(target_dir, log=print, progress=None, replace_tilde=False, collapse_dots=False):
    """Phase 1: walks target_dir and returns (rename_plan, scanned_count). Nothing is renamed."""
    rename_plan = []
    scanned_count = 0

    log("Phase 1: Discovering items to rename...")
    log("-" * 50)

    for root, dirs, files in os.walk(target_dir, topdown=True):
        for dirname in dirs:
            sanitized_dirname = sanitize_name(dirname, replace_tilde, collapse_dots)
            if sanitized_dirname != dirname:
                old_path = os.path.join(root, dirname)
                new_path = os.path.join(root, sanitized_dirname)
                rename_plan.append((old_path, new_path))

        for filename in files:
            scanned_count += 1
            if progress:
                progress(scanned_count)

            sanitized_filename = sanitize_name(filename, replace_tilde, collapse_dots)
            if sanitized_filename != filename:
                old_path = os.path.join(root, filename)
                new_path = os.path.join(root, sanitized_filename)
                rename_plan.append((old_path, new_path))

    rename_plan.sort(key=lambda x: len(x[0]), reverse=True)
    log(f"Phase 1 Complete: {len(rename_plan)} items planned for renaming.")
    return rename_plan, scanned_count

def execute_plan(target_dir, rename_plan, log=print):
    """Phase 2: renames each item in the plan, deepest first.

    Every successful rename is written to an undo CSV (old_path, new_path) right away.
    Returns (rename_count, log_file_path or None, csv_path or None).
    """
    log_records = []
    log("Phase 2: Executing rename plan...")
    log("-" * 50)

    csv_path = _unique_output_path(target_dir, UNDO_PREFIX, '.csv')
    csv_file = None
    writer = None
    try:
        csv_file = open(csv_path, 'w', newline='', encoding='utf-8-sig')
        writer = csv.writer(csv_file)
        writer.writerow(['old_path', 'new_path'])
    except OSError as e:
        log(f"WARNING: Could not create undo file '{csv_path}'. Reason: {e}")
        csv_path = None

    rename_count = 0
    try:
        for old_path, new_path in rename_plan:
            try:
                final_new_path = get_unique_path(new_path)

                # Use normalized paths for the actual rename operation
                os.rename(normalize_path_for_windows(old_path), normalize_path_for_windows(final_new_path))

                if writer:
                    writer.writerow([old_path, final_new_path])
                    csv_file.flush()
                log_message = f"SUCCESS: Renamed '{old_path}'\n     --> '{final_new_path}'\n"
                log(log_message)
                log_records.append(log_message)
                rename_count += 1
            except (OSError, PermissionError) as e:
                error_message = f"ERROR: Could not rename '{old_path}'. Reason: {e}\n"
                log(error_message)
                log_records.append(error_message)
    finally:
        if csv_file:
            csv_file.close()

    if csv_path and rename_count == 0:
        try:
            os.remove(csv_path)
        except OSError:
            pass
        csv_path = None

    log("-" * 50)
    log(f"Total items successfully renamed: {rename_count}")

    log_file_path = None
    if log_records:
        log_file_path = _unique_output_path(target_dir, LOG_PREFIX, '.txt')
        try:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write("OneDrive Name Fixer Log\n")
                f.write(f"Report generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Processed Directory: {target_dir}\n")
                if csv_path:
                    f.write(f"Undo file: {csv_path}\n")
                f.write("-" * 50 + "\n\n")
                f.writelines(log_records)
            log(f"\nLog file saved to: {log_file_path}")
        except (OSError, PermissionError) as e:
            log(f"\nCRITICAL ERROR: Could not write log file. Reason: {e}")
            log_file_path = None
    if csv_path:
        log(f"Undo file saved to: {csv_path}")
    return rename_count, log_file_path, csv_path

def read_undo_csv(csv_path):
    """Reads an undo CSV and returns a list of (old_path, new_path)."""
    pairs = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != ['old_path', 'new_path']:
            raise ValueError("This file is not an undo file made by OneDrive Name Fixer.")
        for row in reader:
            if len(row) == 2:
                pairs.append((row[0], row[1]))
    return pairs

def undo_renames(pairs, log=print):
    """Renames new_path back to old_path, in reverse order of the original run.

    Skips an item if the renamed item is gone or the old name is taken again.
    Returns (restored_count, skipped_count).
    """
    restored = skipped = 0
    for old_path, new_path in reversed(pairs):
        src = normalize_path_for_windows(new_path)
        dst = normalize_path_for_windows(old_path)
        if not os.path.exists(src):
            log(f"SKIPPED (not found): '{new_path}'")
            skipped += 1
            continue
        if os.path.exists(dst):
            log(f"SKIPPED (old name already in use): '{old_path}'")
            skipped += 1
            continue
        try:
            os.rename(src, dst)
            log(f"RESTORED: '{new_path}'\n     --> '{old_path}'")
            restored += 1
        except OSError as e:
            log(f"ERROR: Could not restore '{new_path}'. Reason: {e}")
            skipped += 1
    return restored, skipped

# --- GUI Application Class ---

class SanitizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OneDrive Name Fixer")
        self.root.geometry("700x600")
        self.root.minsize(500, 400)
        self.root.configure(bg='#f0f0f0')
        self.last_target_dir = None

        main_frame = tk.Frame(root, padx=15, pady=15, bg='#f0f0f0')
        main_frame.pack(expand=True, fill=tk.BOTH)

        controls_frame = tk.Frame(main_frame, bg='#f0f0f0')
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        self.select_button = tk.Button(
            controls_frame, text="Select Folder and Start Scan", command=self.start_processing,
            font=("Helvetica", 12, "bold"), bg='#0078d4', fg='white', relief=tk.FLAT, padx=10, pady=10
        )
        self.select_button.pack(fill=tk.X)

        options_frame = tk.Frame(controls_frame, bg='#f0f0f0')
        options_frame.pack(fill=tk.X, pady=(8, 0))
        self.replace_tilde_var = tk.BooleanVar(value=False)
        self.collapse_dots_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text='Also replace "~" with "_"', variable=self.replace_tilde_var,
                       bg='#f0f0f0').pack(side=tk.LEFT)
        tk.Checkbutton(options_frame, text='Also change ".." to "."', variable=self.collapse_dots_var,
                       bg='#f0f0f0').pack(side=tk.LEFT, padx=(15, 0))
        self.undo_button = tk.Button(options_frame, text="Undo a Previous Run...", command=self.start_undo)
        self.undo_button.pack(side=tk.RIGHT)

        progress_frame = tk.Frame(main_frame, bg='#f0f0f0', pady=5)
        progress_frame.pack(fill=tk.X)
        self.progress_label = tk.Label(progress_frame, text="Ready to start.", font=("Helvetica", 10), bg='#f0f0f0', anchor='w')
        self.progress_label.pack(fill=tk.X)

        log_frame = tk.LabelFrame(main_frame, text="Processing Log", font=("Helvetica", 10), padx=10, pady=10, bg='#f0f0f0')
        log_frame.pack(expand=True, fill=tk.BOTH)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9),
            bg='#ffffff', relief=tk.SUNKEN, borderwidth=1
        )
        self.log_text.pack(expand=True, fill=tk.BOTH)

    # Thread-safe helpers: worker threads call these, the widgets are changed on the main thread.
    def log(self, message):
        self.root.after(0, lambda: self._update_log_widget(message))

    def _update_log_widget(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_busy(self, text):
        self.select_button.config(state=tk.DISABLED, text=text)
        self.undo_button.config(state=tk.DISABLED)

    def start_processing(self):
        target_dir = filedialog.askdirectory(title="Select a Folder to Sanitize")
        if not target_dir:
            messagebox.showinfo("Cancelled", "Operation cancelled.")
            return
        self.last_target_dir = target_dir

        self._clear_log()
        self._set_busy("Scanning...")
        self.progress_label.config(text="Preparing to scan...")

        options = (self.replace_tilde_var.get(), self.collapse_dots_var.get())
        thread = threading.Thread(target=self._scan_thread_task, args=(target_dir, options))
        thread.daemon = True
        thread.start()

    def _scan_thread_task(self, target_dir, options):
        try:
            self.root.after(0, lambda: self.progress_label.config(text="Calculating total files..."))
            # Use a generator expression for memory efficiency on huge directories
            total_files = sum(len(files) for _, _, files in os.walk(target_dir))
            rename_plan, scanned_count = scan_directory(
                target_dir, log=self.log,
                progress=lambda s: self.root.after(0, lambda: self.update_progress(s, total_files)),
                replace_tilde=options[0], collapse_dots=options[1]
            )
            self.root.after(0, lambda: self._on_scan_complete(target_dir, rename_plan, scanned_count))
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            print(error_msg)
            self.root.after(0, lambda: messagebox.showerror("Fatal Error", error_msg))
            self.root.after(0, self._reset_ui)

    def _on_scan_complete(self, target_dir, rename_plan, scanned_count):
        if not rename_plan:
            self._update_log_widget("\nNo files or directories need renaming.")
            self._reset_ui()
            messagebox.showinfo("Scan Complete", f"{scanned_count} files scanned.\n\nNothing needs renaming.")
            return

        self._update_log_widget("\nPREVIEW - nothing has been renamed yet:")
        for old_path, new_path in rename_plan:
            rel = os.path.relpath(old_path, target_dir)
            self._update_log_widget(f"  {rel}\n     --> {os.path.basename(new_path)}")

        answer = messagebox.askyesno(
            "Rename Items?",
            f"{len(rename_plan)} items will be renamed ({scanned_count} files scanned).\n\n"
            "The preview list is in the log window.\n\n"
            "A log and an undo file (CSV) will be saved in the selected folder.\n\n"
            "Rename these items now?"
        )
        if not answer:
            self._update_log_widget("\nCancelled. Nothing was renamed.")
            self._reset_ui()
            return

        self._set_busy("Renaming...")
        self.progress_label.config(text=f"Renaming {len(rename_plan)} items...")
        thread = threading.Thread(target=self._rename_thread_task, args=(target_dir, rename_plan, scanned_count))
        thread.daemon = True
        thread.start()

    def _rename_thread_task(self, target_dir, rename_plan, scanned_count):
        try:
            rename_count, log_path, csv_path = execute_plan(target_dir, rename_plan, log=self.log)
            self.root.after(0, lambda: self._on_processing_complete(rename_count, scanned_count, log_path, csv_path))
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            print(error_msg)
            self.root.after(0, lambda: messagebox.showerror("Fatal Error", error_msg))
            self.root.after(0, self._reset_ui)

    def update_progress(self, processed_count, total_count):
        self.progress_label.config(text=f"Scanning file: {processed_count} / {total_count}")

    def _on_processing_complete(self, rename_count, scanned_count, log_path, csv_path):
        self._reset_ui()
        details = ""
        if log_path:
            details += f"\n\nLog: {log_path}"
        if csv_path:
            details += f"\nUndo file: {csv_path}"
        messagebox.showinfo(
            "Process Complete",
            f"{rename_count} items renamed out of {scanned_count} files scanned.{details}"
        )

    def start_undo(self):
        csv_path = filedialog.askopenfilename(
            title="Select an undo file (renamed_files_undo_....csv)",
            initialdir=self.last_target_dir or None,
            filetypes=[("Undo CSV", f"{UNDO_PREFIX}_*.csv"), ("CSV files", "*.csv")]
        )
        if not csv_path:
            return
        try:
            pairs = read_undo_csv(csv_path)
        except (OSError, ValueError, csv.Error) as e:
            messagebox.showerror("Undo", f"Could not read the undo file.\n\n{e}")
            return
        if not pairs:
            messagebox.showinfo("Undo", "The undo file has no renames in it.")
            return
        if not messagebox.askyesno("Undo Renames?",
                                   f"Rename {len(pairs)} items back to their old names?"):
            return

        self._clear_log()
        self._set_busy("Undoing...")
        self.progress_label.config(text=f"Restoring {len(pairs)} items...")

        def task():
            try:
                restored, skipped = undo_renames(pairs, log=self.log)
                self.root.after(0, lambda: self._on_undo_complete(restored, skipped))
            except Exception as e:
                error_msg = f"An unexpected error occurred: {e}"
                self.root.after(0, lambda: messagebox.showerror("Fatal Error", error_msg))
                self.root.after(0, self._reset_ui)

        threading.Thread(target=task, daemon=True).start()

    def _on_undo_complete(self, restored, skipped):
        self._reset_ui()
        messagebox.showinfo("Undo Complete", f"{restored} items restored.\n{skipped} items skipped (see the log window).")

    def _reset_ui(self):
        self.select_button.config(state=tk.NORMAL, text="Select Another Folder and Start Scan")
        self.undo_button.config(state=tk.NORMAL)
        self.progress_label.config(text="Ready to start.")

# --- Main Execution ---

def run_cli():
    """Runs the script in command-line mode with better feedback."""
    try:
        from tqdm import tqdm
    except ImportError:
        print("The package 'tqdm' is needed for command-line mode.")
        print("Install it with:  pip install -r requirements.txt")
        sys.exit(1)
    print("--- OneDrive Name Fixer (Command-Line Mode) ---")
    while True:
        target_dir = input("Enter the full path to the folder to scan (or 'exit' to quit):\n> ")
        if target_dir.lower() == 'exit':
            break
        if os.path.isdir(target_dir):
            print("Calculating total files... (This may take a moment on large folders)")
            total_files = 0
            try:
                for _, _, files in os.walk(target_dir):
                    total_files += len(files)
                    print(f"\rFound: {total_files} files... ", end="", flush=True)
                print()
            except Exception as e:
                print(f"\nAn error occurred during file counting: {e}")
                continue

            replace_tilde = input('Also replace "~" with "_"? (y/n, default n): ').strip().lower() == 'y'
            collapse_dots = input('Also change ".." to "."? (y/n, default n): ').strip().lower() == 'y'
            with tqdm(total=total_files, unit="file", desc="Scanning") as pbar:
                rename_plan, _ = scan_directory(target_dir, log=pbar.write,
                                                progress=lambda s: pbar.update(1),
                                                replace_tilde=replace_tilde, collapse_dots=collapse_dots)
            if not rename_plan:
                print("No files or directories need renaming.")
            else:
                print("\nPREVIEW - nothing has been renamed yet:")
                for old_path, new_path in rename_plan:
                    print(f"  {old_path}\n     --> {os.path.basename(new_path)}")
                if input(f"\nRename these {len(rename_plan)} items now? (y/n): ").strip().lower() == 'y':
                    execute_plan(target_dir, rename_plan)
                else:
                    print("Cancelled. Nothing was renamed.")
            print("\nProcess finished for this directory." + "\n" + "-" * 50)
        else:
            print(f"ERROR: The path '{target_dir}' is not a valid directory. Please try again.")

if __name__ == "__main__":
    if GUI_ENABLED:
        app_root = tk.Tk()
        app = SanitizerApp(app_root)
        app_root.mainloop()
    else:
        run_cli()
