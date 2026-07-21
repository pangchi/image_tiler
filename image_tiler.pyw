"""
Image Tiler
-----------
Drag and drop multiple JPG/PNG files into the window, arrange them,
and save them tiled into a single combined image.

Dependencies (auto-installed on first run if missing):
    tkinterdnd2, Pillow

Run:
    python image_tiler.pyw
"""

import os
import sys
import subprocess


def _ensure_deps():
    """Install missing dependencies automatically."""
    missing = []
    try:
        import tkinterdnd2  # noqa: F401
    except ImportError:
        missing.append("tkinterdnd2")
    try:
        import PIL  # noqa: F401
    except ImportError:
        missing.append("pillow")

    if missing:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", *missing]
        )


_ensure_deps()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}


def parse_dnd_files(data: str):
    """Parse the raw string tkinterdnd2 gives us into a list of paths.
    Handles paths with spaces (they arrive wrapped in {curly braces})."""
    paths = []
    buf = ""
    in_brace = False
    for ch in data:
        if ch == "{":
            in_brace = True
            buf = ""
        elif ch == "}":
            in_brace = False
            paths.append(buf)
            buf = ""
        elif ch == " " and not in_brace:
            if buf:
                paths.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        paths.append(buf)
    return paths


class ImageEntry:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.thumb = None  # ImageTk.PhotoImage for the listbox-adjacent preview
        self.width = None
        self.height = None
        try:
            with Image.open(path) as img:
                self.width, self.height = img.size
        except Exception:
            pass


class ImageTilerApp:
    THUMB_LIST_SIZE = (48, 48)

    def __init__(self, root):
        self.root = root
        self.root.title("Image Tiler")
        self.root.geometry("880x600")
        self.root.minsize(700, 480)

        self.entries = []  # list[ImageEntry], in tile order
        self.bg_color = "#FFFFFF"
        self.preview_photo = None  # keep a reference so it isn't garbage collected

        self._build_ui()
        self._register_dnd()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(1, weight=1)

        # ---- Left: file list & controls ----
        left = ttk.Frame(main)
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        drop_label = tk.Label(
            left,
            text="Drag & drop JPG / PNG files here\n(or use 'Add Files...')",
            relief="ridge",
            bd=2,
            bg="#f0f0f0",
            fg="#555555",
            height=4,
            justify="center",
        )
        drop_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.drop_label = drop_label

        list_frame = ttk.Frame(left)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, selectmode="extended", activestyle="dotbox")
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._update_preview())

        btn_row = ttk.Frame(left)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(btn_row, text="Add Files...", command=self.add_files_dialog).pack(side="left")
        ttk.Button(btn_row, text="Remove", command=self.remove_selected).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Clear All", command=self.clear_all).pack(side="left")

        order_row = ttk.Frame(left)
        order_row.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(order_row, text="Move Up", command=lambda: self.move_selected(-1)).pack(side="left")
        ttk.Button(order_row, text="Move Down", command=lambda: self.move_selected(1)).pack(side="left", padx=4)

        # ---- Right: layout options & preview ----
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        opts = ttk.LabelFrame(right, text="Tile Options", padding=10)
        opts.grid(row=0, column=0, sticky="ew")
        for i in range(4):
            opts.columnconfigure(i, weight=1)

        ttk.Label(opts, text="Columns:").grid(row=0, column=0, sticky="w")
        self.columns_var = tk.IntVar(value=0)  # 0 = auto (square-ish)
        ttk.Spinbox(opts, from_=0, to=20, width=6, textvariable=self.columns_var,
                    command=self._update_preview).grid(row=0, column=1, sticky="w", padx=(4, 16))
        ttk.Label(opts, text="(0 = auto)").grid(row=0, column=2, sticky="w")

        ttk.Label(opts, text="Cell size (px):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.cell_size_var = tk.IntVar(value=300)
        cell_spin = ttk.Spinbox(opts, from_=32, to=2000, increment=10, width=6,
                                 textvariable=self.cell_size_var,
                                 command=self._update_preview)
        cell_spin.grid(row=1, column=1, sticky="w", padx=(4, 16), pady=(8, 0))
        # Any manual interaction with the spinbox turns off auto-suggest,
        # so the user's chosen value isn't overwritten on the next add/remove.
        cell_spin.bind("<KeyRelease>", lambda e: self.auto_cell_size_var.set(False))
        cell_spin.bind("<ButtonRelease-1>", lambda e: self.auto_cell_size_var.set(False))

        self.auto_cell_size_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text="Auto-suggest from image sizes",
            variable=self.auto_cell_size_var,
            command=lambda: self._suggest_cell_size(force=True),
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(opts, text="Spacing (px):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.spacing_var = tk.IntVar(value=8)
        ttk.Spinbox(opts, from_=0, to=200, width=6, textvariable=self.spacing_var,
                    command=self._update_preview).grid(row=2, column=1, sticky="w", padx=(4, 16), pady=(8, 0))

        self.fit_mode_var = tk.StringVar(value="contain")
        ttk.Label(opts, text="Fit mode:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        fit_combo = ttk.Combobox(
            opts, textvariable=self.fit_mode_var, state="readonly", width=10,
            values=["contain", "cover", "stretch"]
        )
        fit_combo.grid(row=3, column=1, sticky="w", padx=(4, 16), pady=(8, 0))
        fit_combo.bind("<<ComboboxSelected>>", lambda e: self._update_preview())

        ttk.Button(opts, text="Background Color...", command=self._choose_bg_color).grid(
            row=3, column=2, columnspan=2, sticky="e", pady=(8, 0)
        )
        self.bg_swatch = tk.Label(opts, bg=self.bg_color, width=4, relief="sunken")
        self.bg_swatch.grid(row=3, column=4, sticky="e", padx=(4, 0), pady=(8, 0))

        for var in (self.columns_var, self.spacing_var, self.cell_size_var):
            var.trace_add("write", lambda *a: self._update_preview())

        # Preview
        preview_frame = ttk.LabelFrame(right, text="Preview", padding=6)
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        right.rowconfigure(1, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_frame, bg="#dddddd", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())

        # Bottom action row
        bottom = ttk.Frame(right)
        bottom.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.status_var = tk.StringVar(value="No images loaded")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")
        ttk.Button(bottom, text="Save Tiled Image...", command=self.save_tiled_image).pack(side="right")

    def _register_dnd(self):
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind("<<Drop>>", self._on_drop)

    # -------------------------------------------------------------- Events
    def _on_drop(self, event):
        paths = parse_dnd_files(event.data)
        self._add_paths(paths)

    def add_files_dialog(self):
        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All files", "*.*")],
        )
        if paths:
            self._add_paths(paths)

    def _add_paths(self, paths):
        added = 0
        skipped = 0
        for p in paths:
            p = os.path.normpath(p)
            if os.path.isdir(p):
                # Allow dropping a folder: add all supported images inside it
                for fname in sorted(os.listdir(p)):
                    fpath = os.path.join(p, fname)
                    if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() in SUPPORTED_EXTS:
                        self.entries.append(ImageEntry(fpath))
                        added += 1
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext in SUPPORTED_EXTS and os.path.isfile(p):
                self.entries.append(ImageEntry(p))
                added += 1
            else:
                skipped += 1

        self._refresh_listbox()
        self._suggest_cell_size()
        self._update_preview()
        msg = f"Added {added} image(s)."
        if skipped:
            msg += f" Skipped {skipped} unsupported file(s)."
        self.status_var.set(msg)

    def _suggest_cell_size(self, force=False):
        """Auto-detect a sensible cell size from the dimensions of the
        loaded images and fill in the Cell size field. Runs automatically
        after files are added/removed as long as auto-suggest is on
        (or when force=True, e.g. the checkbox was just re-enabled)."""
        if not (self.auto_cell_size_var.get() or force):
            return
        sizes = [min(e.width, e.height) for e in self.entries if e.width and e.height]
        if not sizes:
            return
        sizes.sort()
        mid = sizes[len(sizes) // 2]  # median smaller-dimension
        suggested = max(80, min(1200, round(mid / 10) * 10))
        self.cell_size_var.set(suggested)

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        for idx in reversed(sel):
            del self.entries[idx]
        self._refresh_listbox()
        self._suggest_cell_size()
        self._update_preview()

    def clear_all(self):
        self.entries.clear()
        self._refresh_listbox()
        self._update_preview()

    def move_selected(self, direction):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        indices = sel if direction < 0 else list(reversed(sel))
        new_selection = []
        for idx in indices:
            new_idx = idx + direction
            if 0 <= new_idx < len(self.entries):
                self.entries[idx], self.entries[new_idx] = self.entries[new_idx], self.entries[idx]
                new_selection.append(new_idx)
            else:
                new_selection.append(idx)
        self._refresh_listbox()
        for idx in new_selection:
            self.listbox.selection_set(idx)
        self._update_preview()

    def _choose_bg_color(self):
        color = colorchooser.askcolor(color=self.bg_color, title="Choose background color")
        if color and color[1]:
            self.bg_color = color[1]
            self.bg_swatch.configure(bg=self.bg_color)
            self._update_preview()

    def _refresh_listbox(self):
        self.listbox.delete(0, "end")
        for e in self.entries:
            self.listbox.insert("end", e.name)

    # ------------------------------------------------------------- Layout
    def _grid_dims(self, n):
        cols = self.columns_var.get()
        if cols and cols > 0:
            cols = min(cols, n) if n > 0 else cols
            rows = (n + cols - 1) // cols
            return cols, rows
        # auto: roughly square grid
        import math
        cols = max(1, math.ceil(math.sqrt(n)))
        rows = math.ceil(n / cols)
        return cols, rows

    def _place_image(self, canvas_img, cell_w, cell_h):
        """Resize a PIL image to fit a cell according to fit mode.
        Returns (resized_image, x_offset, y_offset) for centering."""
        mode = self.fit_mode_var.get()
        img = canvas_img
        iw, ih = img.size
        if mode == "stretch":
            return img.resize((cell_w, cell_h), Image.LANCZOS), 0, 0

        scale_contain = min(cell_w / iw, cell_h / ih)
        scale_cover = max(cell_w / iw, cell_h / ih)
        scale = scale_contain if mode == "contain" else scale_cover
        new_w, new_h = max(1, int(iw * scale)), max(1, int(ih * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        if mode == "cover":
            # crop to cell size, centered
            left = max(0, (new_w - cell_w) // 2)
            top = max(0, (new_h - cell_h) // 2)
            resized = resized.crop((left, top, left + cell_w, top + cell_h))
            return resized, 0, 0

        # contain: center within cell
        x_off = (cell_w - new_w) // 2
        y_off = (cell_h - new_h) // 2
        return resized, x_off, y_off

    def build_tiled_image(self):
        if not self.entries:
            return None
        n = len(self.entries)
        cols, rows = self._grid_dims(n)
        cell = self.cell_size_var.get()
        spacing = self.spacing_var.get()

        canvas_w = cols * cell + (cols + 1) * spacing
        canvas_h = rows * cell + (rows + 1) * spacing
        canvas = Image.new("RGB", (canvas_w, canvas_h), self.bg_color)

        for idx, entry in enumerate(self.entries):
            try:
                img = Image.open(entry.path).convert("RGB")
            except Exception:
                continue
            resized, x_off, y_off = self._place_image(img, cell, cell)
            r, c = divmod(idx, cols)
            x = spacing + c * (cell + spacing) + x_off
            y = spacing + r * (cell + spacing) + y_off
            canvas.paste(resized, (x, y))

        return canvas

    def _update_preview(self):
        self.preview_canvas.delete("all")
        tiled = self.build_tiled_image()
        if tiled is None:
            self.status_var.set("No images loaded")
            return

        cw = self.preview_canvas.winfo_width() or 500
        ch = self.preview_canvas.winfo_height() or 400
        scale = min(cw / tiled.width, ch / tiled.height, 1.0)
        disp_w, disp_h = max(1, int(tiled.width * scale)), max(1, int(tiled.height * scale))
        disp_img = tiled.resize((disp_w, disp_h), Image.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(disp_img)
        x = (cw - disp_w) // 2
        y = (ch - disp_h) // 2
        self.preview_canvas.create_image(x, y, anchor="nw", image=self.preview_photo)
        self.status_var.set(f"{len(self.entries)} image(s) — output {tiled.width}x{tiled.height}px")

    # --------------------------------------------------------------- Save
    def save_tiled_image(self):
        if not self.entries:
            messagebox.showinfo("No images", "Add some images first.")
            return
        tiled = self.build_tiled_image()
        path = filedialog.asksaveasfilename(
            title="Save tiled image",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
        )
        if not path:
            return
        try:
            if path.lower().endswith((".jpg", ".jpeg")):
                tiled.save(path, quality=95)
            else:
                tiled.save(path)
            messagebox.showinfo("Saved", f"Tiled image saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Error saving image", str(exc))


def main():
    root = TkinterDnD.Tk()
    ImageTilerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
