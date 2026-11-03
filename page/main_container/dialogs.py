"""
page/main_container/dialogs.py
──────────────────────────────
Küçük modal pencereler.

AreaPickerDialog: V8'de alan seçmek için ID'yi elle yazdırıyordu
(simpledialog.askstring). Artık listeden seçilir.
"""

import tkinter as tk


class AreaPickerDialog(tk.Toplevel):
    """Listeden bir alan seçtirir. `result` seçilen alanın id'si (iptalde None)."""

    def __init__(self, parent, colors, areas: list[dict], title: str, action_text: str = "Seç"):
        super().__init__(parent)
        self.result = None
        self._areas = areas
        self.title(title)
        self.configure(bg=colors["bg_medium"])
        self.resizable(False, False)
        self.transient(parent)

        tk.Label(self, text=title, font=("Segoe UI", 11, "bold"),
                 bg=colors["bg_medium"], fg=colors["text"], pady=10, padx=20).pack()

        self.listbox = tk.Listbox(
            self, height=min(max(len(areas), 3), 10), width=34, font=("Segoe UI", 11),
            bg=colors["bg_dark"], fg=colors["text"], selectbackground=colors["accent"],
            selectforeground="white", relief=tk.FLAT, activestyle="none", exportselection=False)
        for a in areas:
            self.listbox.insert(tk.END, f"  {a['name']}   ({len(a['points'])} nokta)")
        self.listbox.pack(padx=20, pady=(0, 10))
        if areas:
            self.listbox.selection_set(0)
        self.listbox.bind("<Double-Button-1>", lambda e: self._ok())

        row = tk.Frame(self, bg=colors["bg_medium"])
        row.pack(pady=(0, 15))
        for text, cmd, bg in ((action_text, self._ok, colors["accent"]),
                              ("İptal", self.destroy, colors["bg_light"])):
            tk.Button(row, text=text, command=cmd, font=("Segoe UI", 10), bg=bg, fg="white",
                      relief=tk.FLAT, padx=18, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=6)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.listbox.focus_set()
        self.wait_window(self)

    def _ok(self):
        sel = self.listbox.curselection()
        if sel:
            self.result = self._areas[sel[0]]["id"]
        self.destroy()
