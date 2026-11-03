"""
page/settings/widgets.py
────────────────────────
Yeniden kullanılabilir ayar bileşenleri.

ContentFooter : Her sekmenin altındaki çubuk
                Sol → durum metni (aktif model, kayıt durumu)
                Sağ → aksiyon butonu (Modeli Uygula / Kaydet)
"""

import tkinter as tk

from page.settings.ui_utils import add_hover


class ContentFooter(tk.Frame):
    """Sekme alt çubuğu — sol durum etiketi + sağ aksiyon butonu."""

    def __init__(
        self,
        parent: tk.Widget,
        colors: dict,
        button_text: str,
        on_action,
        status_text: str = '',
    ):
        """
        parent       : Sekmenin ana çerçevesi
        button_text  : Sağ buton metni (örn. 'Modeli Uygula', 'Kaydet')
        on_action    : Butona basınca çalışacak fonksiyon
        status_text  : Sol etiketin başlangıç metni
        """
        super().__init__(parent, bg=colors['bg_medium'], height=55)
        self.colors = colors
        self.pack(fill=tk.X, side=tk.BOTTOM)
        self.pack_propagate(False)

        # Sol — bilgi / durum satırı
        self.status_label = tk.Label(
            self,
            text=status_text,
            font=('Segoe UI', 10),
            bg=colors['bg_medium'],
            fg=colors['text'],
            padx=20,
        )
        self.status_label.pack(side=tk.LEFT, pady=15)

        # Sağ — kaydet / uygula butonu
        action_btn = tk.Button(
            self,
            text=button_text,
            font=('Segoe UI', 10, 'bold'),
            bg=colors['accent'],
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor='hand2',
            command=on_action,
        )
        action_btn.pack(side=tk.RIGHT, padx=20, pady=10)
        add_hover(action_btn, colors['accent'], colors['accent_hover'])

    def set_status(self, text: str) -> None:
        """Sol durum etiketini güncelle (örn. 'Aktif model: best.pt')."""
        self.status_label.configure(text=text)
