"""
Folder Structure Analyzer
GUI application for analyzing a folder structure (depth, sizes, dates)
and generating CSV and tree-view TXT reports for organization.
"""

import os
import csv
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from datetime import datetime
import sys

class FolderAnalyzerTool:
    """
    A GUI tool to analyze a directory's structure, depth, and contents.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Folder Structure Analyzer")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # --- Initialize variables ---
        self.folder_to_analyze_path = tk.StringVar()
        self.is_running = False
        self.stop_requested = False
        self.ignore_extensions_var = tk.BooleanVar(value=False)
        self.ignore_extensions_list = tk.StringVar(value=".DS_Store, .tmp, .log, Thumbs.db")
        self.save_folder_path = tk.StringVar()
        self.file_handler = None
        
        # --- Setup logging ---
        self.setup_logging()
        
        # --- Create GUI ---
        self.create_gui()
        
    def setup_logging(self):
        """
        Configures logging to the console. When an analysis starts, a log file is
        also written to the folder chosen in "Save Reports To" (see start_log_file).
        """
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(sys.stdout) # Print logs to the console
                ]
            )
            
            self.logger = logging.getLogger(__name__)
            self.logger.info("Folder Analyzer Tool started")
        except Exception as e:
            messagebox.showerror("Logging Error", f"Failed to initialize logger: {e}")
            self.logger = logging.getLogger(__name__) # Basic logger

    def start_log_file(self, save_dir, report_basename):
        """Writes this run's log next to its reports."""
        if self.file_handler:
            self.logger.removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None
        try:
            log_path = os.path.join(save_dir, f"{report_basename}.log")
            self.file_handler = logging.FileHandler(log_path, encoding='utf-8')
            self.file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(self.file_handler)
        except OSError as e:
            self.logger.warning(f"Could not create log file: {e}")
            
    def create_gui(self):
        """
        Creates the main GUI for the application.
        """
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # --- Configure grid weights for responsiveness ---
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        title_label = ttk.Label(main_frame, text="Folder Structure Analyzer", font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # --- Path Selection ---
        ttk.Label(main_frame, text="Folder to Analyze:", font=('Arial', 11, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        path_frame.columnconfigure(0, weight=1)
        
        self.path_entry = ttk.Entry(path_frame, textvariable=self.folder_to_analyze_path, width=60)
        self.path_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(path_frame, text="Browse...", command=self.select_folder).grid(row=0, column=1)

        ttk.Label(path_frame, text="Save Reports To:", font=('Arial', 11, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(10, 5))
        ttk.Entry(path_frame, textvariable=self.save_folder_path, width=60).grid(row=2, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(path_frame, text="Browse...", command=self.select_save_folder).grid(row=2, column=1)

        # --- Options Frame ---
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)
        
        self.ignore_check = ttk.Checkbutton(options_frame, text="Ignore specific file extensions:", variable=self.ignore_extensions_var)
        self.ignore_check.grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.ignore_entry = ttk.Entry(options_frame, textvariable=self.ignore_extensions_list, width=50)
        self.ignore_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # --- Control Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(10, 20))
        
        self.start_button = ttk.Button(button_frame, text="Start Analysis", command=self.start_analysis, style='Accent.TButton')
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_analysis, state='disabled')
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).grid(row=0, column=2)
        
        # --- Progress and Status ---
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Ready to start analysis.")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, wraplength=800)
        self.status_label.grid(row=6, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)
        
        # --- Log Display ---
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="5")
        log_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1) # Allow log to expand
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def select_folder(self):
        """
        Opens a dialog to select the folder to analyze.
        """
        folder = filedialog.askdirectory(title="Select Folder to Analyze")
        if folder:
            self.folder_to_analyze_path.set(folder)
            self.log_message(f"Folder selected: {folder}")
            
    def select_save_folder(self):
        """
        Opens a dialog to choose where the reports are saved.
        """
        folder = filedialog.askdirectory(title="Choose Where to Save the Reports")
        if folder:
            self.save_folder_path.set(folder)
            self.log_message(f"Reports will be saved to: {folder}")

    def log_message(self, message, level="info"):
        """
        Logs a message to the GUI log box and the logging framework.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Safely update GUI from any thread
        self.root.after(0, self.log_text.insert, tk.END, formatted_message + "\n")
        self.root.after(0, self.log_text.see, tk.END)
        
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        
    def validate_inputs(self):
        """
        Validates that the selected path is a valid directory.
        """
        path = self.folder_to_analyze_path.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select a folder to analyze.")
            return False
        if not os.path.isdir(path):
            messagebox.showerror("Error", f"The selected path is not a valid directory:\n{path}")
            return False
        if not self.save_folder_path.get().strip():
            self.select_save_folder()
            if not self.save_folder_path.get().strip():
                messagebox.showerror("Error", "Please choose where to save the reports.")
                return False
        if not os.path.isdir(self.save_folder_path.get().strip()):
            messagebox.showerror("Error", f"The save folder does not exist:\n{self.save_folder_path.get().strip()}")
            return False
        return True
        
    def start_analysis(self):
        """
        Starts the folder analysis in a separate thread.
        """
        if not self.validate_inputs():
            return
            
        if self.is_running:
            messagebox.showwarning("Warning", "An analysis is already in progress.")
            return
            
        self.stop_requested = False
        self.is_running = True
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.progress_var.set(0)
        self.clear_log()
        
        # Read the Tk variables here on the main thread; the worker thread only gets plain values.
        self.run_settings = {
            'root_path': self.folder_to_analyze_path.get().strip(),
            'save_dir': self.save_folder_path.get().strip(),
            'ignore_enabled': self.ignore_extensions_var.get(),
            'ignore_list': self.ignore_extensions_list.get(),
        }
        self.analysis_thread = threading.Thread(target=self.run_analysis)
        self.analysis_thread.daemon = True
        self.analysis_thread.start()
        
    def stop_analysis(self):
        """
        Requests the analysis thread to stop.
        """
        if self.is_running:
            self.stop_requested = True
            self.log_message("Stop requested. Finishing current operations...", "warning")
            self.stop_button.config(state='disabled')

    def run_analysis(self):
        """
        The core analysis logic that runs in a background thread.
        """
        settings = self.run_settings
        root_path = settings['root_path']
        save_dir = settings['save_dir']
        base_folder_name = os.path.basename(os.path.normpath(root_path)) or "Drive"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_basename = f"{base_folder_name}_Analysis_{timestamp}"
        self.start_log_file(save_dir, report_basename)
        try:
            self.log_message(f"Starting analysis for: {root_path}")
            if settings['ignore_enabled']:
                self.log_message(f"Ignoring extensions: {settings['ignore_list']}")

            self.root.after(0, self.status_var.set, "Scanning directory...")
            self.root.after(0, self.progress_var.set, 5)

            # --- Data collection ---
            all_items = [] # List to hold dictionaries of item data
            item_count = 0
            max_depth = 0

            # --- Prepare ignored extensions ---
            ignore_enabled = settings['ignore_enabled']
            ignored_extensions = tuple()
            if ignore_enabled:
                raw_ext_list = settings['ignore_list'].split(',')
                cleaned_exts = [ext.strip().lower() for ext in raw_ext_list if ext.strip()]
                ignored_extensions = tuple([ext if ext.startswith('.') else '.' + ext for ext in cleaned_exts])

            # --- Walk the directory ---
            for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
                if self.stop_requested:
                    break

                rel_path = os.path.relpath(dirpath, root_path)
                # Normalize path and calculate depth
                depth = rel_path.count(os.sep) if rel_path != '.' else 0
                if depth > max_depth: max_depth = depth

                # Process the directory itself
                try:
                    dir_modified = datetime.fromtimestamp(os.path.getmtime(dirpath)).strftime('%Y-%m-%d %H:%M:%S')
                except (OSError, ValueError) as e:
                    dir_modified = ''
                    self.log_message(f"Cannot read folder date: {dirpath} - {e}", "warning")
                all_items.append({
                    'Name': os.path.basename(dirpath),
                    'Type': 'Folder',
                    'Depth': depth,
                    'Relative Path': rel_path if rel_path != '.' else '',
                    'Size (Bytes)': '',
                    'Date Modified': dir_modified,
                    'Full Path': dirpath
                })
                item_count += 1
                
                # Process files in the directory
                for filename in filenames:
                    if ignore_enabled and filename.lower().endswith(ignored_extensions):
                        continue
                    
                    full_path = os.path.join(dirpath, filename)
                    file_rel_path = os.path.relpath(full_path, root_path)
                    
                    try:
                        file_stat = os.stat(full_path)
                        all_items.append({
                            'Name': filename,
                            'Type': 'File',
                            'Depth': depth + 1,
                            'Relative Path': file_rel_path.replace('\\', '/'),
                            'Size (Bytes)': file_stat.st_size,
                            'Date Modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                            'Full Path': full_path
                        })
                        item_count += 1
                    except (OSError, PermissionError) as e:
                        self.log_message(f"Cannot access file: {full_path} - {e}", "warning")
                
                if item_count % 500 == 0:
                    self.root.after(0, self.status_var.set, f"Scanned {item_count:,} items...")

            if self.stop_requested:
                self.finish_analysis("Analysis stopped by user.")
                return

            self.root.after(0, self.status_var.set, "Generating reports...")
            self.root.after(0, self.progress_var.set, 80)
            
            # --- Generate reports ---
            self.generate_reports(all_items, root_path, save_dir, report_basename)
            
            self.root.after(0, self.progress_var.set, 100)
            self.finish_analysis(f"Analysis complete! Found {item_count:,} items. Max depth: {max_depth}.")

        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            self.log_message(error_msg, "error")
            self.logger.error(error_msg, exc_info=True) # Log full traceback
            self.finish_analysis(error_msg)

    def generate_reports(self, all_items, root_path, save_dir, report_basename):
        """
        Generates CSV and TXT reports from the collected data in save_dir.
        """
        # --- Generate CSV Report ---
        csv_path = os.path.join(save_dir, f"{report_basename}.csv")
        try:
            self.log_message(f"Generating CSV report at: {csv_path}")
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Type', 'Depth', 'Name', 'Relative Path', 'Size (Bytes)', 'Date Modified', 'Full Path']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_items)
            self.log_message("CSV report generated successfully.")
        except Exception as e:
            self.log_message(f"Error generating CSV report: {e}", "error")

        # --- Generate TXT Report (Tree View) ---
        txt_path = os.path.join(save_dir, f"{report_basename}.txt")
        try:
            self.log_message(f"Generating TXT tree view report at: {txt_path}")
            with open(txt_path, 'w', encoding='utf-8') as txtfile:
                txtfile.write(f"Folder Analysis for: {root_path}\n")
                txtfile.write(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                txtfile.write("-" * 50 + "\n\n")
                for line in self.build_tree_lines(all_items, root_path):
                    txtfile.write(line + "\n")
            self.log_message("TXT report generated successfully.")
        except Exception as e:
            self.log_message(f"Error generating TXT report: {e}", "error")

    @staticmethod
    def build_tree_lines(all_items, root_path):
        """
        Returns the lines of a tree view. Folders are listed before files.
        The last entry in each folder uses '└── ', the others use '├── ', and
        '│   ' continues the line of a folder that has more entries below.
        """
        children = {}
        root_name = os.path.basename(os.path.normpath(root_path)) or root_path
        for item in all_items:
            if item['Type'] == 'Folder' and item['Depth'] == 0:
                root_name = item['Name'] or root_name
                continue
            rel = os.path.relpath(item['Full Path'], root_path)
            parts = tuple(rel.split(os.sep))
            children.setdefault(parts[:-1], []).append((parts[-1], item['Type']))

        lines = [root_name]
        # Stack of (folder key, list of entries, index of next entry, line prefix)
        def sorted_entries(key):
            return sorted(children.get(key, []), key=lambda e: (e[1] != 'Folder', e[0].lower()))
        stack = [((), sorted_entries(()), 0, '')]
        while stack:
            key, entries, index, prefix = stack.pop()
            if index >= len(entries):
                continue
            name, item_type = entries[index]
            is_last = index == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{name}")
            stack.append((key, entries, index + 1, prefix))
            if item_type == 'Folder':
                child_key = key + (name,)
                stack.append((child_key, sorted_entries(child_key), 0,
                              prefix + ('    ' if is_last else '│   ')))
        return lines

    def finish_analysis(self, message):
        """
        Cleans up the GUI state after the analysis is finished or stopped.
        """
        self.is_running = False
        self.root.after(0, self.status_var.set, message)
        self.root.after(0, self.start_button.config, {'state': 'normal'})
        self.root.after(0, self.stop_button.config, {'state': 'disabled'})
        self.log_message(f"----- {message} -----")
        
        if not self.stop_requested and "complete" in message.lower():
            self.root.after(10, messagebox.showinfo, "Analysis Complete",
                "Folder analysis finished!\n\n"
                f"Detailed reports have been saved to:\n{self.run_settings['save_dir']}")

def main():
    """Main function to create and run the application."""
    root = tk.Tk()
    
    # --- Apply a modern theme ---
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use('clam')
        style.configure('Accent.TButton', font=('Arial', 10, 'bold'), foreground='white', background='#0078D7') # A nice blue
    except tk.TclError:
        print("Ttk themes not available, using default.")

    app = FolderAnalyzerTool(root)
    
    # --- Handle window closing ---
    def on_closing():
        if app.is_running:
            if messagebox.askokcancel("Quit", "Analysis is running. Are you sure you want to quit?"):
                app.stop_requested = True
                app.logger.info("Application closed by user during operation.")
                root.destroy()
        else:
            app.logger.info("Application closed.")
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
