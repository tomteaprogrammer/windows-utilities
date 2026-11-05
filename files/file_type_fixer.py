import os
import shutil
import threading
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import mimetypes
import datetime

# Initialize mimetypes
mimetypes.init()

# Add common file signatures (magic numbers)
FILE_SIGNATURES = {
    b'\xFF\xD8\xFF': '.jpg',         # JPEG
    b'\x89PNG\r\n\x1a\n': '.png',    # PNG
    b'GIF8': '.gif',                 # GIF
    b'ID3': '.mp3',                  # MP3 with ID3 tag
    b'\xFF\xFB': '.mp3',             # MP3 without ID3 tag
    b'\x00\x00\x00\x20\x66\x74\x79\x70': '.mp4',  # MP4
    b'\x00\x00\x00\x1C\x66\x74\x79\x70': '.mp4',  # MP4
    b'\x52\x49\x46\x46': '.wav',     # WAV
    b'\x25\x50\x44\x46': '.pdf',     # PDF
    b'\x50\x4B\x03\x04': '.zip',     # ZIP (or Office documents, see office_type_of_zip)
    b'\x42\x4D': '.bmp',             # BMP
    b'\x49\x49\x2A\x00': '.tif',     # TIFF
    b'\x4D\x4D\x00\x2A': '.tif',     # TIFF
    b'\x4F\x67\x67\x53': '.ogg',     # Ogg Vorbis
    b'\x66\x4C\x61\x43': '.flac',    # FLAC
}

def office_type_of_zip(file_path):
    """Word, Excel and PowerPoint files are ZIP files inside.
    Returns '.docx', '.xlsx' or '.pptx' when the ZIP holds an Office document, otherwise '.zip'."""
    try:
        with zipfile.ZipFile(file_path) as zf:
            names = zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return '.zip'
    if '[Content_Types].xml' not in names:
        return '.zip'
    for folder, extension in (('word/', '.docx'), ('xl/', '.xlsx'), ('ppt/', '.pptx')):
        if any(name.startswith(folder) for name in names):
            return extension
    return '.zip'

def unique_path(path):
    """Returns path, or 'name (1).ext', 'name (2).ext' ... if the file already exists."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base} ({counter}){ext}"):
        counter += 1
    return f"{base} ({counter}){ext}"

class FileTypeFixerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Type Fixer")
        self.root.geometry("600x450")
        
        self.source_folder = tk.StringVar()
        self.destination_folder = tk.StringVar()
        self.has_magic = self.check_magic_available()
        
        self.create_widgets()
    
    def check_magic_available(self):
        """Check if python-magic is available"""
        try:
            import magic
            return magic is not None
        except ImportError:
            return False
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Source folder selection
        ttk.Label(main_frame, text="Source Folder (with broken files):").grid(column=0, row=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, width=50, textvariable=self.source_folder).grid(column=0, row=1, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="Browse...", command=self.browse_source).grid(column=1, row=1, padx=5)
        
        # Destination folder selection
        ttk.Label(main_frame, text="Destination Folder (for fixed files):").grid(column=0, row=2, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, width=50, textvariable=self.destination_folder).grid(column=0, row=3, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="Browse...", command=self.browse_destination).grid(column=1, row=3, padx=5)
        
        # Magic library status
        magic_status = "Installed ✓" if self.has_magic else "Not Installed ✗"
        magic_color = "green" if self.has_magic else "red"
        ttk.Label(main_frame, text="Python-Magic Library:").grid(column=0, row=4, sticky=tk.W, pady=(15, 0))
        status_label = ttk.Label(main_frame, text=magic_status)
        status_label.grid(column=0, row=5, sticky=tk.W)
        status_label.configure(foreground=magic_color)
        
        if not self.has_magic:
            install_note = ttk.Label(main_frame, 
                                     text="For better file type detection, install python-magic:\n"
                                          "pip install python-magic (Linux/Mac)\n"
                                          "pip install python-magic-bin (Windows)")
            install_note.grid(column=0, row=6, sticky=tk.W, columnspan=2)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        ttk.Label(main_frame, text="Progress:").grid(column=0, row=7, sticky=tk.W, pady=(15, 0))
        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=100, mode='determinate', variable=self.progress_var)
        self.progress.grid(column=0, row=8, sticky=(tk.W, tk.E), pady=5)
        
        # Status message
        self.status_message = tk.StringVar()
        self.status_message.set("Ready")
        status = ttk.Label(main_frame, textvariable=self.status_message)
        status.grid(column=0, row=9, columnspan=2, sticky=tk.W)
        
        # Process button
        self.process_button = ttk.Button(main_frame, text="Process Files", command=self.process_files)
        self.process_button.grid(column=0, row=10, pady=20)
        
        # Configure grid
        main_frame.columnconfigure(0, weight=1)
        
    def browse_source(self):
        folder_selected = filedialog.askdirectory(title="Select Source Folder")
        if folder_selected:
            self.source_folder.set(folder_selected)
    
    def browse_destination(self):
        folder_selected = filedialog.askdirectory(title="Select Destination Folder")
        if folder_selected:
            self.destination_folder.set(folder_selected)
    
    def identify_file_type(self, file_path):
        """Identify the file type by examining its content."""
        try:
            # Read the first 8 bytes to check against known signatures
            with open(file_path, 'rb') as f:
                header = f.read(8)
                
            # Check against known signatures
            for signature, extension in FILE_SIGNATURES.items():
                if header.startswith(signature):
                    if extension == '.zip':
                        extension = office_type_of_zip(file_path)
                    return extension, f"Identified via signature as {extension}"
            
            # Try using python-magic if available
            if self.has_magic:
                import magic
                mime = magic.Magic(mime=True)
                mime_type = mime.from_file(file_path)
                extension = mimetypes.guess_extension(mime_type) or ".unknown"
                return extension, f"Identified via magic as {extension} (MIME: {mime_type})"
            
            # Fall back to mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                extension = mimetypes.guess_extension(mime_type) or ".unknown"
                return extension, f"Identified via mimetype as {extension}"
                    
            return ".unknown", "Could not identify file type"
            
        except Exception as e:
            return ".unknown", f"Error: {str(e)}"
    
    def process_files(self):
        source = self.source_folder.get()
        destination = self.destination_folder.get()
        
        if not source or not os.path.isdir(source):
            messagebox.showerror("Error", "Please select a valid source folder")
            return
            
        if not destination or not os.path.isdir(destination):
            messagebox.showerror("Error", "Please select a valid destination folder")
            return
        
        # The rest runs in a worker thread so the window stays responsive.
        self.process_button.config(state=tk.DISABLED)
        threading.Thread(target=self._process_worker, args=(source, destination), daemon=True).start()

    def _ui(self, func, *args):
        """Runs func on the main (Tk) thread."""
        self.root.after(0, func, *args)

    def _process_worker(self, source, destination):
        try:
            self._process_files_in_thread(source, destination)
        except Exception as e:
            self._ui(messagebox.showerror, "Error", f"Processing stopped:\n{e}")
            self._ui(self.status_message.set, "Stopped because of an error.")
        finally:
            self._ui(self.process_button.config, {'state': tk.NORMAL})

    def _process_files_in_thread(self, source, destination):
        # Create error folder
        error_folder = os.path.join(destination, "error_files")
        os.makedirs(error_folder, exist_ok=True)

        # Log file goes in the destination (output) folder
        log_path = unique_path(os.path.join(
            destination, f"file_fixer_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"))

        successful_files = []
        error_files = []

        # Get all files from source (skip the destination if it is inside the source)
        dest_norm = os.path.normcase(os.path.abspath(destination))
        all_files = []
        for root, dirs, files in os.walk(source):
            dirs[:] = [d for d in dirs
                       if os.path.normcase(os.path.abspath(os.path.join(root, d))) != dest_norm]
            for file in files:
                all_files.append(os.path.join(root, file))

        total_files = len(all_files)
        if total_files == 0:
            self._ui(messagebox.showinfo, "Info", "No files found in the source folder")
            return

        # Process each file
        for i, file_path in enumerate(all_files):
            self._ui(self.status_message.set, f"Processing {i+1}/{total_files}: {os.path.basename(file_path)}")
            self._ui(self.progress_var.set, (i / total_files) * 100)

            try:
                # Get just the filename without the potentially incorrect extension
                file_name = os.path.basename(file_path)
                base_name, old_extension = os.path.splitext(file_name)

                # Identify correct file type
                new_extension, reason = self.identify_file_type(file_path)

                # Create new filename
                new_filename = f"{base_name}{new_extension}"

                # Determine if successful or error
                success = new_extension != ".unknown"

                # Determine target folder, keeping the same subfolders as the source
                rel_dir = os.path.relpath(os.path.dirname(file_path), source)
                target_dir = destination if success else error_folder
                if rel_dir != os.curdir:
                    target_dir = os.path.join(target_dir, rel_dir)
                os.makedirs(target_dir, exist_ok=True)

                # Copy file with new name (never overwrite: add a number if the name is taken)
                target_path = unique_path(os.path.join(target_dir, new_filename))
                shutil.copy2(file_path, target_path)

                # Add to appropriate list
                log_entry = f"{file_path} -> {target_path} ({reason})"
                if success:
                    successful_files.append(log_entry)
                else:
                    error_files.append(log_entry)

            except Exception as e:
                error_files.append(f"{file_path} -> ERROR: {str(e)}")

        # Update progress to complete
        self._ui(self.progress_var.set, 100)

        # Write log file
        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write("=== File Type Fixer Log ===\n")
            log_file.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Source folder: {source}\n")
            log_file.write(f"Destination folder: {destination}\n")
            log_file.write(f"Error folder: {error_folder}\n")
            log_file.write(f"Total files processed: {total_files}\n")
            log_file.write(f"Successfully processed: {len(successful_files)}\n")
            log_file.write(f"Errors: {len(error_files)}\n\n")

            log_file.write("=== Successful Files ===\n")
            for entry in successful_files:
                log_file.write(f"{entry}\n")

            log_file.write("\n=== Error Files ===\n")
            for entry in error_files:
                log_file.write(f"{entry}\n")

        # Show completion message
        message = (f"Processing complete!\n\n"
                   f"Total files: {total_files}\n"
                   f"Successful: {len(successful_files)}\n"
                   f"Errors: {len(error_files)}\n\n"
                   f"Log file created at:\n{log_path}")
        self._ui(messagebox.showinfo, "Complete", message)
        self._ui(self.status_message.set, f"Completed. Successfully processed {len(successful_files)} files.")


if __name__ == "__main__":
    root = tk.Tk()
    app = FileTypeFixerApp(root)
    root.mainloop()