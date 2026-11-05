#!/usr/bin/env python3
"""Find and unblock documents and Microsoft Office files on Windows.

Windows tags files that came from the internet with a hidden
``Zone.Identifier`` alternate data stream (ADS).  Explorer shows this as the
"This file came from another computer and might be blocked" security notice
with an *Unblock* checkbox.  Removing the stream is exactly what that checkbox
does.

The tool works in three stages, and never skips ahead:

    1. Scan   - count how many files are blocked and where they live.
    2. Dry run - check every file for problems (locked, read-only, no rights)
                 without changing anything.
    3. Unblock - only unlocked after a dry run has been done.

Run it with no arguments for the window (browse the list, jump to folders,
preview files), or with ``--cli`` for a plain console run.

    python unblock_documents.py
    python unblock_documents.py --cli --path "C:\\Users\\me\\Downloads"
    python unblock_documents.py --cli --path D:\\Docs --dry-run
"""

from __future__ import annotations

import argparse
import csv
import os
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

APP_NAME = "Unblock Documents"
ZONE_STREAM = "Zone.Identifier"

IS_WINDOWS = os.name == "nt"

# Test hook: emulate alternate data streams with sidecar files so the scan /
# dry-run / unblock pipeline can be exercised on a non-Windows box.
FAKE_ADS = os.environ.get("UNBLOCK_FAKE_ADS") == "1"
FAKE_SUFFIX = ".__Zone.Identifier__"

# Word, Excel, PowerPoint, Access, Publisher, Visio, Project, OneNote.
OFFICE_EXTS = {
    ".doc", ".docx", ".docm", ".dot", ".dotx", ".dotm", ".docb",
    ".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".xltm", ".xlam",
    ".ppt", ".pptx", ".pptm", ".pps", ".ppsx", ".ppsm", ".pot", ".potx",
    ".potm", ".ppam", ".sldx",
    ".mdb", ".accdb", ".accde", ".accdr",
    ".pub", ".vsd", ".vsdx", ".vsdm", ".vssx", ".vstx",
    ".mpp", ".mpt", ".one", ".onepkg", ".onetoc2",
}

# Everything else people mean by "documents".
DOC_EXTS = {
    ".pdf", ".rtf", ".txt", ".csv", ".tsv", ".md", ".xml", ".xps", ".oxps",
    ".odt", ".ods", ".odp", ".odg", ".odf", ".epub", ".mobi", ".djvu",
    ".wpd", ".wps", ".pages", ".numbers", ".key", ".tex", ".msg", ".eml",
}

# Macro-enabled Office formats. Removing the mark from these lets their macros
# run, so they are skipped unless the user turns them on (--include-macros or
# the "Include macro-enabled files" box). This applies to every preset, "all" too.
MACRO_EXTS = {
    ".docm", ".dotm", ".xlsm", ".xltm", ".xlsb", ".xlam",
    ".pptm", ".ppsm", ".potm", ".ppam", ".vsdm",
}

ALL_FILES_WARNING = ("'Every file' also covers programs and scripts (.exe, .msi, .bat, .js, ...). "
                     "Unblocking them removes the Windows SmartScreen warning. "
                     "Macro-enabled Office files stay skipped unless you include them.")

PRESETS = {
    "office": ("Microsoft Office files only", OFFICE_EXTS),
    "documents": ("Office files + documents (PDF, text, OpenDocument...)",
                  OFFICE_EXTS | DOC_EXTS),
    "all": ("Every file, whatever the extension", None),
}

ZONE_NAMES = {
    0: "Local machine",
    1: "Local intranet",
    2: "Trusted site",
    3: "Internet",
    4: "Restricted site",
}

# Explorer only offers the Unblock checkbox for these zones.
BLOCKING_ZONES = (3, 4)

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_ERROR = "error"


# --------------------------------------------------------------------------
# Zone.Identifier plumbing
# --------------------------------------------------------------------------

def _long_path(path: str) -> str:
    """Prefix a path so Windows accepts it past the 260 character limit."""
    if not IS_WINDOWS or len(path) < 240 or path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def stream_path(path: str) -> str:
    """Return the path of the file's Zone.Identifier stream."""
    if FAKE_ADS:
        return path + FAKE_SUFFIX
    return _long_path(path) + ":" + ZONE_STREAM


def read_zone(path: str) -> dict | None:
    """Read the Zone.Identifier stream.

    Returns a dict of its key/value pairs, or None when the file carries no
    such stream (i.e. it is not blocked).  Raises OSError if the stream exists
    but cannot be read.
    """
    try:
        with open(stream_path(path), "rb") as handle:
            raw = handle.read(64 * 1024)
    except FileNotFoundError:
        return None
    except NotADirectoryError:
        # Some filesystems report a missing stream this way.
        return None
    except OSError as exc:
        if getattr(exc, "winerror", None) in (2, 3, 123, 161):
            return None
        raise

    info: dict[str, str] = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        key, sep, value = line.partition("=")
        if sep:
            info[key.strip()] = value.strip()
    return info


def zone_id_of(info: dict | None) -> int | None:
    if not info:
        return None
    try:
        return int(info.get("ZoneId", "").strip())
    except (TypeError, ValueError):
        return None


def is_readonly(path: str) -> bool:
    try:
        return not os.access(path, os.W_OK)
    except OSError:
        return False


def clear_readonly(path: str) -> None:
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IWRITE | stat.S_IWUSR)


def set_readonly(path: str) -> None:
    mode = os.stat(path).st_mode
    os.chmod(path, mode & ~(stat.S_IWRITE | stat.S_IWUSR))


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------

@dataclass
class FileEntry:
    path: str
    name: str
    folder: str
    size: int
    modified: float
    zone_id: int | None
    host_url: str = ""
    referrer_url: str = ""
    selected: bool = True
    check_status: str = ""
    check_message: str = ""
    result: str = ""

    @property
    def zone_name(self) -> str:
        if self.zone_id is None:
            return "Unknown"
        return ZONE_NAMES.get(self.zone_id, f"Zone {self.zone_id}")

    @property
    def is_blocked(self) -> bool:
        """True when Explorer would show the Unblock checkbox for this file."""
        return self.zone_id is None or self.zone_id in BLOCKING_ZONES

    @property
    def source(self) -> str:
        return self.host_url or self.referrer_url or ""


@dataclass
class ScanResult:
    entries: list[FileEntry] = field(default_factory=list)
    scanned: int = 0
    errors: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def blocked(self) -> list[FileEntry]:
        return [e for e in self.entries if e.is_blocked]

    @property
    def other_zone(self) -> list[FileEntry]:
        return [e for e in self.entries if not e.is_blocked]

    def folders(self, entries: list[FileEntry] | None = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in (self.entries if entries is None else entries):
            counts[entry.folder] = counts.get(entry.folder, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())))


def iter_files(root: str, recurse: bool, errors: list[str]):
    """Yield (path, DirEntry) pairs, recording folders we cannot read."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for item in it:
                    try:
                        if item.is_dir(follow_symlinks=False):
                            if recurse:
                                stack.append(item.path)
                            continue
                        if not item.is_file(follow_symlinks=False):
                            continue
                    except OSError as exc:
                        errors.append(f"{item.path}: {exc.strerror or exc}")
                        continue
                    yield item
        except PermissionError:
            errors.append(f"{current}: access denied (folder skipped)")
        except OSError as exc:
            errors.append(f"{current}: {exc.strerror or exc}")


def scan(root: str, recurse: bool = True, extensions: set[str] | None = None,
         progress=None, cancel: threading.Event | None = None,
         include_macros: bool = False) -> ScanResult:
    """Walk *root* and collect every file carrying a Zone.Identifier stream.

    Macro-enabled Office files (MACRO_EXTS) are skipped unless include_macros is True.
    """
    result = ScanResult()
    root = os.path.abspath(root)
    last_report = 0.0

    for item in iter_files(root, recurse, result.errors):
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            break

        if FAKE_ADS and item.name.endswith(FAKE_SUFFIX):
            continue

        ext = os.path.splitext(item.name)[1].lower()
        if extensions is not None and ext not in extensions:
            continue
        if not include_macros and ext in MACRO_EXTS:
            continue

        result.scanned += 1
        path = item.path
        try:
            info = read_zone(path)
        except OSError as exc:
            result.errors.append(f"{path}: cannot read zone info ({exc.strerror or exc})")
            continue

        if info is not None:
            try:
                st = item.stat()
                size, modified = st.st_size, st.st_mtime
            except OSError:
                size, modified = 0, 0.0
            result.entries.append(FileEntry(
                path=path,
                name=item.name,
                folder=os.path.dirname(path),
                size=size,
                modified=modified,
                zone_id=zone_id_of(info),
                host_url=info.get("HostUrl", ""),
                referrer_url=info.get("ReferrerUrl", ""),
            ))

        now = time.monotonic()
        if progress is not None and now - last_report > 0.15:
            last_report = now
            progress(result.scanned, len(result.entries))

    if progress is not None:
        progress(result.scanned, len(result.entries))
    return result


# --------------------------------------------------------------------------
# Dry run and unblock
# --------------------------------------------------------------------------

# Attributes of OneDrive / Google Drive "online-only" placeholder files.
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
CLOUD_ONLY_MASK = (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN
                   | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)


def is_cloud_only(path: str) -> bool:
    """True for an online-only cloud file. Reads attributes only; the file is not opened."""
    try:
        attrs = getattr(os.stat(_long_path(path)), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & CLOUD_ONLY_MASK)


def check_entry(entry: FileEntry) -> tuple[str, str]:
    """Look for anything that would stop this file being unblocked."""
    path = entry.path
    long_path = _long_path(path)
    if not os.path.exists(long_path):
        return STATUS_ERROR, "File no longer exists"

    try:
        info = read_zone(path)
    except OSError as exc:
        return STATUS_ERROR, f"Cannot read zone info: {exc.strerror or exc}"
    if info is None:
        return STATUS_WARN, "Already unblocked since the scan - nothing to do"

    notes: list[str] = []
    if is_readonly(long_path):
        notes.append("read-only (flag will be cleared, then restored)")

    if is_cloud_only(path):
        # Opening an online-only file would make OneDrive/Drive download it,
        # so the "is it open in another program" test is skipped for these.
        notes.append("online-only cloud file (not opened, so not downloaded; lock check skipped)")
    else:
        try:
            with open(long_path, "r+b"):
                pass
        except PermissionError:
            if not is_readonly(long_path):
                return STATUS_ERROR, "No write permission - run as the file's owner or as administrator"
        except OSError as exc:
            winerr = getattr(exc, "winerror", None)
            if winerr in (32, 33):
                return STATUS_ERROR, "File is open in another program - close it first"
            return STATUS_ERROR, f"Cannot open file: {exc.strerror or exc}"

    if IS_WINDOWS and len(path) > 259:
        notes.append("very long path (handled with the extended-length prefix)")

    if notes:
        return STATUS_WARN, "; ".join(notes)
    return STATUS_OK, "Ready to unblock"


def dry_run(entries: list[FileEntry], progress=None,
            cancel: threading.Event | None = None) -> dict[str, int]:
    counts = {STATUS_OK: 0, STATUS_WARN: 0, STATUS_ERROR: 0}
    for index, entry in enumerate(entries, 1):
        if cancel is not None and cancel.is_set():
            break
        status, message = check_entry(entry)
        entry.check_status, entry.check_message = status, message
        counts[status] += 1
        if progress is not None:
            progress(index, len(entries), entry)
    return counts


def unblock_entry(entry: FileEntry) -> tuple[bool, str]:
    """Remove the Zone.Identifier stream, restoring the read-only flag."""
    path = entry.path
    long_path = _long_path(path)
    if not os.path.exists(long_path):
        return False, "File no longer exists"

    was_readonly = is_readonly(long_path)
    target = stream_path(path)

    def _remove() -> None:
        os.remove(target)

    try:
        try:
            _remove()
        except PermissionError:
            if not was_readonly:
                raise
            clear_readonly(long_path)
            _remove()
    except FileNotFoundError:
        return True, "Was not blocked any more"
    except PermissionError:
        return False, "Access denied - close the file or run as administrator"
    except OSError as exc:
        if getattr(exc, "winerror", None) in (32, 33):
            return False, "File is open in another program"
        return False, f"{exc.strerror or exc}"
    finally:
        if was_readonly and not is_readonly(long_path) and os.path.exists(long_path):
            try:
                set_readonly(long_path)
            except OSError:
                pass

    return True, "Unblocked"


def unblock_all(entries: list[FileEntry], progress=None,
                cancel: threading.Event | None = None) -> tuple[int, int]:
    done = failed = 0
    for index, entry in enumerate(entries, 1):
        if cancel is not None and cancel.is_set():
            break
        ok, message = unblock_entry(entry)
        entry.result = message
        if ok:
            done += 1
        else:
            failed += 1
        if progress is not None:
            progress(index, len(entries), entry, ok)
    return done, failed


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:,.0f} {unit}" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{size} B"


def human_time(timestamp: float) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def export_csv(entries: list[FileEntry], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Name", "Folder", "Zone", "ZoneId", "Source",
                         "Size", "Modified", "Check", "Check detail", "Result"])
        for entry in entries:
            writer.writerow([
                entry.name, entry.folder, entry.zone_name,
                "" if entry.zone_id is None else entry.zone_id,
                entry.source, entry.size, human_time(entry.modified),
                entry.check_status, entry.check_message, entry.result,
            ])


def open_file(path: str) -> str:
    """Preview a file with whatever program is registered for it."""
    try:
        if IS_WINDOWS:
            os.startfile(path)  # noqa: S606 - intended shell association
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as exc:
        return f"Could not open {path}: {exc}"
    return ""


def open_with_dialog(path: str) -> str:
    """Windows 'Open with...' picker, so you can choose the program."""
    if not IS_WINDOWS:
        return open_file(path)
    try:
        subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", path])
    except OSError as exc:
        return f"Could not show the Open with dialog: {exc}"
    return ""


def reveal_in_explorer(path: str) -> str:
    """Open the containing folder with the file highlighted."""
    try:
        if IS_WINDOWS:
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except OSError as exc:
        return f"Could not open the folder: {exc}"
    return ""


def open_folder(path: str) -> str:
    try:
        if IS_WINDOWS:
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as exc:
        return f"Could not open the folder: {exc}"
    return ""


def warn_if_not_windows(printer=print) -> None:
    if not IS_WINDOWS and not FAKE_ADS:
        printer("Note: Zone.Identifier streams only exist on Windows/NTFS, "
                "so nothing will be found on this system.")


# --------------------------------------------------------------------------
# Console mode
# --------------------------------------------------------------------------

def run_cli(args) -> int:
    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"Not a folder: {root}")
        return 2

    label, extensions = PRESETS[args.types]
    warn_if_not_windows()
    print(f"Folder     : {root}")
    print(f"Subfolders : {'yes' if not args.no_recurse else 'no'}")
    print(f"File types : {label}")
    print(f"Macro files: {'INCLUDED' if args.include_macros else 'skipped (use --include-macros)'}")
    if args.types == "all":
        print(f"\nWARNING: {ALL_FILES_WARNING}")
    if args.include_macros:
        print("\nWARNING: macro-enabled files are included. Unblocking them lets their macros run.")
    print("\nScanning...")

    def progress(scanned: int, found: int) -> None:
        line = f"  {scanned:,} files checked, {found:,} tagged"
        print("\r" + line.ljust(64), end="", flush=True)

    result = scan(root, recurse=not args.no_recurse, extensions=extensions,
                  progress=progress, include_macros=args.include_macros)
    print()

    # ---- stage 1: what is blocked, and where ----------------------------
    targets = result.blocked if not args.include_all_zones else list(result.entries)
    folders = result.folders(targets)

    print("\n" + "=" * 70)
    print(f"Files checked            : {result.scanned:,}")
    print(f"BLOCKED (Internet zone)  : {len(result.blocked):,}")
    if result.other_zone:
        print(f"Tagged, other zones      : {len(result.other_zone):,}"
              f"{'  (included)' if args.include_all_zones else '  (skipped, use --include-all-zones)'}")
    print(f"Folders involved         : {len(folders):,}")
    print("=" * 70)

    if result.errors:
        print(f"\n{len(result.errors)} folder/file(s) could not be read:")
        for line in result.errors[:10]:
            print(f"  - {line}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more")

    if not targets:
        print("\nNothing to unblock.")
        return 0

    print("\nBlocked files per folder:")
    for folder, count in folders.items():
        print(f"  {count:>6,}  {folder}")

    if args.list:
        print("\nFiles:")
        for entry in targets:
            print(f"  [{entry.zone_name}] {entry.path}")

    # ---- stage 2: dry run ------------------------------------------------
    print("\nDry run - checking every file, nothing is being changed...")
    counts = dry_run(targets)
    print(f"  ready      : {counts[STATUS_OK]:,}")
    print(f"  warnings   : {counts[STATUS_WARN]:,}")
    print(f"  problems   : {counts[STATUS_ERROR]:,}")

    for status, header in ((STATUS_WARN, "Warnings"), (STATUS_ERROR, "Problems")):
        rows = [e for e in targets if e.check_status == status]
        if rows:
            print(f"\n{header}:")
            for entry in rows[:40]:
                print(f"  {entry.path}\n      {entry.check_message}")
            if len(rows) > 40:
                print(f"  ... and {len(rows) - 40} more")

    if args.csv:
        export_csv(targets, args.csv)
        print(f"\nReport written to {args.csv}")

    if args.dry_run:
        print("\nDry run only (--dry-run), no files were changed.")
        return 0

    # ---- stage 3: the real thing ----------------------------------------
    runnable = [e for e in targets if e.check_status != STATUS_ERROR]
    if not runnable:
        print("\nEvery file has a problem - fix those first, then run again.")
        return 1

    if not args.yes:
        print(f"\nAbout to unblock {len(runnable):,} file(s).")
        try:
            answer = input("Type YES to continue: ").strip()
        except EOFError:
            answer = ""
        if answer != "YES":
            print("Cancelled - nothing was changed.")
            return 0

    print("\nUnblocking...")
    done, failed = unblock_all(runnable)
    print(f"\nUnblocked : {done:,}")
    print(f"Failed    : {failed:,}")
    for entry in runnable:
        if entry.result and entry.result not in ("Unblocked", "Was not blocked any more"):
            print(f"  {entry.path}\n      {entry.result}")

    if args.csv:
        export_csv(targets, args.csv)
    return 0 if failed == 0 else 1


# --------------------------------------------------------------------------
# Window mode
# --------------------------------------------------------------------------

def run_gui(args) -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("Tkinter is not available in this Python install, "
              "so the window cannot open. Use --cli instead.")
        return 2

    CHECKED, UNCHECKED = "\u2611", "\u2610"

    class App:
        def __init__(self, root_window, start_path: str, types: str, recurse: bool,
                     include_macros: bool = False):
            self.win = root_window
            self.win.title(APP_NAME)
            self.win.geometry("1180x760")
            self.win.minsize(900, 560)

            self.result: ScanResult | None = None
            self.entries: list[FileEntry] = []
            self.visible: list[FileEntry] = []
            self.by_iid: dict[str, FileEntry] = {}
            self.cancel = threading.Event()
            self.worker: threading.Thread | None = None
            self.dry_run_done = False
            self.dry_run_paths: set[str] = set()  # files checked by the last dry run
            self.is_busy = False
            self.sort_column = "folder"
            self.sort_reverse = False
            self._last_tick = 0.0

            self.var_path = tk.StringVar(value=start_path)
            self.var_recurse = tk.BooleanVar(value=recurse)
            self.var_types = tk.StringVar(value=PRESETS[types][0])
            self.var_group = tk.BooleanVar(value=True)
            self.var_all_zones = tk.BooleanVar(value=False)
            self.var_macros = tk.BooleanVar(value=include_macros)
            self.var_filter = tk.StringVar()
            self.var_summary = tk.StringVar(value="Pick a folder and press Scan.")
            self.var_status = tk.StringVar(value="Ready.")

            self._build()
            self.var_filter.trace_add("write", lambda *_: self.refresh_tree())
            warn_if_not_windows(self.log)

        # -- layout --------------------------------------------------------
        def _build(self):
            pad = dict(padx=6, pady=4)

            top = ttk.LabelFrame(self.win, text="1. Where to look")
            top.pack(fill="x", **pad)

            row = ttk.Frame(top)
            row.pack(fill="x", padx=6, pady=(6, 2))
            ttk.Label(row, text="Folder:").pack(side="left")
            entry = ttk.Entry(row, textvariable=self.var_path)
            entry.pack(side="left", fill="x", expand=True, padx=6)
            entry.bind("<Return>", lambda _e: self.start_scan())
            ttk.Button(row, text="Browse...", command=self.browse).pack(side="left")

            row2 = ttk.Frame(top)
            row2.pack(fill="x", padx=6, pady=(2, 6))
            ttk.Checkbutton(row2, text="Include subfolders",
                            variable=self.var_recurse).pack(side="left")
            ttk.Label(row2, text="   File types:").pack(side="left")
            combo = ttk.Combobox(row2, textvariable=self.var_types, width=48,
                                 state="readonly",
                                 values=[label for label, _ in PRESETS.values()])
            combo.pack(side="left", padx=6)
            combo.bind("<<ComboboxSelected>>", self.on_types_changed)
            ttk.Checkbutton(row2, text="Show other zones too (intranet/trusted)",
                            variable=self.var_all_zones,
                            command=self.refresh_tree).pack(side="left", padx=6)
            self.btn_scan = ttk.Button(row2, text="Scan", command=self.start_scan)
            self.btn_scan.pack(side="right")
            self.btn_stop = ttk.Button(row2, text="Stop", command=self.stop,
                                       state="disabled")
            self.btn_stop.pack(side="right", padx=4)

            row3 = ttk.Frame(top)
            row3.pack(fill="x", padx=6, pady=(0, 6))
            ttk.Checkbutton(row3, text="Include macro-enabled files (.docm, .xlsm, .pptm, ...)",
                            variable=self.var_macros,
                            command=self.on_macros_toggled).pack(side="left")
            ttk.Label(row3, text="   Off by default: unblocking a macro file lets its macros run.",
                      foreground="#b00000").pack(side="left")

            summary = ttk.Frame(self.win)
            summary.pack(fill="x", padx=6)
            ttk.Label(summary, textvariable=self.var_summary,
                      font=("Segoe UI", 11, "bold")).pack(side="left")

            mid = ttk.LabelFrame(self.win, text="2. Blocked files")
            mid.pack(fill="both", expand=True, **pad)

            bar = ttk.Frame(mid)
            bar.pack(fill="x", padx=6, pady=4)
            ttk.Label(bar, text="Filter:").pack(side="left")
            ttk.Entry(bar, textvariable=self.var_filter, width=32).pack(side="left", padx=4)
            ttk.Checkbutton(bar, text="Group by folder", variable=self.var_group,
                            command=self.refresh_tree).pack(side="left", padx=8)
            ttk.Button(bar, text="Select all", command=lambda: self.select_all(True)).pack(side="left")
            ttk.Button(bar, text="Select none", command=lambda: self.select_all(False)).pack(side="left", padx=4)
            ttk.Label(bar, text="   Double-click a file to preview it "
                               "- right-click for more").pack(side="left")

            holder = ttk.Frame(mid)
            holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))

            columns = ("sel", "name", "folder", "zone", "source", "size", "modified", "check")
            self.tree = ttk.Treeview(holder, columns=columns, show="tree headings",
                                     selectmode="extended")
            headings = {
                "sel": ("", 34),
                "name": ("File", 260),
                "folder": ("Folder", 300),
                "zone": ("Zone", 110),
                "source": ("Came from", 220),
                "size": ("Size", 90),
                "modified": ("Modified", 130),
                "check": ("Dry run", 220),
            }
            self.tree.column("#0", width=26, stretch=False)
            for key, (title, width) in headings.items():
                self.tree.heading(key, text=title,
                                  command=(lambda k=key: self.sort_by(k)) if key != "sel" else "")
                anchor = "e" if key == "size" else "w"
                self.tree.column(key, width=width, anchor=anchor,
                                 stretch=key in ("name", "folder", "source"))

            yscroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
            xscroll = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
            self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            self.tree.grid(row=0, column=0, sticky="nsew")
            yscroll.grid(row=0, column=1, sticky="ns")
            xscroll.grid(row=1, column=0, sticky="ew")
            holder.rowconfigure(0, weight=1)
            holder.columnconfigure(0, weight=1)

            self.tree.tag_configure("folder", font=("Segoe UI", 9, "bold"))
            self.tree.tag_configure("warn", foreground="#a06000")
            self.tree.tag_configure("error", foreground="#b00000")
            self.tree.tag_configure("ok", foreground="#0a6b0a")

            self.tree.bind("<Button-1>", self.on_click)
            self.tree.bind("<Double-1>", self.on_double_click)
            self.tree.bind("<space>", lambda _e: self.toggle_selected_rows())
            self.tree.bind("<Button-3>", self.on_right_click)

            self.menu = tk.Menu(self.win, tearoff=0)
            self.menu.add_command(label="Preview with default program",
                                  command=lambda: self.act_on_focus(open_file))
            self.menu.add_command(label="Open with...",
                                  command=lambda: self.act_on_focus(open_with_dialog))
            self.menu.add_separator()
            self.menu.add_command(label="Show in folder",
                                  command=lambda: self.act_on_focus(reveal_in_explorer))
            self.menu.add_command(label="Open containing folder",
                                  command=lambda: self.act_on_focus(
                                      lambda p: open_folder(os.path.dirname(p))))
            self.menu.add_separator()
            self.menu.add_command(label="Copy full path", command=self.copy_path)
            self.menu.add_command(label="Copy source URL", command=self.copy_source)

            actions = ttk.LabelFrame(self.win, text="3. Check, then unblock")
            actions.pack(fill="x", **pad)
            arow = ttk.Frame(actions)
            arow.pack(fill="x", padx=6, pady=6)
            self.btn_dry = ttk.Button(arow, text="Dry run (check selected)",
                                      command=self.start_dry_run, state="disabled")
            self.btn_dry.pack(side="left")
            self.btn_unblock = ttk.Button(arow, text="Unblock selected",
                                          command=self.start_unblock, state="disabled")
            self.btn_unblock.pack(side="left", padx=6)
            ttk.Button(arow, text="Export CSV...", command=self.export).pack(side="left")
            self.progress = ttk.Progressbar(arow, mode="determinate", length=260)
            self.progress.pack(side="right")
            ttk.Label(arow, textvariable=self.var_status).pack(side="right", padx=8)

            logframe = ttk.LabelFrame(self.win, text="Log")
            logframe.pack(fill="both", padx=6, pady=(0, 6))
            self.logbox = tk.Text(logframe, height=7, wrap="none")
            logscroll = ttk.Scrollbar(logframe, orient="vertical",
                                      command=self.logbox.yview)
            self.logbox.configure(yscrollcommand=logscroll.set, state="disabled")
            self.logbox.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
            logscroll.pack(side="right", fill="y", pady=6)

        # -- small helpers -------------------------------------------------
        def log(self, message: str) -> None:
            self.logbox.configure(state="normal")
            self.logbox.insert("end", f"{datetime.now():%H:%M:%S}  {message}\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")

        def busy(self, value: bool) -> None:
            self.is_busy = value
            state = "disabled" if value else "normal"
            self.btn_scan.configure(state=state)
            self.btn_stop.configure(state="normal" if value else "disabled")
            if value:
                self.btn_dry.configure(state="disabled")
                self.btn_unblock.configure(state="disabled")
            else:
                self.update_buttons()

        def update_buttons(self) -> None:
            if self.is_busy:
                # Keep both buttons disabled while a scan, dry run or unblock is running.
                self.btn_dry.configure(state="disabled")
                self.btn_unblock.configure(state="disabled")
                return
            has_selection = bool(self.picked_entries())
            self.btn_dry.configure(state="normal" if has_selection else "disabled")
            runnable = self.runnable_entries()
            self.btn_unblock.configure(
                state="normal" if (self.dry_run_done and runnable) else "disabled")

        def invalidate_dry_run(self) -> None:
            if self.dry_run_done:
                self.dry_run_done = False
                self.log("Selection changed - run the dry run again before unblocking.")
            self.update_buttons()

        def current_entries(self) -> list[FileEntry]:
            if self.result is None:
                return []
            if self.var_all_zones.get():
                return list(self.result.entries)
            return self.result.blocked

        def browse(self) -> None:
            chosen = filedialog.askdirectory(initialdir=self.var_path.get() or os.getcwd(),
                                             title="Choose a folder to scan")
            if chosen:
                self.var_path.set(os.path.normpath(chosen))

        def on_types_changed(self, _event=None) -> None:
            if self.preset_key() == "all":
                messagebox.showwarning(APP_NAME, ALL_FILES_WARNING)

        def on_macros_toggled(self) -> None:
            if self.var_macros.get() and not messagebox.askyesno(
                    APP_NAME,
                    "Include macro-enabled Office files?\n\n"
                    "Unblocking one of these lets its macros run when it is opened. "
                    "Macros in files from the internet are a common way to spread malware.\n\n"
                    "Only continue if you trust every one of these files.",
                    icon="warning"):
                self.var_macros.set(False)

        def preset_key(self) -> str:
            for key, (label, _) in PRESETS.items():
                if label == self.var_types.get():
                    return key
            return "documents"

        # -- scanning ------------------------------------------------------
        def start_scan(self) -> None:
            path = os.path.abspath(self.var_path.get().strip('" '))
            if not os.path.isdir(path):
                messagebox.showerror(APP_NAME, f"Not a folder:\n{path}")
                return
            self.var_path.set(path)
            self.cancel.clear()
            self.dry_run_done = False
            self.tree.delete(*self.tree.get_children())
            self.by_iid.clear()
            self.busy(True)
            self.progress.configure(mode="indeterminate")
            self.progress.start(60)
            _, extensions = PRESETS[self.preset_key()]
            recurse = self.var_recurse.get()
            include_macros = self.var_macros.get()
            self.log(f"Scanning {path} ({'with' if recurse else 'without'} subfolders"
                     f"{', macro-enabled files included' if include_macros else ''})...")

            def work():
                try:
                    res = scan(path, recurse=recurse, extensions=extensions,
                               progress=lambda s, f: self.win.after(
                                   0, self.var_status.set,
                                   f"{s:,} files checked, {f:,} tagged"),
                               cancel=self.cancel, include_macros=include_macros)
                except Exception as exc:  # keep the window alive
                    self.win.after(0, self.worker_failed, exc)
                else:
                    self.win.after(0, self.scan_done, res)

            self.worker = threading.Thread(target=work, daemon=True)
            self.worker.start()

        def worker_failed(self, exc: Exception) -> None:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.busy(False)
            self.log(f"Something went wrong: {exc}")
            messagebox.showerror(APP_NAME, f"Something went wrong:\n{exc}")

        def scan_done(self, res: ScanResult) -> None:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.result = res
            for entry in res.entries:
                entry.selected = entry.is_blocked
            self.busy(False)

            blocked = len(res.blocked)
            folders = len(res.folders(res.blocked))
            other = len(res.other_zone)
            self.var_summary.set(
                f"{blocked:,} blocked file(s) in {folders:,} folder(s)"
                f"   -   {res.scanned:,} files checked"
                + (f"   -   {other:,} tagged with another zone" if other else ""))
            self.var_status.set("Scan finished." if not res.cancelled else "Scan stopped.")
            self.log(f"Scan {'stopped' if res.cancelled else 'finished'}: "
                     f"{res.scanned:,} checked, {blocked:,} blocked "
                     f"across {folders:,} folder(s).")
            if res.errors:
                self.log(f"{len(res.errors)} item(s) could not be read:")
                for line in res.errors[:5]:
                    self.log(f"    {line}")
                if len(res.errors) > 5:
                    self.log(f"    ... and {len(res.errors) - 5} more")
            self.refresh_tree()
            if blocked == 0:
                messagebox.showinfo(APP_NAME, "No blocked files found in that folder.")

        def stop(self) -> None:
            self.cancel.set()
            self.var_status.set("Stopping...")

        # -- the list ------------------------------------------------------
        def matches_filter(self, entry: FileEntry) -> bool:
            needle = self.var_filter.get().strip().lower()
            if not needle:
                return True
            return (needle in entry.name.lower() or needle in entry.folder.lower()
                    or needle in entry.source.lower())

        def sort_by(self, column: str) -> None:
            if self.sort_column == column:
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_column, self.sort_reverse = column, False
            self.refresh_tree()

        def sorted_entries(self, entries: list[FileEntry]) -> list[FileEntry]:
            keys = {
                "name": lambda e: e.name.lower(),
                "folder": lambda e: (e.folder.lower(), e.name.lower()),
                "zone": lambda e: (e.zone_id if e.zone_id is not None else -1),
                "source": lambda e: e.source.lower(),
                "size": lambda e: e.size,
                "modified": lambda e: e.modified,
                "check": lambda e: e.check_status,
            }
            key = keys.get(self.sort_column, keys["folder"])
            return sorted(entries, key=key, reverse=self.sort_reverse)

        def row_values(self, entry: FileEntry, in_group: bool) -> tuple:
            return (
                CHECKED if entry.selected else UNCHECKED,
                entry.name,
                "" if in_group else entry.folder,
                entry.zone_name,
                entry.source,
                human_size(entry.size),
                human_time(entry.modified),
                entry.result or entry.check_message,
            )

        def row_tags(self, entry: FileEntry) -> tuple:
            if entry.check_status == STATUS_ERROR:
                return ("error",)
            if entry.check_status == STATUS_WARN:
                return ("warn",)
            if entry.check_status == STATUS_OK:
                return ("ok",)
            return ()

        def refresh_tree(self) -> None:
            self.tree.delete(*self.tree.get_children())
            self.by_iid.clear()
            entries = [e for e in self.current_entries() if self.matches_filter(e)]
            self.visible = self.sorted_entries(entries)

            if self.var_group.get():
                grouped: dict[str, list[FileEntry]] = {}
                for entry in self.visible:
                    grouped.setdefault(entry.folder, []).append(entry)
                for folder in sorted(grouped, key=str.lower):
                    rows = grouped[folder]
                    picked = sum(1 for r in rows if r.selected)
                    node = self.tree.insert(
                        "", "end", iid="dir::" + folder, open=True,
                        values=(CHECKED if picked == len(rows) else UNCHECKED,
                                f"{folder}", "", "", "",
                                f"{len(rows)} file(s)", "", ""),
                        tags=("folder",))
                    for entry in rows:
                        iid = self.tree.insert(node, "end", iid=entry.path,
                                               values=self.row_values(entry, True),
                                               tags=self.row_tags(entry))
                        self.by_iid[iid] = entry
            else:
                for entry in self.visible:
                    iid = self.tree.insert("", "end", iid=entry.path,
                                           values=self.row_values(entry, False),
                                           tags=self.row_tags(entry))
                    self.by_iid[iid] = entry

            self.refresh_status_counts()
            self.update_buttons()

        def update_row(self, entry: FileEntry) -> None:
            if self.tree.exists(entry.path):
                self.tree.item(entry.path,
                               values=self.row_values(entry, self.var_group.get()),
                               tags=self.row_tags(entry))

        def select_all(self, value: bool) -> None:
            for entry in self.visible:
                entry.selected = value
            self.invalidate_dry_run()
            self.refresh_tree()

        def toggle_entry(self, entry: FileEntry) -> None:
            entry.selected = not entry.selected
            self.update_row(entry)
            self.invalidate_dry_run()

        def toggle_selected_rows(self) -> None:
            for iid in self.tree.selection():
                entry = self.by_iid.get(iid)
                if entry is not None:
                    self.toggle_entry(entry)
                elif iid.startswith("dir::"):
                    self.toggle_folder(iid)
            self.refresh_status_counts()

        def toggle_folder(self, iid: str) -> None:
            folder = iid[5:]
            rows = [e for e in self.visible if e.folder == folder]
            value = not all(e.selected for e in rows)
            for entry in rows:
                entry.selected = value
                self.update_row(entry)
            current = list(self.tree.item(iid, "values"))
            current[0] = CHECKED if value else UNCHECKED
            self.tree.item(iid, values=current)
            self.invalidate_dry_run()

        def hidden_ticked_count(self) -> int:
            visible = {id(e) for e in self.visible}
            return sum(1 for e in self.current_entries() if e.selected and id(e) not in visible)

        def refresh_status_counts(self) -> None:
            picked = len(self.picked_entries())
            text = f"{len(self.visible):,} shown, {picked:,} ticked"
            hidden = self.hidden_ticked_count()
            if hidden:
                text += f" ({hidden:,} hidden rows also ticked - not included)"
            self.var_status.set(text)

        def on_click(self, event) -> None:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            if self.tree.identify_column(event.x) != "#1":
                return
            iid = self.tree.identify_row(event.y)
            if not iid:
                return
            if iid.startswith("dir::"):
                self.toggle_folder(iid)
            else:
                entry = self.by_iid.get(iid)
                if entry is not None:
                    self.toggle_entry(entry)
            self.refresh_status_counts()

        def on_double_click(self, event) -> str | None:
            iid = self.tree.identify_row(event.y)
            if not iid:
                return None
            if iid.startswith("dir::"):
                error = open_folder(iid[5:])
            else:
                entry = self.by_iid.get(iid)
                if entry is None:
                    return None
                self.log(f"Previewing {entry.name}")
                error = open_file(entry.path)
            if error:
                self.log(error)
            return "break"

        def on_right_click(self, event) -> None:
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.menu.tk_popup(event.x_root, event.y_root)
                self.menu.grab_release()

        def focused_path(self) -> str | None:
            iid = self.tree.focus()
            if not iid:
                return None
            if iid.startswith("dir::"):
                return iid[5:]
            entry = self.by_iid.get(iid)
            return entry.path if entry else None

        def act_on_focus(self, action) -> None:
            path = self.focused_path()
            if not path:
                return
            error = action(path)
            if error:
                self.log(error)

        def copy_path(self) -> None:
            path = self.focused_path()
            if path:
                self.win.clipboard_clear()
                self.win.clipboard_append(path)
                self.log("Path copied to the clipboard.")

        def copy_source(self) -> None:
            iid = self.tree.focus()
            entry = self.by_iid.get(iid) if iid else None
            if entry and entry.source:
                self.win.clipboard_clear()
                self.win.clipboard_append(entry.source)
                self.log("Source URL copied to the clipboard.")
            else:
                self.log("No source URL recorded for that file.")

        # -- dry run / unblock ---------------------------------------------
        def picked_entries(self) -> list[FileEntry]:
            # Only rows shown in the list count. Ticked rows hidden by the filter are left out,
            # so Dry run and Unblock always act on what you can see.
            return [e for e in self.visible if e.selected]

        def runnable_entries(self) -> list[FileEntry]:
            """Ticked, visible files that passed the last dry run."""
            return [e for e in self.picked_entries()
                    if e.path in self.dry_run_paths
                    and e.check_status and e.check_status != STATUS_ERROR]

        def run_worker(self, target, label: str) -> None:
            self.cancel.clear()
            self.busy(True)
            targets = self.picked_entries()
            self.progress.configure(mode="determinate", maximum=max(len(targets), 1),
                                    value=0)
            self.log(f"{label} {len(targets):,} file(s)...")

            def work():
                try:
                    outcome = target(targets)
                except Exception as exc:
                    self.win.after(0, self.worker_failed, exc)
                else:
                    self.win.after(0, self.worker_done, label, targets, outcome)

            self.worker = threading.Thread(target=work, daemon=True)
            self.worker.start()

        def tick(self, index: int, total: int, entry: FileEntry) -> None:
            # Called from the worker thread: coalesce updates so a run over
            # thousands of files does not swamp the event loop.
            now = time.monotonic()
            if index != total and now - self._last_tick < 0.1:
                return
            self._last_tick = now

            def apply():
                self.progress.configure(value=index)
                self.var_status.set(f"{index:,} / {total:,}  {entry.name}")
            self.win.after(0, apply)

        def start_dry_run(self) -> None:
            def target(entries):
                return dry_run(entries, progress=lambda i, t, e: self.tick(i, t, e),
                               cancel=self.cancel)
            self.run_worker(target, "Dry run on")

        def start_unblock(self) -> None:
            targets = self.runnable_entries()
            skipped = len(self.picked_entries()) - len(targets)
            message = f"Unblock {len(targets):,} file(s)?"
            if skipped:
                message += f"\n\n{skipped:,} file(s) failed or missed the dry run and will be skipped."
            hidden = self.hidden_ticked_count()
            if hidden:
                message += f"\n\n{hidden:,} ticked file(s) hidden by the filter are not included."
            if not messagebox.askyesno(APP_NAME, message):
                return
            runnable_paths = {e.path for e in targets}

            def target(entries):
                runnable = [e for e in entries if e.path in runnable_paths]
                return unblock_all(runnable,
                                   progress=lambda i, t, e, ok: self.tick(i, t, e),
                                   cancel=self.cancel)
            self.run_worker(target, "Unblocking")

        def worker_done(self, label: str, targets: list[FileEntry], outcome) -> None:
            self.progress.configure(value=0)
            if label.startswith("Dry run"):
                counts = outcome
                self.dry_run_done = not self.cancel.is_set()
                self.dry_run_paths = {e.path for e in targets} if self.dry_run_done else set()
                self.log(f"Dry run: {counts[STATUS_OK]:,} ready, "
                         f"{counts[STATUS_WARN]:,} warning(s), "
                         f"{counts[STATUS_ERROR]:,} problem(s).")
                for entry in targets:
                    if entry.check_status == STATUS_ERROR:
                        self.log(f"    PROBLEM  {entry.path}: {entry.check_message}")
                self.refresh_tree()
                self.var_status.set("Dry run finished - you can unblock now."
                                    if self.dry_run_done else "Dry run stopped.")
                if counts[STATUS_ERROR] and self.dry_run_done:
                    messagebox.showwarning(
                        APP_NAME,
                        f"{counts[STATUS_ERROR]:,} file(s) cannot be unblocked yet.\n"
                        "They are listed in the log and will be skipped.")
            else:
                done, failed = outcome
                self.log(f"Unblocked {done:,} file(s), {failed:,} failed.")
                for entry in targets:
                    if entry.result and entry.result not in ("Unblocked",
                                                             "Was not blocked any more"):
                        self.log(f"    FAILED   {entry.path}: {entry.result}")
                self.var_status.set(f"Unblocked {done:,}, failed {failed:,}.")
                self.dry_run_done = False
                self.dry_run_paths = set()
                cleared = {e.path for e in targets
                           if e.result in ("Unblocked", "Was not blocked any more")}
                if self.result is not None and cleared:
                    self.result.entries = [e for e in self.result.entries
                                           if e.path not in cleared]
                self.refresh_tree()
                blocked = len(self.result.blocked) if self.result else 0
                folders = len(self.result.folders(self.result.blocked)) if self.result else 0
                self.var_summary.set(
                    f"{blocked:,} blocked file(s) left in {folders:,} folder(s)")
                messagebox.showinfo(APP_NAME,
                                    f"Unblocked {done:,} file(s).\nFailed: {failed:,}.")
            self.busy(False)

        def export(self) -> None:
            entries = self.current_entries()
            if not entries:
                messagebox.showinfo(APP_NAME, "Nothing to export - run a scan first.")
                return
            path = filedialog.asksaveasfilename(
                title="Save report", defaultextension=".csv",
                initialfile="blocked_files.csv",
                filetypes=[("CSV file", "*.csv"), ("All files", "*.*")])
            if not path:
                return
            try:
                export_csv(entries, path)
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"Could not write the file:\n{exc}")
                return
            self.log(f"Report written to {path}")

    window = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if IS_WINDOWS else "clam")
    except Exception:
        pass
    App(window, os.path.abspath(args.path), args.types, not args.no_recurse,
        args.include_macros)
    window.mainloop()
    return 0


# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find and unblock documents and Microsoft Office files "
                    "that Windows marked as coming from another computer.")
    parser.add_argument("path", nargs="?", default=os.getcwd(),
                        help="folder to scan (default: current folder)")
    parser.add_argument("--path", dest="path_opt",
                        help="folder to scan (same as the positional argument)")
    parser.add_argument("--cli", action="store_true",
                        help="run in the console instead of opening the window")
    parser.add_argument("--types", choices=sorted(PRESETS), default="documents",
                        help="which files to look at (default: documents)")
    parser.add_argument("--no-recurse", action="store_true",
                        help="do not look inside subfolders")
    parser.add_argument("--include-macros", action="store_true",
                        help="also handle macro-enabled Office files (.docm, .xlsm, ...)")
    parser.add_argument("--include-all-zones", action="store_true",
                        help="also handle files tagged with a non-internet zone")
    parser.add_argument("--dry-run", action="store_true",
                        help="console mode: stop after the check, change nothing")
    parser.add_argument("--yes", action="store_true",
                        help="console mode: skip the confirmation prompt")
    parser.add_argument("--list", action="store_true",
                        help="console mode: print every blocked file")
    parser.add_argument("--csv", help="write a CSV report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.path_opt:
        args.path = args.path_opt
    if args.cli:
        return run_cli(args)
    return run_gui(args)


if __name__ == "__main__":
    sys.exit(main())
