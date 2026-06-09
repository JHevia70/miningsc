import tkinter as tk
from tkinter import ttk, filedialog
from . import config as cfg_mod


class ConfigWindow:
    def __init__(self, parent_root, on_apply):
        """
        parent_root : tk.Tk  — overlay root, used to schedule after() calls
        on_apply    : callable(cfg) — called with new config dict when user clicks Apply
        """
        self._root = parent_root
        self._on_apply = on_apply
        self._win = None

    def open(self):
        if self._win and self._win.winfo_exists():
            self._win.lift()
            return
        self._build()

    def _build(self):
        cfg = cfg_mod.load()

        win = tk.Toplevel(self._root)
        win.title("MiningSC Scanner — Configuración")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg="#0d1f33")
        self._win = win

        style = ttk.Style(win)
        style.theme_use("clam")
        style.configure(".", background="#0d1f33", foreground="#e0e0e0",
                        fieldbackground="#1a2e45", font=("Electrolize", 10))
        style.configure("TLabel",  background="#0d1f33", foreground="#e0e0e0")
        style.configure("TFrame",  background="#0d1f33")
        style.configure("TButton", background="#1e4a6e", foreground="#e0e0e0",
                        padding=4)
        style.map("TButton", background=[("active", "#2a6090")])
        style.configure("TCombobox", fieldbackground="#1a2e45", foreground="#e0e0e0")
        style.configure("TScale",    background="#0d1f33")

        f = ttk.Frame(win, padding=16)
        f.grid(sticky="nsew")

        row = 0

        # --- Text alignment ---
        ttk.Label(f, text="Alineación del texto").grid(row=row, column=0, sticky="w", pady=4)
        align_var = tk.StringVar(value=cfg.get("text_align", "right"))
        align_cb = ttk.Combobox(f, textvariable=align_var, values=["left", "right"],
                                state="readonly", width=10)
        align_cb.grid(row=row, column=1, sticky="w", padx=8, pady=4)
        row += 1

        # --- Transparency ---
        ttk.Label(f, text="Transparencia").grid(row=row, column=0, sticky="w", pady=4)
        alpha_var = tk.DoubleVar(value=cfg.get("alpha", 0.50))
        alpha_label = ttk.Label(f, text=f"{alpha_var.get():.0%}")
        alpha_label.grid(row=row, column=2, sticky="w", padx=4)

        def _alpha_changed(val):
            alpha_label.config(text=f"{float(val):.0%}")

        alpha_scale = ttk.Scale(f, from_=0.1, to=1.0, orient="horizontal",
                                variable=alpha_var, length=160,
                                command=_alpha_changed)
        alpha_scale.grid(row=row, column=1, sticky="w", padx=8, pady=4)
        row += 1

        # --- Font size ---
        ttk.Label(f, text="Tamaño de fuente").grid(row=row, column=0, sticky="w", pady=4)
        size_var = tk.IntVar(value=cfg.get("font_size", 11))
        size_spin = tk.Spinbox(f, from_=8, to=20, textvariable=size_var, width=5,
                               bg="#1a2e45", fg="#e0e0e0", insertbackground="#e0e0e0",
                               buttonbackground="#1e4a6e", relief="flat")
        size_spin.grid(row=row, column=1, sticky="w", padx=8, pady=4)
        row += 1

        # --- Upload toggle ---
        ttk.Label(f, text="Enviar scans a la BD").grid(row=row, column=0, sticky="w", pady=4)
        upload_var = tk.BooleanVar(value=cfg.get("upload", True))
        ttk.Checkbutton(f, variable=upload_var).grid(row=row, column=1, sticky="w", padx=8)
        row += 1

        # --- Temp folder ---
        ttk.Label(f, text="Carpeta temporal").grid(row=row, column=0, sticky="w", pady=4)
        tempdir_var = tk.StringVar(value=cfg.get("temp_dir", ""))
        tempdir_entry = tk.Entry(f, textvariable=tempdir_var, width=28,
                                 bg="#1a2e45", fg="#e0e0e0", insertbackground="#e0e0e0",
                                 relief="flat")
        tempdir_entry.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

        def _browse():
            folder = filedialog.askdirectory(
                title="Seleccionar carpeta temporal",
                initialdir=tempdir_var.get() or None,
                parent=win,
            )
            if folder:
                tempdir_var.set(folder)

        ttk.Button(f, text="…", width=3, command=_browse).grid(row=row, column=2, padx=4)
        ttk.Label(f, text='Vacío = temp del sistema', foreground="#888888",
                  font=("Electrolize", 8)).grid(row=row+1, column=1, sticky="w", padx=8)
        row += 2

        # --- Separator ---
        ttk.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=3,
                                                    sticky="ew", pady=10)
        row += 1

        # --- Buttons ---
        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="e")

        def _apply():
            new_cfg = cfg_mod.load()
            new_cfg["text_align"]     = align_var.get()
            new_cfg["alpha"]          = round(alpha_var.get(), 2)
            new_cfg["font_size"]      = size_var.get()
            new_cfg["temp_dir"]       = tempdir_var.get().strip()
            new_cfg["upload"]     = upload_var.get()
            cfg_mod.save(new_cfg)
            self._on_apply(new_cfg)

        def _ok():
            _apply()
            win.destroy()

        ttk.Button(btn_frame, text="Aplicar", command=_apply).grid(row=0, column=0, padx=4)
        ttk.Button(btn_frame, text="Aceptar", command=_ok).grid(row=0, column=1, padx=4)
        ttk.Button(btn_frame, text="Cancelar", command=win.destroy).grid(row=0, column=2, padx=4)

        win.update_idletasks()
        # Center on screen
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w  = win.winfo_width()
        h  = win.winfo_height()
        win.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")
