"""Desktop GUI for the interior product binder generator (tkinter).

Runs from source (``python gui.py``) or as a PyInstaller-built Windows exe.
Mirrors the notebook front-end: manual row entry with editing, Excel import,
a Draft toggle, and one-click generation via the shared pipeline.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from dotenv import load_dotenv

import config

# When frozen, .env lives next to the exe; from source, in the repo root.
load_dotenv(os.path.join(config.APP_DIR, ".env"))

from src import excel_reader, pipeline  # noqa: E402  (after load_dotenv)

FIELD_KEYS = ["KEY", "DESCRIPTION", "PATH", "PG", "DESCRIPTION2", "DESCRIPTION3"]
TREE_COLS = ("key", "description", "source")


class BinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("DFH Product Binder Generator")
        root.geometry("900x680")
        root.minsize(760, 560)

        self.rows: list[dict] = []
        self.editing: int | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.last_output: str | None = None

        pad = {"padx": 6, "pady": 3}
        body = ttk.Frame(root, padding=8)
        body.pack(fill="both", expand=True)

        # ── Project details ───────────────────────────────────────────────
        proj = ttk.LabelFrame(body, text="Project details", padding=6)
        proj.pack(fill="x", **pad)
        ttk.Label(proj, text="Project name:").grid(row=0, column=0, sticky="w")
        self.project_var = tk.StringVar(value="Untitled Project")
        ttk.Entry(proj, textvariable=self.project_var, width=52).grid(
            row=0, column=1, sticky="we", padx=6)
        ttk.Label(proj, text="Prepared by:").grid(row=1, column=0, sticky="w")
        self.prepared_var = tk.StringVar(value=os.environ.get("COMPANY_NAME", ""))
        ttk.Entry(proj, textvariable=self.prepared_var, width=52).grid(
            row=1, column=1, sticky="we", padx=6)
        self.draft_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            proj, variable=self.draft_var,
            text="Draft binder (DRAFT watermark + NOT FOR CONSTRUCTION)",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        proj.columnconfigure(1, weight=1)

        # ── Mode tabs ─────────────────────────────────────────────────────
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill="both", expand=True, **pad)
        self.manual_tab = ttk.Frame(self.tabs, padding=6)
        self.import_tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(self.manual_tab, text="Manual entry")
        self.tabs.add(self.import_tab, text="Import Excel")

        self._build_manual_tab()
        self._build_import_tab()

        # ── Generate + log ────────────────────────────────────────────────
        actions = ttk.Frame(body)
        actions.pack(fill="x", **pad)
        self.gen_btn = ttk.Button(actions, text="Generate binder",
                                  command=self.on_generate)
        self.gen_btn.pack(side="left")
        self.open_btn = ttk.Button(actions, text="Open binder",
                                   command=self.on_open, state="disabled")
        self.open_btn.pack(side="left", padx=6)

        self.log = scrolledtext.ScrolledText(body, height=9, state="disabled",
                                             font=("Consolas", 9))
        self.log.pack(fill="both", expand=False, **pad)
        self._log("Ready. API key set: %s (needed only for webpage sources)."
                  % bool(os.environ.get("ANTHROPIC_API_KEY")))

        root.after(150, self._drain_log)

    # ── Manual tab ────────────────────────────────────────────────────────
    def _build_manual_tab(self):
        t = self.manual_tab
        form = ttk.Frame(t)
        form.pack(fill="x")

        ttk.Label(form, text="KEY:").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="Description:").grid(row=0, column=2, sticky="w")
        ttk.Label(form, text="Source:").grid(row=1, column=0, sticky="w")
        ttk.Label(form, text="PG (group):").grid(row=2, column=0, sticky="w")
        ttk.Label(form, text="Description 2:").grid(row=3, column=0, sticky="w")
        ttk.Label(form, text="Description 3:").grid(row=4, column=0, sticky="w")

        self.field_vars = {k: tk.StringVar() for k in FIELD_KEYS}
        ttk.Entry(form, textvariable=self.field_vars["KEY"], width=14).grid(
            row=0, column=1, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.field_vars["DESCRIPTION"]).grid(
            row=0, column=3, sticky="we", padx=4)
        ttk.Entry(form, textvariable=self.field_vars["PATH"]).grid(
            row=1, column=1, columnspan=3, sticky="we", padx=4)
        ttk.Button(form, text="Browse...", command=self.on_browse_pdf).grid(
            row=1, column=4, padx=2)
        ttk.Entry(form, textvariable=self.field_vars["PG"], width=14).grid(
            row=2, column=1, sticky="w", padx=4)
        ttk.Label(form, text="Rows with no Source that share a PG value are "
                             "grouped onto one OWNER INPUT NEEDED page.",
                  foreground="#666666").grid(row=2, column=2, columnspan=2, sticky="w")
        ttk.Entry(form, textvariable=self.field_vars["DESCRIPTION2"]).grid(
            row=3, column=1, columnspan=3, sticky="we", padx=4)
        ttk.Entry(form, textvariable=self.field_vars["DESCRIPTION3"]).grid(
            row=4, column=1, columnspan=3, sticky="we", padx=4)
        form.columnconfigure(3, weight=1)

        btns = ttk.Frame(t)
        btns.pack(fill="x", pady=6)
        self.add_btn = ttk.Button(btns, text="Add row", command=self.on_add)
        self.add_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Cancel edit",
                                     command=self.on_cancel_edit)
        ttk.Button(btns, text="Edit selected", command=self.on_edit).pack(
            side="left", padx=6)
        ttk.Button(btns, text="Delete selected", command=self.on_delete).pack(
            side="left")
        ttk.Button(btns, text="Clear all", command=self.on_clear).pack(
            side="left", padx=6)

        self.tree = ttk.Treeview(t, columns=TREE_COLS, show="headings", height=8)
        self.tree.heading("key", text="KEY")
        self.tree.heading("description", text="DESCRIPTION")
        self.tree.heading("source", text="SOURCE")
        self.tree.column("key", width=80, stretch=False)
        self.tree.column("description", width=280)
        self.tree.column("source", width=380)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.on_edit())

    # ── Import tab ────────────────────────────────────────────────────────
    def _build_import_tab(self):
        t = self.import_tab
        row = ttk.Frame(t)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="Schedule (.xlsx):").pack(side="left")
        self.xlsx_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.xlsx_var).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Browse...", command=self.on_browse_xlsx).pack(side="left")
        ttk.Button(t, text="Load rows for review",
                   command=self.on_load_rows).pack(anchor="w", pady=(2, 6))
        ttk.Label(t, text="Pick a schedule that already has KEY / DESCRIPTION / "
                          "PATH columns populated. 'Load rows for review' opens "
                          "it in the Manual entry tab so you can edit rows "
                          "before generating; or click Generate binder to use "
                          "the file as-is.").pack(anchor="w")

    def on_load_rows(self):
        xlsx_path = self.xlsx_var.get().strip()
        if not xlsx_path or not os.path.exists(xlsx_path):
            messagebox.showwarning("No schedule", "Choose an existing .xlsx schedule first.")
            return
        try:
            loaded = excel_reader.load_rows(xlsx_path)
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Could not read schedule", str(e))
            return
        if not loaded:
            messagebox.showinfo("Empty schedule", "No rows with a KEY were found.")
            return
        if self.rows and not messagebox.askyesno(
                "Replace rows", f"Replace the {len(self.rows)} existing row(s) "
                f"with the {len(loaded)} imported row(s)?"):
            return
        self.rows = loaded
        self.on_cancel_edit()
        self._refresh_tree()
        self.tabs.select(self.manual_tab)
        self._log(f"Loaded {len(loaded)} row(s) from {os.path.basename(xlsx_path)} "
                  "for review - edit as needed, then Generate binder.")

    # ── Row helpers ───────────────────────────────────────────────────────
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            src = r["PATH"] or "(owner input needed)"
            self.tree.insert("", "end", iid=str(i),
                             values=(r["KEY"], r["DESCRIPTION"], src))

    def _selected_index(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def on_add(self):
        row = {k: v.get().strip() for k, v in self.field_vars.items()}
        if not row["KEY"]:
            messagebox.showwarning("Missing KEY", "KEY is required.")
            return
        if self.editing is None:
            self.rows.append(row)
        else:
            self.rows[self.editing] = row
            self._set_editing(None)
        for v in self.field_vars.values():
            v.set("")
        self._refresh_tree()

    def on_edit(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Edit row", "Select a row to edit first.")
            return
        for k, v in self.field_vars.items():
            v.set(self.rows[idx].get(k, ""))
        self._set_editing(idx)

    def _set_editing(self, idx: int | None):
        self.editing = idx
        if idx is None:
            self.add_btn.configure(text="Add row")
            self.cancel_btn.pack_forget()
        else:
            self.add_btn.configure(text=f"Update row {idx + 1}")
            self.cancel_btn.pack(side="left", padx=6)

    def on_cancel_edit(self):
        for v in self.field_vars.values():
            v.set("")
        self._set_editing(None)

    def on_delete(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Delete row", "Select a row to delete first.")
            return
        self.rows.pop(idx)
        if self.editing is not None:
            self.on_cancel_edit()
        self._refresh_tree()

    def on_clear(self):
        if self.rows and not messagebox.askyesno("Clear all", "Remove all rows?"):
            return
        self.rows.clear()
        self.on_cancel_edit()
        self._refresh_tree()

    def on_browse_pdf(self):
        path = filedialog.askopenfilename(
            title="Select a product spec sheet (PDF)",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.field_vars["PATH"].set(path)

    def on_browse_xlsx(self):
        path = filedialog.askopenfilename(
            title="Select a schedule spreadsheet",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")])
        if path:
            self.xlsx_var.set(path)

    # ── Generation ────────────────────────────────────────────────────────
    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_log(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple):  # ("done", output_path_or_None)
                    _, out = item
                    self.gen_btn.configure(state="normal")
                    if out:
                        self.last_output = out
                        self.open_btn.configure(state="normal")
                else:
                    self._log(item)
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log)

    def on_generate(self):
        manual = self.tabs.index(self.tabs.select()) == 0
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        base = pipeline.unique_output_base(
            self.project_var.get() or "Untitled Project", self.prepared_var.get())
        pdf_path = base + ".pdf"

        if manual:
            if not self.rows:
                messagebox.showwarning("No rows", "Add at least one product row first.")
                return
            xlsx_path = base + ".xlsx"
            excel_reader.save_schedule(self.rows, xlsx_path)
            self._log(f"Saved schedule: {xlsx_path}")
        else:
            xlsx_path = self.xlsx_var.get().strip()
            if not xlsx_path or not os.path.exists(xlsx_path):
                messagebox.showwarning(
                    "No schedule", "Choose an existing .xlsx schedule first.")
                return

        self.gen_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        args = (xlsx_path, pdf_path,
                self.project_var.get() or "Untitled Project",
                self.prepared_var.get(), self.draft_var.get())
        threading.Thread(target=self._worker, args=args, daemon=True).start()

    def _worker(self, xlsx_path, pdf_path, project, prepared, draft):
        out = None
        try:
            results = pipeline.generate_from_xlsx(
                xlsx_path, pdf_path, project, prepared,
                log=self.log_queue.put, draft=draft)
            ok = sum(1 for r in results if not r.error)
            self.log_queue.put(f"Done: {ok}/{len(results)} product group(s) succeeded.")
            out = pdf_path
        except PermissionError:
            self.log_queue.put(
                "ERROR: could not read the schedule - is it open in Excel?")
        except Exception as e:
            self.log_queue.put(f"ERROR: {e}")
        self.log_queue.put(("done", out))

    def on_open(self):
        if self.last_output and os.path.exists(self.last_output):
            os.startfile(self.last_output)  # noqa: S606 (Windows open)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    BinderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
