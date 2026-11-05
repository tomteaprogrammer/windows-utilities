import os
import sys
import time
import queue
import shutil
import signal
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

APP_TITLE = "Robocopy GUI - Fast Copy"

# Robocopy exit codes 0-7 are not fatal. 8+ means at least one failure.
# https://learn.microsoft.com/windows-server/administration/windows-commands/robocopy
ROBOCOPY_FATAL_EXIT_CODE = 8


class RobocopyGuiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("860x620")
        self.root.minsize(780, 560)

        self.source_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="contents")
        self.threads_var = tk.IntVar(value=32)
        self.retries_var = tk.IntVar(value=1)
        self.wait_var = tk.IntVar(value=1)
        self.copy_empty_dirs_var = tk.BooleanVar(value=True)
        self.copy_security_var = tk.BooleanVar(value=False)
        self.show_file_names_var = tk.BooleanVar(value=True)
        self.use_restartable_var = tk.BooleanVar(value=False)
        self.use_unbuffered_var = tk.BooleanVar(value=False)
        self.mirror_var = tk.BooleanVar(value=False)
        self.save_log_var = tk.BooleanVar(value=True)

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen | None = None
        self.worker_thread: threading.Thread | None = None
        self.started_at: float | None = None
        self.log_path: str | None = None

        self._build_ui()
        self._poll_output_queue()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        path_frame = ttk.LabelFrame(main, text="Folders", padding=10)
        path_frame.pack(fill="x")
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="Source").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(path_frame, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(path_frame, text="Browse", command=self._choose_source).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(path_frame, text="Destination").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(path_frame, textvariable=self.dest_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(path_frame, text="Browse", command=self._choose_dest).grid(row=1, column=2, padx=(8, 0), pady=4)

        mode_frame = ttk.LabelFrame(main, text="Copy behavior", padding=10)
        mode_frame.pack(fill="x", pady=(10, 0))
        mode_frame.columnconfigure(2, weight=1)

        ttk.Radiobutton(
            mode_frame,
            text="Copy source contents into destination",
            variable=self.mode_var,
            value="contents",
            command=self._update_command_preview,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Radiobutton(
            mode_frame,
            text="Create source folder inside destination",
            variable=self.mode_var,
            value="folder",
            command=self._update_command_preview,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)

        ttk.Checkbutton(
            mode_frame,
            text="Include empty folders (/E)",
            variable=self.copy_empty_dirs_var,
            command=self._update_command_preview,
        ).grid(row=0, column=2, sticky="w", padx=(20, 0), pady=2)
        ttk.Checkbutton(
            mode_frame,
            text="Show file names in log",
            variable=self.show_file_names_var,
            command=self._update_command_preview,
        ).grid(row=1, column=2, sticky="w", padx=(20, 0), pady=2)
        ttk.Checkbutton(
            mode_frame,
            text="Save log in the logs folder",
            variable=self.save_log_var,
            command=self._update_command_preview,
        ).grid(row=2, column=2, sticky="w", padx=(20, 0), pady=2)

        advanced = ttk.LabelFrame(main, text="Robocopy options", padding=10)
        advanced.pack(fill="x", pady=(10, 0))
        advanced.columnconfigure(7, weight=1)

        ttk.Label(advanced, text="Threads (/MT)").grid(row=0, column=0, sticky="w", pady=2)
        threads = ttk.Spinbox(advanced, from_=1, to=128, textvariable=self.threads_var, width=6, command=self._update_command_preview)
        threads.grid(row=0, column=1, sticky="w", padx=(6, 18), pady=2)
        threads.bind("<KeyRelease>", lambda _e: self._update_command_preview())

        ttk.Label(advanced, text="Retries (/R)").grid(row=0, column=2, sticky="w", pady=2)
        retries = ttk.Spinbox(advanced, from_=0, to=20, textvariable=self.retries_var, width=6, command=self._update_command_preview)
        retries.grid(row=0, column=3, sticky="w", padx=(6, 18), pady=2)
        retries.bind("<KeyRelease>", lambda _e: self._update_command_preview())

        ttk.Label(advanced, text="Wait seconds (/W)").grid(row=0, column=4, sticky="w", pady=2)
        wait = ttk.Spinbox(advanced, from_=0, to=60, textvariable=self.wait_var, width=6, command=self._update_command_preview)
        wait.grid(row=0, column=5, sticky="w", padx=(6, 18), pady=2)
        wait.bind("<KeyRelease>", lambda _e: self._update_command_preview())

        ttk.Checkbutton(
            advanced,
            text="Restartable mode /Z (safer, slower)",
            variable=self.use_restartable_var,
            command=self._update_command_preview,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Checkbutton(
            advanced,
            text="Unbuffered /J (large files)",
            variable=self.use_unbuffered_var,
            command=self._update_command_preview,
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=2)
        ttk.Checkbutton(
            advanced,
            text="Copy permissions /COPY:DATS",
            variable=self.copy_security_var,
            command=self._update_command_preview,
        ).grid(row=1, column=4, columnspan=2, sticky="w", pady=2)
        ttk.Checkbutton(
            advanced,
            text="MIRROR destination /MIR (deletes extras)",
            variable=self.mirror_var,
            command=self._mirror_warning,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=2)
        ttk.Label(
            advanced,
            text="Warning: /MIR deletes files in the destination that are not in the source.",
            foreground="#b00020",
        ).grid(row=3, column=0, columnspan=8, sticky="w", pady=(0, 2))

        preview_frame = ttk.LabelFrame(main, text="Command preview", padding=8)
        preview_frame.pack(fill="x", pady=(10, 0))
        self.preview = tk.Text(preview_frame, height=2, wrap="word")
        self.preview.pack(fill="x")
        self.preview.configure(state="disabled")

        status_frame = ttk.Frame(main)
        status_frame.pack(fill="x", pady=(10, 0))
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(side="right")

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(10, 0))
        self.start_button = ttk.Button(buttons, text="Start robocopy", command=self.start_copy)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel_copy, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Clear output", command=self._clear_output).pack(side="right")

        output_frame = ttk.LabelFrame(main, text="Live robocopy output", padding=8)
        output_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.output = ScrolledText(output_frame, wrap="word", height=14)
        self.output.pack(fill="both", expand=True)

        for var in (
            self.source_var,
            self.dest_var,
            self.mode_var,
            self.threads_var,
            self.retries_var,
            self.wait_var,
            self.copy_empty_dirs_var,
            self.copy_security_var,
            self.show_file_names_var,
            self.use_restartable_var,
            self.use_unbuffered_var,
            self.mirror_var,
            self.save_log_var,
        ):
            try:
                var.trace_add("write", lambda *_args: self._update_command_preview())
            except Exception:
                pass

        self._update_command_preview()

    def _choose_source(self):
        path = filedialog.askdirectory(title="Choose source folder")
        if path:
            self.source_var.set(path)

    def _choose_dest(self):
        path = filedialog.askdirectory(title="Choose destination folder")
        if path:
            self.dest_var.set(path)

    def _clear_output(self):
        self.output.delete("1.0", "end")

    def _safe_int(self, var: tk.IntVar, default: int, low: int, high: int) -> int:
        try:
            value = int(var.get())
        except Exception:
            value = default
        return max(low, min(high, value))

    def _effective_paths(self) -> tuple[str, str]:
        # An empty box stays empty. (abspath("") would silently become the current folder.)
        source_raw = self.source_var.get().strip()
        dest_raw = self.dest_var.get().strip()
        source = os.path.abspath(os.path.normpath(source_raw)) if source_raw else ""
        dest_base = os.path.abspath(os.path.normpath(dest_raw)) if dest_raw else ""
        if not dest_base:
            dest = ""
        elif self.mode_var.get() == "folder" and source:
            dest = os.path.join(dest_base, os.path.basename(source.rstrip("\\/")))
        else:
            dest = dest_base
        return source, dest

    def _build_robocopy_command(self) -> list[str]:
        source, dest = self._effective_paths()
        threads = self._safe_int(self.threads_var, 32, 1, 128)
        retries = self._safe_int(self.retries_var, 1, 0, 20)
        wait = self._safe_int(self.wait_var, 1, 0, 60)

        command = ["robocopy", source, dest]

        if self.mirror_var.get():
            command.append("/MIR")
        else:
            command.append("/E" if self.copy_empty_dirs_var.get() else "/S")

        # Good default copy metadata. D=data, A=attributes, T=timestamps. S=security if requested.
        command.append("/COPY:DATS" if self.copy_security_var.get() else "/COPY:DAT")
        command.append("/DCOPY:DAT")

        # Avoid getting stuck on junction/symlink loops.
        command.append("/XJ")

        command.extend([f"/MT:{threads}", f"/R:{retries}", f"/W:{wait}"])

        # Avoid slow progress percentage spam; keep overall transfer quick.
        command.append("/NP")

        if not self.show_file_names_var.get():
            command.extend(["/NFL", "/NDL"])

        if self.use_restartable_var.get():
            command.append("/Z")
        if self.use_unbuffered_var.get():
            command.append("/J")

        if self.save_log_var.get():
            self.log_path = self._make_log_path()
            command.append(f"/LOG+:{self.log_path}")
            # /TEE also sends the output to the console, so the live output box keeps working.
            command.append("/TEE")
        else:
            self.log_path = None

        return command

    def _make_log_path(self) -> str:
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = os.getcwd()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(base_dir, "logs", f"robocopy_{timestamp}.log")

    def _quote_for_preview(self, arg: str) -> str:
        if not arg:
            return '""'
        if any(ch.isspace() for ch in arg) or any(ch in arg for ch in '&()[]{}^=;!\'+,`~'):
            return '"' + arg.replace('"', '\\"') + '"'
        return arg

    def _update_command_preview(self):
        try:
            if not self.source_var.get().strip() or not self.dest_var.get().strip():
                raise ValueError("missing folder")
            command = self._build_robocopy_command()
            preview = " ".join(self._quote_for_preview(arg) for arg in command)
        except Exception:
            preview = "Choose source and destination folders."
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", preview)
        self.preview.configure(state="disabled")

    def _mirror_warning(self):
        if self.mirror_var.get():
            ok = messagebox.askyesno(
                "Mirror warning",
                "Mirror mode uses /MIR and deletes files/folders from the destination when they are not in the source.\n\nUse it only for backups where the destination should exactly match the source. Keep mirror mode on?",
            )
            if not ok:
                self.mirror_var.set(False)
        self._update_command_preview()

    def _validate_before_start(self) -> bool:
        if sys.platform != "win32":
            messagebox.showerror("Windows required", "Robocopy is a Windows command. Run this script on Windows.")
            return False

        if not shutil.which("robocopy"):
            messagebox.showerror("Robocopy not found", "Windows robocopy.exe was not found in PATH.")
            return False

        if not self.source_var.get().strip() or not self.dest_var.get().strip():
            messagebox.showwarning("Missing folders", "Choose both a source folder and a destination folder.")
            return False

        source, dest = self._effective_paths()
        if not source or not dest:
            messagebox.showwarning("Missing folders", "Choose both a source folder and a destination folder.")
            return False

        if not os.path.isdir(source):
            messagebox.showerror("Source not found", "The source folder does not exist.")
            return False

        source_norm = os.path.normcase(os.path.abspath(source))
        dest_norm = os.path.normcase(os.path.abspath(dest))
        if source_norm == dest_norm:
            messagebox.showerror("Same folder", "Source and destination cannot be the same folder.")
            return False

        # Prevent recursive copies such as C:\Photos -> C:\Photos\Backup.
        try:
            common = os.path.commonpath([source_norm, dest_norm])
            if common == source_norm:
                messagebox.showerror(
                    "Destination inside source",
                    "The destination is inside the source folder. Choose a destination outside the source to avoid recursive copying.",
                )
                return False
        except ValueError:
            # Different drives can raise ValueError; that is fine.
            pass

        if self.mirror_var.get():
            ok = messagebox.askyesno(
                "Confirm mirror copy",
                "Mirror mode is on. Robocopy will delete destination files/folders that are not in the source.\n\nStart mirror copy?",
            )
            if not ok:
                return False

        return True

    def start_copy(self):
        if self.process is not None:
            return
        if not self._validate_before_start():
            return

        self._clear_output()
        command = self._build_robocopy_command()
        source, dest = self._effective_paths()
        os.makedirs(dest, exist_ok=True)
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

        self.started_at = time.time()
        self.status_label.configure(text="Copying now")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress.start(12)

        self._append_output("Starting robocopy. It will copy immediately without pre-counting every file.\n")
        self._append_output("Command:\n" + " ".join(self._quote_for_preview(a) for a in command) + "\n\n")

        self.worker_thread = threading.Thread(target=self._run_robocopy, args=(command,), daemon=True)
        self.worker_thread.start()

    def _run_robocopy(self, command: list[str]):
        exit_code = None
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="oem",  # robocopy writes in the console (OEM) code page
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )

            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.output_queue.put(line)
            exit_code = self.process.wait()

        except FileNotFoundError:
            self.output_queue.put("ERROR: robocopy.exe was not found.\n")
            exit_code = ROBOCOPY_FATAL_EXIT_CODE
        except Exception as exc:
            self.output_queue.put(f"ERROR: {exc}\n")
            exit_code = ROBOCOPY_FATAL_EXIT_CODE
        finally:
            self.output_queue.put(("__DONE__", exit_code))

    def cancel_copy(self):
        if self.process is None:
            return
        self.status_label.configure(text="Canceling")
        self.cancel_button.configure(state="disabled")
        self._append_output("\nCancel requested. Stopping robocopy...\n")
        try:
            if sys.platform == "win32":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
                # Give robocopy a moment to exit cleanly.
                self.root.after(2000, self._kill_if_still_running)
            else:
                self.process.terminate()
        except Exception:
            self._kill_if_still_running()

    def _kill_if_still_running(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.kill()
            except Exception:
                pass

    def _poll_output_queue(self):
        try:
            while True:
                item = self.output_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "__DONE__":
                    self._on_done(item[1])
                else:
                    self._append_output(str(item))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_output_queue)

    def _append_output(self, text: str):
        self.output.insert("end", text)
        self.output.see("end")

    def _on_done(self, exit_code: int | None):
        elapsed = int(time.time() - self.started_at) if self.started_at else 0
        self.progress.stop()
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.process = None

        code = exit_code if exit_code is not None else ROBOCOPY_FATAL_EXIT_CODE
        log_note = f"\nLog file: {self.log_path}\n" if self.log_path else ""
        self._append_output(f"\nRobocopy finished with exit code {code} after {elapsed} seconds.{log_note}")

        if code >= ROBOCOPY_FATAL_EXIT_CODE:
            self.status_label.configure(text=f"Failed: exit code {code}")
            messagebox.showerror(
                "Copy failed",
                f"Robocopy reported a failure. Exit code: {code}\n\nCheck the live output and log file for details.",
            )
        else:
            self.status_label.configure(text=f"Done: exit code {code}")
            messagebox.showinfo(
                "Copy finished",
                f"Robocopy completed. Exit code: {code}\n\nCodes 0-7 are success/warning codes, not fatal errors.",
            )


def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    RobocopyGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
