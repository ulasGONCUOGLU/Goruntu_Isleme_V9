"""
page/settings/ui_utils.py
─────────────────────────
Ayarlar sayfasında paylaşılan küçük UI yardımcıları.

Sekme dosyalarına özel değil; birden fazla sekme veya widget kullanabilir.
"""

import tkinter as tk


def add_hover(widget: tk.Widget, normal: str, hover: str) -> None:
    """
    Fare üzerine gelince arka plan rengini değiştir.
    normal : Varsayılan renk
    hover  : Üzerine gelince renk
    """
    widget.bind('<Enter>', lambda e: widget.configure(bg=hover))
    widget.bind('<Leave>', lambda e: widget.configure(bg=normal))


def show_toast(parent: tk.Widget, message: str, accent: str) -> None:
    """
    Sağ alt köşede kısa süreli bildirim göster (2.5 sn).
    Model kaydedildi / ayarlar kaydedildi gibi geri bildirimler için.
    """
    toast = tk.Label(
        parent,
        text=message,
        font=('Segoe UI', 10),
        bg=accent,
        fg='white',
        padx=16,
        pady=8,
        relief=tk.FLAT,
    )
    toast.place(relx=1.0, rely=1.0, anchor='se', x=-20, y=-20)
    parent.after(2500, toast.destroy)
