"""
page/settings/tabs/base.py
──────────────────────────
Tüm ayar sekmelerinin ortak iskeleti (soyut taban sınıf).

Her sekme:
  - self.frame içinde kendi arayüzünü kurar
  - show() / hide() ile görünür/gizli olur
  - build() alt sınıfta doldurulur

Yeni sekme örneği:
    class BenimTab(BaseSettingsTab):
        key = 'benim'
        def build(self): ...
"""

import tkinter as tk


class BaseSettingsTab:
    """Tüm ayar sekmelerinin ortak iskeleti."""

    key: str = ''  # sidebar.TAB_DEFS ve main.tabs anahtarı ile aynı olmalı

    def __init__(self, parent: tk.Widget, colors: dict, show_toast):
        """
        parent      : main.content_area — sağ içerik alanı
        colors      : Tema renkleri
        show_toast  : Bildirim göstermek için callback (lambda msg: ...)
        """
        self.colors = colors
        self.show_toast = show_toast
        # Bu çerçeve content_area içinde pack edilir / forget edilir
        self.frame = tk.Frame(parent, bg=colors['bg_dark'])

    def show(self) -> None:
        """Sekmeyi sağ panelde göster."""
        self.frame.pack(fill=tk.BOTH, expand=True)

    def hide(self) -> None:
        """Başka sekme seçilince bu çerçeveyi gizle."""
        self.frame.pack_forget()

    def build(self) -> None:
        """Alt sınıf kendi arayüzünü burada oluşturur."""
        raise NotImplementedError
