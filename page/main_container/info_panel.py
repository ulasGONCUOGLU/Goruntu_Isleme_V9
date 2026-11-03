"""
page/main_container/info_panel.py
─────────────────────────────────
Sağdaki sayım paneli.

V8'de her geçişte tüm label'lar silinip yeniden oluşturuluyordu. Burada
satırlar yalnızca alan seti değiştiğinde kurulur; sayım değişince mevcut
label'ların metni yerinde güncellenir.
"""

import tkinter as tk

from core.zones import CountSnapshot


class InfoPanel:
    def __init__(self, parent, colors, width=270):
        self.colors = colors
        self.frame = tk.Frame(parent, bg=colors["bg_medium"], width=width)
        self.frame.pack_propagate(False)

        tk.Label(self.frame, text="Alan Geçişleri", font=("Segoe UI", 12, "bold"),
                 bg=colors["bg_medium"], fg=colors["text"], pady=12).pack()

        wrap = tk.Frame(self.frame, bg=colors["bg_medium"])
        wrap.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Canvas(wrap, bg=colors["bg_medium"], highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        self.content = tk.Frame(self._canvas, bg=colors["bg_medium"])
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._win = self._canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>",
                          lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._win, width=e.width))

        self._empty = tk.Label(self.content, text="Alan çizin ve videoyu başlatın",
                               font=("Segoe UI", 10), bg=colors["bg_medium"],
                               fg="#888888", pady=20, wraplength=width - 40)
        self._rows: dict = {}          # anahtar → (başlık_label, detay_label)
        self._row_keys: list = []
        self._visit_rows: dict = {}
        self._visit_header = None
        self._shown_empty = False

    def pack(self, **kw):
        self.frame.pack(**kw)

    # ── güncelleme ─────────────────────────────────────────────────
    def update(self, snap: CountSnapshot | None) -> None:
        if snap is None or not snap.transitions:
            self._clear()
            if not self._shown_empty:
                self._empty.pack(pady=20)
                self._shown_empty = True
            return
        if self._shown_empty:
            self._empty.pack_forget()
            self._shown_empty = False

        keys = sorted(snap.transitions)
        zones = sorted(snap.zone_visits)
        if keys != self._row_keys or zones != sorted(self._visit_rows):
            self._rebuild(keys, zones)

        for key in keys:
            total = snap.transitions[key]
            title, detail = self._rows[key]
            self._set(title, f"{key[0]} → {key[1]}:  {total}", "#00ff7f" if total else "#7a7a7a")
            by_cls = snap.transitions_by_class.get(key, {})
            self._set(detail, "   " + " · ".join(f"{c} {n}" for c, n in sorted(by_cls.items())) if by_cls else "")

        for z in zones:
            title, detail = self._visit_rows[z]
            self._set(title, f"{z}:  {snap.zone_visits[z]} araç")
            by_cls = snap.zone_visits_by_class.get(z, {})
            self._set(detail, "   " + " · ".join(f"{c} {n}" for c, n in sorted(by_cls.items())) if by_cls else "")

    @staticmethod
    def _set(label: tk.Label, text: str, fg: str | None = None) -> None:
        if label.cget("text") != text:
            label.configure(text=text)
        if fg and label.cget("fg") != fg:
            label.configure(fg=fg)

    def _clear(self) -> None:
        for w in self.content.winfo_children():
            if w is not self._empty:
                w.destroy()
        self._rows, self._row_keys = {}, []
        self._visit_rows, self._visit_header = {}, None

    def _rebuild(self, keys, zones) -> None:
        self._clear()
        c = self.colors
        for key in keys:
            title = tk.Label(self.content, font=("Segoe UI", 10, "bold"), bg=c["bg_medium"],
                             fg="#7a7a7a", anchor=tk.W, padx=10)
            title.pack(fill=tk.X, pady=(6, 0))
            detail = tk.Label(self.content, font=("Segoe UI", 8), bg=c["bg_medium"],
                              fg="#a0a0a0", anchor=tk.W, padx=10)
            detail.pack(fill=tk.X)
            self._rows[key] = (title, detail)
        self._row_keys = keys

        self._visit_header = tk.Label(
            self.content, text="Alana giren benzersiz araç", font=("Segoe UI", 10, "bold"),
            bg=c["bg_medium"], fg=c["text"], anchor=tk.W, padx=10, pady=8)
        self._visit_header.pack(fill=tk.X, pady=(14, 0))
        for z in zones:
            title = tk.Label(self.content, font=("Segoe UI", 10), bg=c["bg_medium"],
                             fg="#4fc3f7", anchor=tk.W, padx=10)
            title.pack(fill=tk.X, pady=(4, 0))
            detail = tk.Label(self.content, font=("Segoe UI", 8), bg=c["bg_medium"],
                              fg="#a0a0a0", anchor=tk.W, padx=10)
            detail.pack(fill=tk.X)
            self._visit_rows[z] = (title, detail)
