"""
app.py — VideoFramesPDF
Application de bureau : extrait une image toutes les N secondes d'une vidéo,
laisse l'utilisateur supprimer celles qu'il ne veut pas, puis génère un PDF
contenant toutes les images dans l'ordre choisi.

Lancement :  python app.py
"""

import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdfwriter import PAGE_SIZES, PdfBuilder          # noqa: E402
import video_frames as vf                              # noqa: E402

APP_NAME = "VideoFramesPDF"
VERSION = "1.0"


# --------------------------------------------------------------------------
#  Thème
# --------------------------------------------------------------------------
BG = "#12141a"
BG2 = "#1b1e26"
FG = "#e7e9ee"
MUTED = "#9aa1b1"
ACCENT = "#3b82f6"
ACCENT2 = "#22c55e"
DANGER = "#ef4444"

THUMB_W, THUMB_H = 210, 120


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s %s — Images de vidéo en PDF" % (APP_NAME, VERSION))
        self.geometry("1240x800")
        self.minsize(940, 620)
        self.configure(bg=BG)
        self._style()

        # état
        self.video_path = tk.StringVar()
        self.interval = tk.StringVar(value="4")
        self.status = tk.StringVar(value="Choisissez une vidéo pour commencer.")
        self.progress = tk.DoubleVar(value=0.0)
        self.page_fmt = tk.StringVar(value="A4 portrait")
        self.quality = tk.IntVar(value=88)
        self.use_cover = tk.BooleanVar(value=True)
        self.show_times = tk.BooleanVar(value=True)
        self.pdf_name = tk.StringVar(value="")
        self.out_dir = tk.StringVar(value="")
        self.count_info = tk.StringVar(value="0 image")

        self.items = []            # [{path,time,index,thumb,photom,selected}]
        self.cancel_event = threading.Event()
        self.worker = None
        self.msg_q = queue.Queue()
        self.tmp_dir = None

        self._build_ui()
        self._update_count()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------- Style
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=BG2)
        s.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("Muted.TLabel", background=BG, foreground=MUTED,
                    font=("Segoe UI", 9))
        s.configure("Title.TLabel", background=BG2, foreground=FG,
                    font=("Segoe UI", 15, "bold"))
        s.configure("Btn.TButton", background="#2a2e39", foreground=FG,
                    font=("Segoe UI", 10), padding=(10, 6),
                    bordercolor="#2a2e39", lightcolor="#2a2e39",
                    darkcolor="#2a2e39")
        s.map("Btn.TButton", background=[("active", "#3b4152"),
                                        ("pressed", "#3b4152")],
              foreground=[("active", "#ffffff")])
        s.configure("TButton", font=("Segoe UI", 10), padding=(10, 6),
                    background="#2a2e39", foreground=FG,
                    bordercolor="#2a2e39", lightcolor="#2a2e39",
                    darkcolor="#2a2e39")
        s.map("TButton", background=[("active", "#3b4152")],
              foreground=[("active", "#ffffff")])
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    font=("Segoe UI", 10, "bold"), padding=(14, 8),
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT)
        s.map("Accent.TButton", background=[("active", "#2f6fd0")])
        s.configure("Danger.TButton", background=DANGER, foreground="#ffffff",
                    padding=(10, 5), bordercolor=DANGER, lightcolor=DANGER,
                    darkcolor=DANGER)
        s.map("Danger.TButton", background=[("active", "#dc2626")])
        s.configure("Small.TButton", font=("Segoe UI", 9), padding=(6, 3),
                    background="#3a3f4d", foreground=FG,
                    bordercolor="#3a3f4d", lightcolor="#3a3f4d",
                    darkcolor="#3a3f4d")
        s.map("Small.TButton", background=[("active", "#4a5062")])
        s.configure("TCheckbutton", background=BG2, foreground=FG,
                    font=("Segoe UI", 9), indicatorcolor=ACCENT2,
                    indicatorbackground="#12141a",
                    indicatormargin=(0, 0, 8, 0))
        s.map("TCheckbutton", background=[("active", BG2)],
              foreground=[("active", "#ffffff")],
              indicatorcolor=[("selected", ACCENT2), ("active", ACCENT2),
                              ("disabled", "#4a5062")],
              indicatorbackground=[("selected", "#12141a"),
                                  ("active", "#12141a")])
        s.configure("TProgressbar", background=ACCENT2, troughcolor="#2a2e39",
                    borderwidth=0, thickness=10)
        s.configure("TCombobox", fieldbackground=BG2, background="#3a3f4d",
                    foreground=FG, arrowcolor=FG, bordercolor="#3a3f4d",
                    lightcolor=BG2, darkcolor=BG2, insertcolor=FG,
                    padding=(4, 3))
        s.map("TCombobox", fieldbackground=[("readonly", BG2)],
              foreground=[("readonly", FG)], arrowcolor=[("readonly", FG)],
              selectbackground=[("readonly", BG2)],
              selectforeground=[("readonly", FG)])
        s.configure("TRadiobutton", background=BG2, foreground=FG,
                    font=("Segoe UI", 9))
        s.configure("TSpinbox", fieldbackground=BG2, background="#3a3f4d",
                    foreground=FG, arrowcolor=FG, bordercolor="#3a3f4d",
                    lightcolor=BG2, darkcolor=BG2, insertcolor=FG)
        s.map("TSpinbox", fieldbackground=[("readonly", BG2)],
              foreground=[("readonly", FG)], arrowcolor=[("readonly", FG)])

    # --------------------------------------------------------------- UI
    def _build_ui(self):
        # ---------------- barre supérieure
        top = tk.Frame(self, bg=BG2)
        top.pack(side="top", fill="x")
        inner = tk.Frame(top, bg=BG2)
        inner.pack(fill="x", padx=14, pady=12)

        tk.Label(inner, text="VIDEOFRAMES PDF", bg=BG2, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(inner, text="  |  extraire une image toutes les N secondes "
                              "→ PDF", bg=BG2, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")

        # ---------------- barre de sélection de fichier
        bar = tk.Frame(self, bg=BG)
        bar.pack(side="top", fill="x", padx=14, pady=(12, 6))

        tk.Label(bar, text="Vidéo :", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.entry = tk.Entry(bar, textvariable=self.video_path, bg=BG2,
                               fg=FG, insertbackground=FG, relief="flat",
                               font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, padx=(6, 8),
                        ipady=6)
        ttk.Button(bar, text="Parcourir…", style="Btn.TButton",
                   command=self.choose_video).pack(side="left")
        ttk.Button(bar, text="Ouvrir le dossier", style="Btn.TButton",
                   command=self.open_video_folder).pack(side="left", padx=(6, 0))

        # ---------------- options + boutons
        opts = tk.Frame(self, bg=BG)
        opts.pack(side="top", fill="x", padx=14, pady=(0, 6))

        tk.Label(opts, text="Intervalle :", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        ttk.Spinbox(opts, from_=0.5, to=600, increment=0.5, width=6,
                    textvariable=self.interval).pack(side="left", padx=(4, 2))
        tk.Label(opts, text="secondes", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left", padx=(2, 16))
        tk.Label(opts, text="Qualité JPEG :", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        ttk.Spinbox(opts, from_=40, to=100, increment=1, width=5,
                    textvariable=self.quality).pack(side="left", padx=(4, 16))

        self.btn_extract = ttk.Button(opts, text="1 · Extraire les images",
                                      style="Accent.TButton",
                                      command=self.start_extract)
        self.btn_extract.pack(side="left")
        self.btn_cancel = ttk.Button(opts, text="Annuler", style="Btn.TButton", state="disabled",
                                     command=self.cancel_extract)
        self.btn_cancel.pack(side="left", padx=(8, 0))

        # ---------------- barre de progression
        prog = tk.Frame(self, bg=BG)
        prog.pack(side="top", fill="x", padx=14, pady=(0, 8))
        self.pbar = ttk.Progressbar(prog, variable=self.progress, maximum=1.0)
        self.pbar.pack(side="left", fill="x", expand=True)
        tk.Label(prog, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))

        # ---------------- zone centrale : galerie
        mid = tk.Frame(self, bg=BG)
        mid.pack(side="top", fill="both", expand=True, padx=14, pady=(0, 6))

        self.canvas = tk.Canvas(mid, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.grid_frame = tk.Frame(self.canvas, bg=BG)
        self._grid_window = self.canvas.create_window((0, 0),
                                                      window=self.grid_frame,
                                                      anchor="nw")
        self.grid_frame.bind("<Configure>", self._on_grid_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        # ---------------- barre d'actions galerie
        acts = tk.Frame(self, bg=BG)
        acts.pack(side="top", fill="x", padx=14, pady=(0, 6))
        ttk.Button(acts, text="Tout sélectionner", style="Btn.TButton",
                   command=lambda: self.set_all(True)).pack(side="left")
        ttk.Button(acts, text="Tout désélectionner", style="Btn.TButton",
                   command=lambda: self.set_all(False)).pack(side="left", padx=6)
        ttk.Button(acts, text="Supprimer la sélection", style="Danger.TButton",
                   command=self.delete_selected).pack(side="left")
        ttk.Button(acts, text="Tout supprimer", style="Btn.TButton",
                   command=self.delete_all).pack(side="left", padx=6)
        ttk.Checkbutton(acts, text="Afficher l’horodatage",
                        variable=self.show_times,
                        command=self._refresh_gallery).pack(side="left",
                                                            padx=(12, 0))
        tk.Label(acts, textvariable=self.count_info, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right")

        # ---------------- barre finale : PDF
        bottom = tk.Frame(self, bg=BG2)
        bottom.pack(side="bottom", fill="x")
        binner = tk.Frame(bottom, bg=BG2)
        binner.pack(fill="x", padx=14, pady=10)

        ttk.Label(binner, text="Format :").pack(side="left")
        cb = ttk.Combobox(binner, textvariable=self.page_fmt, width=16,
                          state="readonly", values=list(PAGE_SIZES.keys()))
        cb.pack(side="left", padx=(4, 12))
        ttk.Checkbutton(binner, text="Page de garde", variable=self.use_cover
                        ).pack(side="left", padx=(0, 12))
        tk.Label(binner, text="Nom du PDF :", bg=BG2, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(binner, textvariable=self.pdf_name, bg=BG, fg=FG,
                 insertbackground=FG, relief="flat", width=24,
                 font=("Segoe UI", 10)).pack(side="left", padx=6, ipady=5)
        ttk.Button(binner, text="Choisir le dossier…", style="Btn.TButton",
                   command=self.choose_out_dir).pack(side="left")
        tk.Label(binner, textvariable=self.out_dir, bg=BG2, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=6)

        self.btn_pdf = ttk.Button(binner, text="2 · Générer le PDF",
                                   style="Accent.TButton",
                                   command=self.start_pdf)
        self.btn_pdf.pack(side="right")

        self._empty_label()

    def _empty_label(self):
        self.empty = tk.Label(self.grid_frame,
                              text="Aucune image pour le moment.\n\n"
                                   "1. Choisissez votre vidéo\n"
                                   "2. Cliquez sur « Extraire les images »",
                              bg=BG, fg=MUTED, font=("Segoe UI", 12),
                              justify="center")
        self.empty.pack(pady=60)

    # ------------------------------------------------------- Galerie
    def _on_grid_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self.canvas.itemconfigure(self._grid_window, width=e.width)
        self._relayout()

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _columns(self):
        try:
            w = self.canvas.winfo_width()
        except Exception:
            w = 1000
        if w < 10:
            w = 1000
        return max(1, int(w // (THUMB_W + 18)))

    def _relayout(self):
        cols = self._columns()
        for i, card in enumerate(getattr(self, "cards", [])):
            card.grid(row=i // cols, column=i % cols, padx=8, pady=8,
                      sticky="n")

    def _refresh_gallery(self):
        """Reconstruit toute la galerie (appelé après ajout/suppression)."""
        for card in getattr(self, "cards", []):
            card.destroy()
        self.cards = []

        if not self.items:
            if not hasattr(self, "empty") or not self.empty.winfo_exists():
                self._empty_label()
            else:
                self.empty.pack(pady=60)
            self._update_count()
            return

        if hasattr(self, "empty") and self.empty.winfo_exists():
            self.empty.destroy()

        from PIL import Image, ImageTk
        self.cards = []
        for item in self.items:
            card = tk.Frame(self.grid_frame, bg=BG2,
                            highlightbackground="#2a2e39", highlightthickness=1)
            thumb = item.get("photom")
            if thumb is None:
                try:
                    im = Image.open(item["path"])
                    im.thumbnail((THUMB_W, THUMB_H))
                    thumb = ImageTk.PhotoImage(im)
                    item["photom"] = thumb
                except Exception:
                    thumb = None

            var = tk.BooleanVar(value=item["selected"])
            item["var"] = var
            if thumb is not None:
                chk = ttk.Checkbutton(card, image=thumb, variable=var,
                                      command=lambda it=item: self._on_toggle(it))
                chk.configure(padding=(0, 0))
            else:
                chk = ttk.Checkbutton(card, variable=var,
                                      command=lambda it=item: self._on_toggle(it))
            chk.pack(padx=6, pady=(6, 0))
            chk.bind("<Double-1>", lambda e, it=item: self.preview(it))

            lab = tk.Label(card, text=vf._hhmmss(item["time"])
                           if self.show_times.get() else "",
                           bg=BG2, fg=MUTED, font=("Segoe UI", 9))
            lab.pack(pady=(2, 0))

            row = tk.Frame(card, bg=BG2)
            row.pack(pady=(0, 6))
            ttk.Button(row, text="↑", style="Small.TButton",
                       command=lambda it=item: self._move(it, -1)).pack(
                           side="left")
            ttk.Button(row, text="↓", style="Small.TButton",
                       command=lambda it=item: self._move(it, +1)).pack(
                           side="left", padx=4)
            ttk.Button(row, text="✕", style="Small.TButton",
                       command=lambda it=item: self._delete_item(it)).pack(
                           side="left")
            self.cards.append(card)

        self._relayout()
        self._update_count()

    def _on_toggle(self, item):
        item["selected"] = item["var"].get()
        self._update_count()

    def set_all(self, value):
        for it in self.items:
            it["selected"] = value
            if "var" in it:
                it["var"].set(value)
        self._update_count()

    def _update_count(self):
        sel = sum(1 for it in self.items if it["selected"])
        self.count_info.set("%d image(s) — %d sélectionnée(s)"
                            % (len(self.items), sel))
        if hasattr(self, "btn_pdf"):
            self.btn_pdf.state(["!disabled"] if sel and self.items else
                                ["disabled"])

    def _delete_item(self, item):
        if item in self.items:
            self.items.remove(item)
            self._refresh_gallery()

    def delete_selected(self):
        n = sum(1 for it in self.items if it["selected"])
        if not n:
            messagebox.showinfo(APP_NAME, "Aucune image sélectionnée.")
            return
        if not messagebox.askyesno(APP_NAME,
                                   "Supprimer %d image(s) de la liste ?" % n):
            return
        self.items = [it for it in self.items if not it["selected"]]
        self._refresh_gallery()

    def delete_all(self):
        if not self.items:
            return
        if not messagebox.askyesno(APP_NAME,
                                   "Supprimer toutes les %d images ?"
                                   % len(self.items)):
            return
        self.items = []
        self._refresh_gallery()

    def _move(self, item, delta):
        i = self.items.index(item)
        j = i + delta
        if 0 <= j < len(self.items):
            self.items[i], self.items[j] = self.items[j], self.items[i]
            self._refresh_gallery()

    def preview(self, item):
        try:
            from PIL import Image, ImageTk
            win = tk.Toplevel(self)
            win.title("Aperçu — " + os.path.basename(item["path"]))
            win.configure(bg=BG2)
            im = Image.open(item["path"])
            im.thumbnail((1100, 750))
            photo = ImageTk.PhotoImage(im)
            lbl = tk.Label(win, image=photo, bg=BG2)
            lbl.image = photo
            lbl.pack(padx=10, pady=10)
            tk.Label(win, text=vf._hhmmss(item["time"]), bg=BG2, fg=MUTED,
                     font=("Segoe UI", 10)).pack(pady=(0, 10))
        except Exception as e:
            messagebox.showerror(APP_NAME, "Aperçu impossible :\n%s" % e)

    # ------------------------------------------------------- Vidéo
    def choose_video(self):
        path = filedialog.askopenfilename(
            title="Choisir une vidéo",
            filetypes=[("Vidéos", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm "
                                  "*.m4v *.mpg *.mpeg *.3gp *.ts"),
                       ("Tous les fichiers", "*.*")])
        if path:
            self.video_path.set(path)
            if not self.pdf_name.get():
                base = os.path.splitext(os.path.basename(path))[0]
                self.pdf_name.set(base + "_images")
            self.status.set("Vidéo sélectionnée. Cliquez sur « Extraire ».")

    def open_video_folder(self):
        p = self.video_path.get()
        if p and os.path.exists(p):
            self._reveal(os.path.dirname(p))
        else:
            messagebox.showinfo(APP_NAME, "Aucune vidéo sélectionnée.")

    # ------------------------------------------------------- Extraction
    def start_extract(self):
        path = self.video_path.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning(APP_NAME,
                                   "Choisissez d'abord une vidéo existante.")
            return
        try:
            interval = float(self.interval.get().replace(",", "."))
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(APP_NAME,
                                   "L'intervalle doit être un nombre > 0.")
            return

        self.cancel_event.clear()
        self.progress.set(0.0)
        self.btn_extract.state(["disabled"])
        self.btn_cancel.state(["!disabled"])
        self.btn_pdf.state(["disabled"])
        self.status.set("Analyse de la vidéo…")

        if self.tmp_dir and os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.tmp_dir = tempfile.mkdtemp(prefix="vfp_")

        # Lecture des variables Tk dans le thread principal (obligatoire :
        # Tkinter n'est pas thread-safe).
        quality = int(self.quality.get())
        tmp_dir = self.tmp_dir

        def job():
            try:
                res = vf.extract_frames(
                    path, interval=interval, out_dir=tmp_dir,
                    quality=quality,
                    progress=lambda f, m: self.msg_q.put(("progress", f, m)),
                    cancel_event=self.cancel_event)
                self.msg_q.put(("done", res, None))
            except vf.Cancelled:
                self.msg_q.put(("cancelled", None, None))
            except Exception as e:
                self.msg_q.put(("error", str(e), None))

        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    def cancel_extract(self):
        self.cancel_event.set()
        self.status.set("Annulation…")

    # ------------------------------------------------------- PDF
    def choose_out_dir(self):
        d = filedialog.askdirectory(title="Dossier de destination du PDF")
        if d:
            self.out_dir.set(d)

    def start_pdf(self):
        sel = [it for it in self.items if it["selected"]]
        if not sel:
            messagebox.showwarning(APP_NAME,
                                   "Aucune image sélectionnée.")
            return
        name = self.pdf_name.get().strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Indiquez un nom de PDF.")
            return
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        folder = self.out_dir.get().strip()
        if not folder:
            folder = os.path.dirname(self.video_path.get().strip()) \
                or os.path.expanduser("~")
            self.out_dir.set(folder)
        if not os.path.isdir(folder):
            messagebox.showwarning(APP_NAME,
                                   "Le dossier de destination n'existe pas.")
            return
        out = os.path.join(folder, name)
        if os.path.exists(out):
            if not messagebox.askyesno(
                    APP_NAME, "Le fichier existe déjà.\nLe remplacer ?"):
                return

        self.btn_pdf.state(["disabled"])
        self.btn_extract.state(["disabled"])
        self.progress.set(0.0)
        self.status.set("Génération du PDF…")

        # Lecture des variables Tk dans le thread principal.
        page_fmt = self.page_fmt.get()
        use_cover = self.use_cover.get()
        video_name = os.path.basename(self.video_path.get()) or ""
        selected = list(sel)

        def job():
            try:
                size = PAGE_SIZES.get(page_fmt, PAGE_SIZES["A4 portrait"])
                builder = PdfBuilder(page_size=size, title=name,
                                     author=APP_NAME)
                if use_cover:
                    total = len(selected)
                    builder.add_cover(
                        title=os.path.splitext(name)[0],
                        subtitle="%d images extraites de la vidéo"
                                 % total,
                        footer=video_name)
                for i, item in enumerate(selected):
                    with open(item["path"], "rb") as f:
                        data = f.read()
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(data)) as im:
                        w, h = im.size
                    builder.add_image(data, w, h,
                                      caption=vf._hhmmss(item["time"]))
                    self.msg_q.put(("progress", (i + 1) / float(len(selected)),
                                    "Page %d/%d…" % (i + 1, len(selected))))
                builder.save(out)
                self.msg_q.put(("pdf_done", out, None))
            except Exception as e:
                self.msg_q.put(("error", str(e), None))

        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    # ------------------------------------------------------- Messages
    def _poll(self):
        try:
            while True:
                msg = self.msg_q.get_nowait()
                kind, a, b = (list(msg) + [None, None])[:3]
                if kind == "progress":
                    self.progress.set(a)
                    self.status.set(b)
                elif kind == "done":
                    self.items = []
                    for r in a:
                        self.items.append({"path": r["path"],
                                           "time": r["time"],
                                           "index": r["index"],
                                           "selected": True,
                                           "photom": None})
                    self._refresh_gallery()
                    self.progress.set(1.0)
                    self.status.set("%d images extraites. Supprimez celles "
                                    "que vous ne voulez pas." % len(a))
                    self.btn_extract.state(["!disabled"])
                    self.btn_cancel.state(["disabled"])
                elif kind == "cancelled":
                    self.progress.set(0.0)
                    self.status.set("Extraction annulée.")
                    self.btn_extract.state(["!disabled"])
                    self.btn_cancel.state(["disabled"])
                elif kind == "pdf_done":
                    self.progress.set(1.0)
                    self.status.set("PDF créé : %s" % a)
                    self.btn_extract.state(["!disabled"])
                    self.btn_pdf.state(["!disabled"])
                    res = messagebox.askyesno(
                        APP_NAME,
                        "PDF créé avec succès :\n\n%s\n\n%d Ko\n\n"
                        "Ouvrir le dossier ?" % (a, os.path.getsize(a) // 1024))
                    if res:
                        self._reveal(os.path.dirname(a))
                elif kind == "error":
                    self.progress.set(0.0)
                    self.status.set("Erreur.")
                    self.btn_extract.state(["!disabled"])
                    self.btn_cancel.state(["disabled"])
                    self.btn_pdf.state(["!disabled"])
                    messagebox.showerror(APP_NAME, "Une erreur est survenue :\n\n%s" % a)
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def _reveal(self, folder):
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)                      # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _on_close(self):
        self.cancel_event.set()
        if self.tmp_dir and os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.destroy()


def _selftest(video_path, out_pdf, interval=4.0):
    """Mode auto-test sans interface : verifie que le programme fige
    (exe) dispose bien de tous les composants necessaires."""
    import io
    import tempfile
    from PIL import Image

    print("[selftest] extraction depuis", video_path)
    tmp = tempfile.mkdtemp(prefix="vfp_selftest_")
    frames = vf.extract_frames(video_path, interval=interval, out_dir=tmp,
                                quality=88,
                                progress=lambda f, m: None)
    print("[selftest] %d image(s) extraite(s)" % len(frames))
    if not frames:
        print("[selftest] ECHEC : aucune image")
        return 1

    builder = PdfBuilder(page_size=PAGE_SIZES["A4 portrait"],
                         title="selftest", author=APP_NAME)
    builder.add_cover("selftest", "%d images" % len(frames), "test")
    for item in frames:
        with open(item["path"], "rb") as f:
            data = f.read()
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
        builder.add_image(data, w, h, caption=vf._hhmmss(item["time"]))
    builder.save(out_pdf)
    print("[selftest] PDF ecrit :", out_pdf, os.path.getsize(out_pdf),
          "octets")
    shutil.rmtree(tmp, ignore_errors=True)
    print("[selftest] OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        video = sys.argv[2] if len(sys.argv) > 2 else "test_video.mp4"
        dest = sys.argv[3] if len(sys.argv) > 3 else "selftest.pdf"
        sys.exit(_selftest(video, dest))
    App().mainloop()
