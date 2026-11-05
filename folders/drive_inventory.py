#!/usr/bin/env python3
"""
drive_inventory.py  -  Read-only file inventory & move tracker (GUI version).

Just run it - no commands to type:
    python drive_inventory.py

Tab 1 (Scan)    : pick a folder -> creates an inventory .db file (your export).
Tab 2 (Compare) : pick the two .db files -> results split into sub-tabs:
                    * Missing  - files in OLD but not found in NEW (maybe lost)
                    * Moved    - same file, different folder (old -> new)
                    * New      - in NEW but not OLD (leftover/extra)
                  Double-click (or right-click) any row to open its location in
                  File Explorer.

Read-only & Google-Drive safe: only reads file metadata (name, logical size,
dates, attributes). It never opens file contents, so it never modifies a file
and never forces an online-only Drive file to download.
"""

import os
import time
import sqlite3
import csv
import itertools
import queue
import threading
import subprocess
import fnmatch
from datetime import datetime, timezone

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BATCH = 10000
MAX_DISPLAY = 20000  # cap rows shown per tab (CSV export is always complete)

FILE_ATTRIBUTE_OFFLINE               = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN        = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
ONLINE_ONLY_MASK = (FILE_ATTRIBUTE_OFFLINE
                    | FILE_ATTRIBUTE_RECALL_ON_OPEN
                    | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
FILE_ATTRIBUTE_HIDDEN = 0x00000002

# Folder names skipped by default (Google Drive system/cache + Windows system).
# These are matched against folder names, case-insensitive, and support * ? globs.
DEFAULT_IGNORE = [
    ".tmp.drivedownload",
    ".tmp.driveupload",
    ".shortcut-targets-by-id",
    ".file-revisions-by-id",
    ".Trash",
    ".Trash-*",
    "$RECYCLE.BIN",
    "System Volume Information",
]

# result tuple layout (one per changed file)
#  0 status   1 filename  2 size      3 old_rel  4 old_top
#  5 new_rel  6 new_top   7 online    8 old_abs  9 new_abs


# --------------------------------------------------------------------------- #
#  Read-only engine (runs in a background thread; talks to GUI via a queue)
# --------------------------------------------------------------------------- #
def iso(ts):
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return ""


def human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def relparts(abspath, root):
    rel = os.path.relpath(abspath, root)
    parent = os.path.dirname(rel)
    norm = parent.replace("\\", "/")
    top = norm.split("/", 1)[0] if norm and norm != "." else ""
    if parent == ".":
        parent = ""
    return rel, parent, top


def _is_hidden(entry):
    try:
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attrs & FILE_ATTRIBUTE_HIDDEN)
    except OSError:
        return False


def walk_files(root, ignore_patterns=(), skip_hidden=True):
    """
    Walk `root`, yielding file DirEntry objects. Whole folders are skipped when:
      * skip_hidden is True and the folder is hidden (Windows hidden attribute
        or a dot-folder) - this covers Google Drive's hidden cache folders, or
      * the folder name matches one of ignore_patterns (case-insensitive, globs).
    """
    ign = [p.strip().lower() for p in ignore_patterns if p.strip()]
    walk_files.skipped = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            it = os.scandir(current)
        except (PermissionError, FileNotFoundError, OSError):
            continue
        with it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        name = entry.name
                        low = name.lower()
                        if skip_hidden and (name.startswith(".") or _is_hidden(entry)):
                            walk_files.skipped += 1
                            continue
                        if any(fnmatch.fnmatch(low, pat) for pat in ign):
                            walk_files.skipped += 1
                            continue
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        yield entry
                except OSError:
                    continue


walk_files.skipped = 0


def run_scan(root, db_path, label, ignore_patterns, skip_hidden, q, stop_flag):
    try:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            q.put(("error", f"Not a folder:\n{root}"))
            return
        # The GUI has already asked the user before replacing an existing file.
        if os.path.exists(db_path):
            os.remove(db_path)

        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=MEMORY")
        cur.execute("PRAGMA synchronous=OFF")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.execute("""
            CREATE TABLE files (
                relpath TEXT, parent TEXT, top_folder TEXT, filename TEXT,
                ext TEXT, size INTEGER, created TEXT, modified TEXT,
                online_only INTEGER, abspath TEXT)""")
        cur.execute("""CREATE TABLE meta
            (scan_root TEXT, label TEXT, scanned_at TEXT, file_count INTEGER)""")

        insert = "INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?)"
        rows, n, t0 = [], 0, time.time()

        for entry in walk_files(root, ignore_patterns, skip_hidden):
            if stop_flag.is_set():
                con.close()
                try:
                    os.remove(db_path)  # remove the incomplete file this scan created
                except OSError:
                    pass
                q.put(("cancelled", "Scan cancelled. No inventory file was saved."))
                return
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            rel, parent, top = relparts(entry.path, root)
            ext = os.path.splitext(entry.name)[1].lower()
            attrs = getattr(st, "st_file_attributes", 0)
            online = 1 if (attrs & ONLINE_ONLY_MASK) else 0
            rows.append((rel, parent, top, entry.name, ext, st.st_size,
                         iso(st.st_ctime), iso(st.st_mtime), online, entry.path))
            n += 1
            if len(rows) >= BATCH:
                cur.executemany(insert, rows)
                rows.clear()
                rate = n / max(time.time() - t0, 0.001)
                q.put(("progress", (n, rate)))

        if rows:
            cur.executemany(insert, rows)
        q.put(("status", "Building index ..."))
        cur.execute("CREATE INDEX idx_key ON files(filename, size)")
        cur.execute("INSERT INTO meta VALUES (?,?,?,?)",
                    (root, label, datetime.now(timezone.utc).isoformat(), n))
        con.commit()
        con.close()
        dt = time.time() - t0
        skipped = getattr(walk_files, "skipped", 0)
        q.put(("scan_done",
               f"Done! {n:,} files in {dt:,.1f}s\n"
               f"Skipped {skipped:,} hidden/ignored folders.\n"
               f"Saved to: {db_path}\n\n"
               f"Copy this .db file to the other computer to compare it there."))
    except Exception as e:
        q.put(("error", f"Scan failed:\n{e}"))


def grouped(cursor):
    keyfn = lambda r: (r["filename"], r["size"])
    for key, grp in itertools.groupby(cursor, key=keyfn):
        yield key, [dict(r) for r in grp]


def run_compare(old_db, new_db, q, stop_flag):
    try:
        def open_ordered(path):
            c = sqlite3.connect(path)
            c.row_factory = sqlite3.Row
            cur = c.execute(
                "SELECT filename,size,relpath,top_folder,online_only,abspath "
                "FROM files ORDER BY filename, size")
            return c, cur

        con_o, cur_o = open_ordered(old_db)
        con_n, cur_n = open_ordered(new_db)

        counts = dict(UNCHANGED=0, MOVED=0, MISSING=0, NEW=0)
        results = []  # changed files only (MOVED/MISSING/NEW)

        def add(status, o, n):
            counts[status] += 1
            if status == "UNCHANGED":
                return
            results.append((
                status,
                (o or n)["filename"],
                (o or n)["size"],
                o["relpath"] if o else "",
                o["top_folder"] if o else "",
                n["relpath"] if n else "",
                n["top_folder"] if n else "",
                (n["online_only"] if n else (o["online_only"] if o else "")),
                o["abspath"] if o else "",
                n["abspath"] if n else "",
            ))

        def handle_match(o_rows, n_rows):
            o_by = {r["relpath"]: r for r in o_rows}
            n_by = {r["relpath"]: r for r in n_rows}
            for p in (set(o_by) & set(n_by)):
                add("UNCHANGED", o_by[p], n_by[p])
            old_only = sorted(set(o_by) - set(n_by))
            new_only = sorted(set(n_by) - set(o_by))
            pairs = min(len(old_only), len(new_only))
            for i in range(pairs):
                add("MOVED", o_by[old_only[i]], n_by[new_only[i]])
            for p in old_only[pairs:]:
                add("MISSING", o_by[p], None)
            for p in new_only[pairs:]:
                add("NEW", None, n_by[p])

        go, gn = grouped(cur_o), grouped(cur_n)
        o = next(go, None)
        nn = next(gn, None)
        processed = 0
        while o is not None or nn is not None:
            if stop_flag.is_set():
                q.put(("cancelled", "Compare cancelled."))
                con_o.close(); con_n.close()
                return
            if nn is None or (o is not None and o[0] < nn[0]):
                for r in o[1]:
                    add("MISSING", r, None)
                o = next(go, None)
            elif o is None or (nn is not None and nn[0] < o[0]):
                for r in nn[1]:
                    add("NEW", None, r)
                nn = next(gn, None)
            else:
                handle_match(o[1], nn[1])
                o = next(go, None)
                nn = next(gn, None)
            processed += 1
            if processed % 50000 == 0:
                q.put(("status", f"Comparing ... {processed:,} groups"))

        con_o.close(); con_n.close()
        q.put(("compare_done", (counts, results)))
    except Exception as e:
        q.put(("error", f"Compare failed:\n{e}"))


# --------------------------------------------------------------------------- #
#  Open a file's location in Windows File Explorer
# --------------------------------------------------------------------------- #
def open_in_explorer(old_abs, new_abs):
    candidates = [p for p in (new_abs, old_abs) if p]
    # 1) file itself exists on THIS computer -> open folder with it selected
    for p in candidates:
        if os.path.exists(p):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
            return True, None
    # 2) file not here (e.g. it lives only on the other PC) -> nearest folder
    for p in candidates:
        folder = os.path.dirname(p)
        while folder and not os.path.isdir(folder):
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
        if folder and os.path.isdir(folder):
            subprocess.Popen(["explorer", os.path.normpath(folder)])
            return True, (f"The file itself isn't on THIS computer (it may exist only "
                          f"on the other one).\n\nOpened the nearest existing folder:\n{folder}")
    return False, ("Could not find this file or its folder on this computer.\n"
                   "It likely exists only on the other computer's drive.")


# --------------------------------------------------------------------------- #
#  GUI
# --------------------------------------------------------------------------- #
# per sub-tab: list of (column_id, header, width, result_field_index) and which
# absolute path to favour when opening Explorer.
TAB_SPECS = {
    "MISSING": {
        "title": "Missing",
        "cols": [("filename", "File name", 240, 1), ("size", "Size", 90, 2),
                 ("folder", "Folder it was in", 360, 3), ("cloud", "In cloud", 70, 7)],
    },
    "MOVED": {
        "title": "Moved",
        "cols": [("filename", "File name", 220, 1), ("size", "Size", 90, 2),
                 ("old", "Old folder", 270, 3), ("new", "New folder", 270, 5),
                 ("cloud", "In cloud", 70, 7)],
    },
    "NEW": {
        "title": "New / leftover",
        "cols": [("filename", "File name", 240, 1), ("size", "Size", 90, 2),
                 ("folder", "Folder it is in now", 360, 5), ("cloud", "In cloud", 70, 7)],
    },
}
TAB_ORDER = ["MISSING", "MOVED", "NEW"]


class App:
    def __init__(self, root):
        self.root = root
        root.title("Drive Inventory  -  read-only file move tracker")
        root.geometry("1000x660")
        self.q = queue.Queue()
        self.stop_flag = threading.Event()
        self.worker = None
        self.by_status = {s: [] for s in TAB_ORDER}
        self.last_counts = {}
        self.trees = {}
        self.sort_state = {}

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.scan_tab = ttk.Frame(nb)
        self.cmp_tab = ttk.Frame(nb)
        nb.add(self.scan_tab, text="  1. Scan a folder  ")
        nb.add(self.cmp_tab, text="  2. Compare  ")

        self._build_scan_tab()
        self._build_compare_tab()
        self.root.after(100, self._poll_queue)

    # ----- Scan tab -------------------------------------------------------- #
    def _build_scan_tab(self):
        f = self.scan_tab
        pad = dict(padx=8, pady=6)
        ttk.Label(f, text="Step 1: scan this computer's folder into an inventory file.",
                  font=("", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(f, text="Folder to scan:").grid(row=1, column=0, sticky="e", **pad)
        self.scan_folder = tk.StringVar()
        ttk.Entry(f, textvariable=self.scan_folder, width=70).grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(f, text="Browse...", command=self._pick_scan_folder).grid(row=1, column=2, **pad)

        ttk.Label(f, text="Save inventory as:").grid(row=2, column=0, sticky="e", **pad)
        self.scan_db = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "inventory.db"))
        ttk.Entry(f, textvariable=self.scan_db, width=70).grid(row=2, column=1, sticky="we", **pad)
        ttk.Button(f, text="Browse...", command=self._pick_scan_db).grid(row=2, column=2, **pad)

        ttk.Label(f, text="This computer's name:").grid(row=3, column=0, sticky="e", **pad)
        self.scan_label = tk.StringVar(value="this-pc")
        ttk.Entry(f, textvariable=self.scan_label, width=30).grid(row=3, column=1, sticky="w", **pad)

        self.skip_hidden = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            f, variable=self.skip_hidden,
            text="Skip hidden folders (recommended - hides Google Drive cache/system folders)"
        ).grid(row=4, column=1, columnspan=2, sticky="w", **pad)

        ttk.Label(f, text="Also ignore these folder\nnames (one per line):",
                  justify="right").grid(row=5, column=0, sticky="ne", **pad)
        self.ignore_text = tk.Text(f, height=6, width=50, wrap="none")
        self.ignore_text.insert("1.0", "\n".join(DEFAULT_IGNORE))
        self.ignore_text.grid(row=5, column=1, sticky="we", **pad)
        ttk.Label(f, foreground="#666", justify="left", wraplength=180,
                  text="Names match folders anywhere in the tree. * and ? wildcards work, "
                       "e.g.  cache*  or  *_temp").grid(row=5, column=2, sticky="nw", **pad)

        scan_btns = ttk.Frame(f)
        scan_btns.grid(row=6, column=1, sticky="w", **pad)
        self.scan_btn = ttk.Button(scan_btns, text="Start Scan", command=self._start_scan)
        self.scan_btn.pack(side="left")
        self.scan_cancel_btn = ttk.Button(scan_btns, text="Cancel", command=self._cancel,
                                          state="disabled")
        self.scan_cancel_btn.pack(side="left", padx=(8, 0))
        self.scan_progress = ttk.Progressbar(f, mode="indeterminate", length=400)
        self.scan_progress.grid(row=7, column=1, sticky="we", **pad)
        self.scan_status = tk.StringVar(value="Idle.")
        ttk.Label(f, textvariable=self.scan_status, foreground="#444").grid(
            row=8, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(f, foreground="#666", wraplength=900, justify="left",
                  text="Tip: run this on the laptop (save as laptop.db), copy that file to the "
                       "desktop, then run it on the desktop (save as desktop.db). Then use the "
                       "Compare tab.").grid(row=9, column=0, columnspan=3, sticky="w", **pad)
        f.columnconfigure(1, weight=1)

    def _pick_scan_folder(self):
        d = filedialog.askdirectory(title="Choose the folder to scan")
        if d:
            self.scan_folder.set(d)

    def _pick_scan_db(self):
        p = filedialog.asksaveasfilename(
            title="Save inventory file as", defaultextension=".db",
            initialfile="inventory.db",
            filetypes=[("Inventory database", "*.db"), ("All files", "*.*")])
        if p:
            self.scan_db.set(p)

    def _start_scan(self):
        if self.worker and self.worker.is_alive():
            return
        folder = self.scan_folder.get().strip()
        db = self.scan_db.get().strip()
        if not folder or not db:
            messagebox.showwarning("Missing info", "Please choose a folder and an output file.")
            return
        if os.path.exists(db) and not messagebox.askyesno(
                "Replace file?",
                f"This inventory file already exists:\n{db}\n\n"
                "Replace it with the new scan?\n\n"
                "Click No to keep it and choose a different name."):
            return
        ignore = self.ignore_text.get("1.0", "end").splitlines()
        self.stop_flag.clear()
        self.scan_btn.config(state="disabled")
        self.scan_cancel_btn.config(state="normal")
        self.scan_progress.start(12)
        self.scan_status.set("Scanning ...")
        self.worker = threading.Thread(
            target=run_scan,
            args=(folder, db, self.scan_label.get().strip() or "this-pc",
                  ignore, self.skip_hidden.get(), self.q, self.stop_flag), daemon=True)
        self.worker.start()

    # ----- Compare tab ----------------------------------------------------- #
    def _build_compare_tab(self):
        f = self.cmp_tab
        pad = dict(padx=8, pady=5)

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="OLD inventory (e.g. laptop.db):").grid(row=0, column=0, sticky="e", **pad)
        self.old_db = tk.StringVar()
        ttk.Entry(top, textvariable=self.old_db, width=58).grid(row=0, column=1, sticky="we", **pad)
        ttk.Button(top, text="Browse...", command=lambda: self._pick_db(self.old_db)).grid(row=0, column=2, **pad)
        ttk.Label(top, text="NEW inventory (e.g. desktop.db):").grid(row=1, column=0, sticky="e", **pad)
        self.new_db = tk.StringVar()
        ttk.Entry(top, textvariable=self.new_db, width=58).grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(top, text="Browse...", command=lambda: self._pick_db(self.new_db)).grid(row=1, column=2, **pad)
        cmp_btns = ttk.Frame(top)
        cmp_btns.grid(row=2, column=1, sticky="w", **pad)
        self.cmp_btn = ttk.Button(cmp_btns, text="Compare", command=self._start_compare)
        self.cmp_btn.pack(side="left")
        self.cmp_cancel_btn = ttk.Button(cmp_btns, text="Cancel", command=self._cancel,
                                         state="disabled")
        self.cmp_cancel_btn.pack(side="left", padx=(8, 0))
        top.columnconfigure(1, weight=1)

        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Label(bar, text="Search file name:").pack(side="left")
        self.search_var = tk.StringVar()
        se = ttk.Entry(bar, textvariable=self.search_var, width=26)
        se.pack(side="left", padx=4)
        se.bind("<KeyRelease>", lambda e: self._fill_all())
        ttk.Label(bar, foreground="#666",
                  text="Double-click a row (or right-click) to open its location in File Explorer."
                  ).pack(side="left", padx=14)
        ttk.Button(bar, text="Export all to CSV...", command=self._export_csv).pack(side="right")

        # sub-tabs, one per status
        self.result_nb = ttk.Notebook(f)
        self.result_nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.menu = tk.Menu(self.root, tearoff=0)

        for status in TAB_ORDER:
            frame = ttk.Frame(self.result_nb)
            self.result_nb.add(frame, text=TAB_SPECS[status]["title"])
            tree = self._build_tree(frame, status)
            self.trees[status] = tree

        self.cmp_status = tk.StringVar(value="Pick two inventory files and click Compare.")
        ttk.Label(f, textvariable=self.cmp_status, foreground="#444").pack(anchor="w", padx=10, pady=4)

    def _build_tree(self, parent, status):
        spec = TAB_SPECS[status]
        col_ids = [c[0] for c in spec["cols"]]
        tree = ttk.Treeview(parent, columns=col_ids, show="headings")
        for cid, header, width, field in spec["cols"]:
            tree.heading(cid, text=header,
                         command=lambda s=status, fi=field: self._sort(s, fi))
            tree.column(cid, width=width, anchor="w")
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="we")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        tree._rows = {}          # item_id -> (old_abs, new_abs)
        tree._status = status
        tree.bind("<Double-1>", self._on_open)
        tree.bind("<Button-3>", self._on_right_click)
        return tree

    def _pick_db(self, var):
        p = filedialog.askopenfilename(
            title="Choose an inventory .db file",
            filetypes=[("Inventory database", "*.db"), ("All files", "*.*")])
        if p:
            var.set(p)

    def _start_compare(self):
        if self.worker and self.worker.is_alive():
            return
        old, new = self.old_db.get().strip(), self.new_db.get().strip()
        if not os.path.exists(old) or not os.path.exists(new):
            messagebox.showwarning("Missing files", "Please choose both inventory files.")
            return
        self.stop_flag.clear()
        self.cmp_btn.config(state="disabled")
        self.cmp_cancel_btn.config(state="normal")
        self.cmp_status.set("Comparing ...")
        for t in self.trees.values():
            t.delete(*t.get_children())
        self.worker = threading.Thread(
            target=run_compare, args=(old, new, self.q, self.stop_flag), daemon=True)
        self.worker.start()

    def _cancel(self):
        if self.worker and self.worker.is_alive():
            self.stop_flag.set()
            self.scan_cancel_btn.config(state="disabled")
            self.cmp_cancel_btn.config(state="disabled")
            self.scan_status.set("Cancelling ...")
            self.cmp_status.set("Cancelling ...")

    def _reset_buttons(self):
        self.scan_progress.stop()
        self.scan_btn.config(state="normal")
        self.cmp_btn.config(state="normal")
        self.scan_cancel_btn.config(state="disabled")
        self.cmp_cancel_btn.config(state="disabled")

    # ----- table population ----------------------------------------------- #
    def _fill_all(self):
        for status in TAB_ORDER:
            self._fill_tree(status)
        self._update_status_line()

    def _fill_tree(self, status):
        tree = self.trees[status]
        spec = TAB_SPECS[status]
        term = self.search_var.get().strip().lower()
        tree.delete(*tree.get_children())
        tree._rows.clear()
        rows = self.by_status[status]
        if term:
            rows = [r for r in rows if term in r[1].lower()]
        shown = rows[:MAX_DISPLAY]
        for r in shown:
            values = []
            for cid, header, width, field in spec["cols"]:
                if cid == "size":
                    values.append(human_size(r[field]))
                elif cid == "cloud":
                    v = r[field]
                    values.append("Yes" if str(v) == "1" else ("" if v == "" else "No"))
                else:
                    values.append(r[field] or "-")
            item = tree.insert("", "end", values=values)
            tree._rows[item] = (r[8], r[9])     # old_abs, new_abs
        # reflect count (and any cap) in the sub-tab label
        idx = TAB_ORDER.index(status)
        total = len(self.by_status[status])
        label = f"{spec['title']} ({total:,})"
        if len(rows) > MAX_DISPLAY:
            label += " *"
        self.result_nb.tab(idx, text=label)

    def _update_status_line(self):
        c = self.last_counts
        msg = (f"UNCHANGED {c.get('UNCHANGED', 0):,}   |   "
               f"MOVED {c.get('MOVED', 0):,}   |   "
               f"MISSING {c.get('MISSING', 0):,}   |   "
               f"NEW {c.get('NEW', 0):,}")
        if any(len(self.by_status[s]) > MAX_DISPLAY for s in TAB_ORDER):
            msg += f"      (* tab shows first {MAX_DISPLAY:,}; use Export for the full list)"
        self.cmp_status.set(msg)

    def _sort(self, status, field):
        key_id = (status, field)
        asc = not self.sort_state.get(key_id, False)
        self.sort_state[key_id] = asc
        if field == 2:  # size: numeric
            keyfn = lambda r: (r[field] if isinstance(r[field], (int, float)) else 0)
        else:
            keyfn = lambda r: str(r[field]).lower()
        self.by_status[status].sort(key=keyfn, reverse=not asc)
        self._fill_tree(status)

    # ----- open in Explorer ------------------------------------------------ #
    def _open_item(self, tree, item):
        paths = tree._rows.get(item)
        if not paths:
            return
        ok, note = open_in_explorer(paths[0], paths[1])
        if note and ok:
            messagebox.showinfo("Opened nearest folder", note)
        elif not ok:
            messagebox.showwarning("Not found", note)

    def _on_open(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if item:
            self._open_item(tree, item)

    def _on_right_click(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item:
            return
        tree.selection_set(item)
        self.menu.delete(0, "end")
        self.menu.add_command(label="Open file location in Explorer",
                              command=lambda: self._open_item(tree, item))
        self.menu.add_command(label="Copy full path",
                              command=lambda: self._copy_path(tree, item))
        self.menu.tk_popup(event.x_root, event.y_root)

    def _copy_path(self, tree, item):
        paths = tree._rows.get(item)
        if not paths:
            return
        p = paths[1] or paths[0]
        self.root.clipboard_clear()
        self.root.clipboard_append(p)

    # ----- export ---------------------------------------------------------- #
    def _export_csv(self):
        if not any(self.by_status.values()):
            messagebox.showinfo("Nothing to export", "Run a comparison first.")
            return
        p = filedialog.asksaveasfilename(
            title="Save full report as", defaultextension=".csv",
            initialfile="report.csv", filetypes=[("CSV file", "*.csv")])
        if not p:
            return
        n = 0
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["status", "filename", "size_bytes",
                        "old_relpath", "old_top_folder",
                        "new_relpath", "new_top_folder", "online_only",
                        "old_abspath", "new_abspath"])
            for status in TAB_ORDER:
                for r in self.by_status[status]:
                    w.writerow(r)
                    n += 1
        messagebox.showinfo("Exported", f"Saved {n:,} rows to:\n{p}")

    # ----- queue polling --------------------------------------------------- #
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    n, rate = payload
                    self.scan_status.set(f"Scanning ... {n:,} files  ({rate:,.0f}/sec)")
                elif kind == "status":
                    self.scan_status.set(payload)
                    self.cmp_status.set(payload)
                elif kind == "scan_done":
                    self._reset_buttons()
                    self.scan_status.set("Done.")
                    messagebox.showinfo("Scan complete", payload)
                elif kind == "compare_done":
                    counts, results = payload
                    self.last_counts = counts
                    self.by_status = {s: [] for s in TAB_ORDER}
                    for r in results:
                        self.by_status[r[0]].append(r)
                    self._reset_buttons()
                    self._fill_all()
                elif kind == "cancelled":
                    self._reset_buttons()
                    self.scan_status.set("Stopped.")
                    self.cmp_status.set(payload)
                    messagebox.showinfo("Cancelled", payload)
                elif kind == "error":
                    self._reset_buttons()
                    self.scan_status.set("Stopped.")
                    messagebox.showerror("Error", payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
