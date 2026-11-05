import os
import sys
import shutil
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
from datetime import datetime
import traceback
import json

UNDO_LOG_NAME = 'undo_log.jsonl'

def get_long_path(path):
    """Converts a path to a Windows long path format, including network drives."""
    abspath = os.path.abspath(path)
    if sys.platform != 'win32':
        return abspath
    if abspath.startswith('\\\\?\\'):
        return abspath
    if abspath.startswith('\\\\'): # Handle network/UNC paths
        return '\\\\?\\UNC\\' + abspath[2:]
    return '\\\\?\\' + abspath

def clean_path(path):
    """Removes the long path prefix for display. The UNC form is checked first."""
    if path.startswith('\\\\?\\UNC\\'):
        return '\\\\' + path[len('\\\\?\\UNC\\'):]
    if path.startswith('\\\\?\\'):
        return path[len('\\\\?\\'):]
    return path

def open_in_explorer(filepath):
    subprocess.run(['explorer', '/select,', os.path.normpath(clean_path(filepath))])

def log_error(log_file_path, filepath, error_message):
    shown_path = clean_path(filepath) if filepath else "Unknown Path"
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Error on: {shown_path}\n")
        f.write(f"Details: {error_message}\n")
        f.write("-" * 50 + "\n")

def unique_path(folder, name):
    """Returns folder/name, or folder/name_1, name_2 ... if that name is taken."""
    dest_path = os.path.join(folder, name)
    base, ext = os.path.splitext(name)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(folder, f"{base}_{counter}{ext}")
        counter += 1
    return dest_path

class UndoLog:
    """Writes one line per action as it happens, so a run that stops part way can still be undone."""
    def __init__(self, path):
        self.file = open(path, 'a', encoding='utf-8')

    def add(self, **record):
        self.file.write(json.dumps(record) + "\n")
        self.file.flush()

    def close(self):
        self.file.close()

def process_zips(root_dir):
    root_dir_long = get_long_path(root_dir)
    delete_dir = os.path.join(root_dir_long, 'delete')
    review_dir = os.path.join(root_dir_long, 'review')
    log_file_path = os.path.join(root_dir_long, 'error_log.txt')
    undo_log_path = os.path.join(root_dir_long, UNDO_LOG_NAME)
    
    os.makedirs(delete_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    
    skipped_zips = []
    undo_log = UndoLog(undo_log_path)

    print("\nStarting crawl... (This will print every folder it checks)")
    print("-" * 50)

    # Error handler for os.walk so it doesn't silently fail on blocked folders
    def walk_error(err):
        print(f"BLOCKED BY WINDOWS: Cannot read folder {err.filename}")
        log_error(log_file_path, err.filename, f"Folder access denied by OS: {err}")

    # followlinks=False: shortcuts and symlinks to other folders are not followed (avoids loops)
    try:
        for dirpath, dirnames, filenames in os.walk(root_dir_long, followlinks=False, onerror=walk_error):
        
            # Print the current folder to the console so you can watch it crawl
            print(f"Scanning: {clean_path(dirpath)}")
        
            dirs_to_exclude = []
            for d in dirnames:
                abs_d = os.path.abspath(os.path.join(dirpath, d))
                if abs_d == os.path.abspath(delete_dir) or abs_d == os.path.abspath(review_dir):
                    dirs_to_exclude.append(d)
                
            for d in dirs_to_exclude:
                dirnames.remove(d)
            
            for filename in filenames:
                if filename.lower().endswith('.zip'):
                    filepath = os.path.join(dirpath, filename)
                
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zf:
                            has_nested_zip = any(name.lower().endswith('.zip') for name in zf.namelist())
                        
                        if has_nested_zip:
                            dest_path = unique_path(review_dir, filename)
                            shutil.move(filepath, dest_path)
                            skipped_zips.append(dest_path)
                            undo_log.add(type="moved_zip", original=filepath, current=dest_path)
                        else:
                            # Extract into a NEW folder named after the zip, so existing files are never replaced
                            extract_dir = unique_path(dirpath, os.path.splitext(filename)[0])
                            os.makedirs(extract_dir)
                            undo_log.add(type="created_dir", path=extract_dir)
                            with zipfile.ZipFile(filepath, 'r') as zf:
                                for member in zf.infolist():
                                    extracted_path = zf.extract(member, extract_dir)
                                    undo_log.add(type="created_dir" if member.is_dir() else "extracted_file",
                                                 path=os.path.normpath(extracted_path))
                        
                            dest_path = unique_path(delete_dir, filename)
                            shutil.move(filepath, dest_path)
                            undo_log.add(type="moved_zip", original=filepath, current=dest_path)
                        
                    except zipfile.BadZipFile:
                        log_error(log_file_path, filepath, "BadZipFile: The file is corrupted or not a valid zip archive.")
                    except PermissionError as e:
                        log_error(log_file_path, filepath, f"PermissionError: Access denied or file is in use. ({e})")
                    except Exception as e:
                        log_error(log_file_path, filepath, f"Unexpected Error: {e}")
    finally:
        undo_log.close()

    print("-" * 50)
    if skipped_zips:
        print(f"Finished crawling. Found {len(skipped_zips)} zips with nested zips. Launching GUI...")
        show_gui(skipped_zips)
    else:
        print("Processing complete. Crawled all folders, but found NO nested zips.")
        print(f"An '{UNDO_LOG_NAME}' file has been saved in case you need to reverse these actions.")
        input("Press Enter to exit...")

def undo_action(root_dir):
    root_dir_long = get_long_path(root_dir)
    undo_log_path = os.path.join(root_dir_long, UNDO_LOG_NAME)
    
    if not os.path.exists(undo_log_path):
        shown_dir = clean_path(root_dir)
        print(f"\nNo undo log found in:\n{shown_dir}\nCannot undo actions for this folder.")
        input("Press Enter to exit...")
        return
        
    try:
        records = []
        with open(undo_log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # a line cut off by a crash
            
        print("\nStarting undo process...")
        
        moved_count = 0
        deleted_count = 0
        problems = 0
        # Reverse order: the last action is undone first
        for item in reversed(records):
            kind = item.get('type')
            if kind == 'moved_zip':
                original = item['original']
                current = item['current']
                if os.path.exists(current) and not os.path.exists(original):
                    os.makedirs(os.path.dirname(original), exist_ok=True)
                    shutil.move(current, original)
                    moved_count += 1
                elif os.path.exists(current):
                    print(f"Skipped (a file already exists at the old place): {clean_path(original)}")
                    problems += 1
            elif kind == 'extracted_file':
                # Only files this tool extracted are removed
                path = item['path']
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                        deleted_count += 1
                    except OSError as e:
                        print(f"Could not remove {clean_path(path)}: {e}")
                        problems += 1
            elif kind == 'created_dir':
                # This folder was made by the tool. Empty folders inside it are removed,
                # then the folder itself if it is empty. Anything left in it is kept.
                top = item['path']
                if os.path.isdir(top):
                    for sub, _dirs, _files in os.walk(top, topdown=False):
                        try:
                            os.rmdir(sub)
                        except OSError:
                            pass
                
        if problems == 0:
            os.remove(undo_log_path)
        
        for folder in ('delete', 'review'):
            try:
                os.rmdir(os.path.join(root_dir_long, folder))
            except OSError:
                pass

        print("\nUndo complete.")
        print(f"Restored {moved_count} zip files.")
        print(f"Removed {deleted_count} extracted files.")
        if problems:
            print(f"{problems} items could not be undone (see above). The undo log was kept.")
        input("Press Enter to exit...")
        
    except Exception as e:
        print(f"\nError during undo: {e}")
        input("Press Enter to exit...")

def show_gui(skipped_zips):
    root = tk.Tk()
    root.title("Nested Zips Moved to Review")
    root.geometry("600x400") 
    
    header = tk.Label(root, text=f"{len(skipped_zips)} files contained nested zips and were moved to the 'review' folder:")
    header.pack(padx=10, pady=10)
    
    container = tk.Frame(root)
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    canvas = tk.Canvas(container)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    for filepath in skipped_zips:
        shown_path = clean_path(filepath)
        row_frame = tk.Frame(scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        label = tk.Label(row_frame, text=shown_path, anchor='w', wraplength=450, justify="left")
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        btn = tk.Button(row_frame, text="Open in Explorer", 
                        command=lambda p=filepath: open_in_explorer(p))
        btn.pack(side=tk.RIGHT, padx=5)
                  
    close_btn = tk.Button(root, text="Close", command=root.destroy)
    close_btn.pack(pady=10)
    
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

def launch_menu():
    menu_root = tk.Tk()
    menu_root.title("Zip Processor")
    menu_root.geometry("350x150")
    menu_root.eval('tk::PlaceWindow . center')

    def start_process():
        selected_dir = filedialog.askdirectory(parent=menu_root, title="Select Parent Folder to Process Zips")
        if not selected_dir:
            return
        if not messagebox.askyesno(
                "Confirm",
                f"Process every .zip file in:\n{selected_dir}\n(and all its subfolders)?\n\n"
                "- A zip WITHOUT zips inside is extracted into a new folder with the zip's name, "
                "and the zip is moved to the 'delete' folder.\n"
                "- A zip WITH zips inside is moved to the 'review' folder.\n\n"
                "Existing files are never replaced. Use 'Undo Previous Run in a Folder' to reverse it.",
                parent=menu_root):
            return
        menu_root.destroy()
        process_zips(selected_dir)

    def start_undo():
        menu_root.destroy()
        selected_dir = filedialog.askdirectory(title="Select Parent Folder to Undo")
        if selected_dir:
            undo_action(selected_dir)

    label = tk.Label(menu_root, text="What would you like to do?", font=("Arial", 12))
    label.pack(pady=15)

    btn_process = tk.Button(menu_root, text="Process Zips in a Folder", command=start_process, width=30)
    btn_process.pack(pady=5)

    btn_undo = tk.Button(menu_root, text="Undo Previous Run in a Folder", command=start_undo, width=30)
    btn_undo.pack(pady=5)

    menu_root.mainloop()

if __name__ == "__main__":
    try:
        launch_menu()
    except Exception:
        print("\n--- CRITICAL ERROR ---")
        traceback.print_exc()
        input("Press Enter to exit...")