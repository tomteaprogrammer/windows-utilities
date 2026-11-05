import csv
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time

# --- Dependency check ---
try:
    import pyperclip
except ImportError:
    pyperclip = None

def show_missing_package_message():
    """Explains how to install the missing package (no automatic install)."""
    error_msg = (
        "The package 'pyperclip' is not installed. The program cannot continue.\n\n"
        "Open a terminal (Command Prompt or PowerShell) in this program's folder and run:\n\n"
        "pip install -r requirements.txt"
    )
    print(error_msg)
    if 'tkinter' in sys.modules:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing Package", error_msg)
        root.destroy()

class ClipboardCollectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Clipboard Collector")
        self.root.geometry("600x500")
        self.root.configure(bg='#f0f0f0')

        self.data_rows = []
        self.last_copied_text = None
        self.is_monitoring = False
        self.monitor_thread = None
        
        # Variable to control column mode
        self.single_column_mode = tk.BooleanVar(value=False)

        self.setup_gui()
        print("GUI setup complete.")

    def setup_gui(self):
        main_frame = tk.Frame(self.root, bg='#f0f0f0', padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        controls_frame = tk.Frame(main_frame, bg='#f0f0f0')
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        self.toggle_button = ttk.Button(
            controls_frame, text="Start Monitoring", command=self.toggle_monitoring, width=18
        )
        self.toggle_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.save_button = ttk.Button(
            controls_frame, text="Save to CSV", command=self.save_to_csv, width=15
        )
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_button = ttk.Button(
            controls_frame, text="Clear Data", command=self.clear_data, width=15
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))

        # Checkbox for single-column mode
        self.column_mode_check = ttk.Checkbutton(
            controls_frame, text="Use Single Column", variable=self.single_column_mode,
            command=self.toggle_column_mode
        )
        self.column_mode_check.pack(side=tk.LEFT, padx=10)


        self.warning_label = tk.Label(
            main_frame,
            text="Warning: while monitoring is on, EVERYTHING you copy is recorded, including passwords.\n"
                 "Stop monitoring before you copy a password or other private text.",
            fg="#b00020", bg='#f0f0f0', anchor='w', justify=tk.LEFT
        )
        self.warning_label.pack(fill=tk.X, pady=(0, 5))

        self.status_label = tk.Label(
            main_frame, text="Ready to start.", fg="blue", bg='#f0f0f0', anchor='w'
        )
        self.status_label.pack(fill=tk.X, pady=5)

        tree_frame = tk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, show="headings")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Set up initial columns
        self.setup_tree_columns()

    def setup_tree_columns(self):
        """Configures the Treeview columns based on the current mode."""
        if self.single_column_mode.get():
            self.tree.config(columns=("Col A",))
            self.tree.heading("Col A", text="Clipboard Content")
            self.tree.column("Col A", width=550, stretch=tk.YES)
        else:
            self.tree.config(columns=("Col A", "Col B"))
            self.tree.heading("Col A", text="Column A")
            self.tree.heading("Col B", text="Column B")
            self.tree.column("Col A", width=250, stretch=tk.YES)
            self.tree.column("Col B", width=250, stretch=tk.YES)

    def toggle_column_mode(self):
        """Handles switching between single and dual column modes."""
        if self.data_rows:
            if not messagebox.askyesno("Confirm Mode Change", 
                                     "Changing modes will clear all existing data. Continue?"):
                # Revert the checkbox state if the user cancels
                self.single_column_mode.set(not self.single_column_mode.get())
                return
        
        # Clear data, update tree columns, and refresh display
        self.data_rows = []
        self.last_copied_text = None
        self.setup_tree_columns()
        self.update_display()
        self.status_label.config(text="Mode changed. Data cleared.", fg="blue")


    def toggle_monitoring(self):
        if self.is_monitoring:
            self.is_monitoring = False
            self.toggle_button.config(text="Start Monitoring")
            self.status_label.config(text="Monitoring stopped.", fg="red")
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1)
        else:
            self.is_monitoring = True
            try:
                # Get current clipboard content to ignore it on start
                self.last_copied_text = pyperclip.paste().strip()
                print("Ignoring initial clipboard content...")
            except Exception:
                self.last_copied_text = None

            self.toggle_button.config(text="Stop Monitoring")
            self.status_label.config(text="Monitoring clipboard...", fg="green")
            self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
            self.monitor_thread.start()

    def monitor_clipboard(self):
        while self.is_monitoring:
            try:
                current_text = pyperclip.paste()
                if isinstance(current_text, str):
                    current_text = current_text.strip()
                    if current_text and current_text != self.last_copied_text:
                        self.last_copied_text = current_text
                        # Tk variables and widgets are only used on the main thread
                        self.root.after(0, self._on_new_text, current_text)
            except Exception as e:
                print(f"Could not read clipboard content: {e}")
                self.last_copied_text = None
            time.sleep(0.5)

    def _on_new_text(self, text):
        self.add_text_to_data(text)
        self.update_display()

    def add_text_to_data(self, text):
        if self.single_column_mode.get():
            # Single-column mode: always add a new row
            self.data_rows.append([text])
        else:
            # Two-column mode: fill columns A then B
            if not self.data_rows or len(self.data_rows[-1]) == 2:
                self.data_rows.append([text])
            else:
                self.data_rows[-1].append(text)

    def update_display(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        num_cols = len(self.tree["columns"])
        for i, row in enumerate(self.data_rows):
            display_row = row + [''] * (num_cols - len(row))
            self.tree.insert("", "end", iid=i, values=display_row)
        
        if self.data_rows:
            last_item_iid = len(self.data_rows) - 1
            self.tree.see(last_item_iid)

    def save_to_csv(self):
        if not self.data_rows:
            messagebox.showwarning("No Data", "There is no data to save.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Save Data As"
        )
        if not filepath:
            return
        try:
            if self.single_column_mode.get():
                columns = ["Clipboard Content"]
            else:
                columns = ["Column A", "Column B"]
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for row in self.data_rows:
                    writer.writerow(row + [''] * (len(columns) - len(row)))
            self.status_label.config(text=f"Data saved to {filepath}", fg="blue")
            messagebox.showinfo("Success", f"Successfully saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred while saving:\n{e}")
            self.status_label.config(text="Failed to save data.", fg="red")

    def clear_data(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all data?"):
            self.data_rows = []
            try:
                # Prime last_copied_text to ignore what's currently on the clipboard
                self.last_copied_text = pyperclip.paste().strip()
            except Exception:
                self.last_copied_text = None # It's okay if clipboard is not text
            self.update_display()
            self.status_label.config(text="Data cleared.", fg="blue")

    def on_closing(self):
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            print("Waiting for monitoring thread to close...")
            self.monitor_thread.join(timeout=1)
        print("Exiting application.")
        self.root.destroy()

def main():
    """Main function to run the application."""
    if pyperclip is None:
        show_missing_package_message()
        return

    try:
        print("Initializing application window...")
        app_root = tk.Tk()
        app = ClipboardCollectorApp(app_root)
        app_root.protocol("WM_DELETE_WINDOW", app.on_closing)
        print("Starting main application loop.")
        app_root.mainloop()
    except Exception as e:
        error_msg = f"A critical error occurred and the application cannot start:\n\n{e}"
        print(error_msg)
        error_root = tk.Tk()
        error_root.withdraw()
        messagebox.showerror("Application Start Error", error_msg)
        error_root.destroy()
        input("Press Enter to exit.")

if __name__ == "__main__":
    main()

