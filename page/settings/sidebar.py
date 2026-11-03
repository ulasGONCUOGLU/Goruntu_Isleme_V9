"""
page/settings/sidebar.py
────────────────────────
Sol sekme menüsü — yalnızca navigasyon.

Bu dosyada form, slider veya DB işlemi yoktur.
Kullanıcı bir kategoriye tıkladığında main.py içindeki _show_tab çağrılır.

Yeni kategori eklemek:
    1. TAB_DEFS listesine (key, 'görünen ad') ekleyin
    2. main.py → self.tabs sözlüğüne aynı key ile sekme sınıfı ekleyin
"""

import tkinter as tk


class SettingsSidebar:
    """Sol sekme menüsü — yalnızca navigasyon."""

    # (iç anahtar, buton üzerindeki metin)
    # key değeri main.py self.tabs sözlüğündeki anahtarla eşleşmeli
    TAB_DEFS = [
        ('model', '🤖  Model Seçimi'),   # YOLO .pt model listesi
        ('config', '⚙️  Yapılandırma'),  # Eşikler, izleyici, FPS (Settings'e bağlı)
    ]

    def __init__(self, parent: tk.Widget, colors: dict, on_tab_change):
        """
        parent         : Gövde çerçevesi (body)
        colors         : Tema renkleri
        on_tab_change  : Sekme değişince çağrılan fonksiyon → main._show_tab
        """
        self.colors = colors
        self.on_tab_change = on_tab_change
        self.buttons: dict[str, tk.Button] = {}  # key → menü butonu

        # Sol panel — sabit 200 px genişlik
        self.panel = tk.Frame(parent, bg=colors['bg_medium'], width=200)
        self.panel.pack(side=tk.LEFT, fill=tk.Y)
        self.panel.pack_propagate(False)

        # Küçük başlık etiketi
        tk.Label(
            self.panel,
            text='KATEGORİLER',
            font=('Segoe UI', 8, 'bold'),
            bg=colors['bg_medium'],
            fg='#888888',
            padx=15,
            anchor='w',
        ).pack(fill=tk.X, pady=(20, 6))

        # Her kategori için bir menü butonu
        for key, label in self.TAB_DEFS:
            btn = tk.Button(
                self.panel,
                text=label,
                font=('Segoe UI', 10),
                bg=colors['bg_medium'],
                fg=colors['text'],
                relief=tk.FLAT,
                anchor='w',
                padx=15,
                pady=10,
                cursor='hand2',
                command=lambda k=key: self._on_click(k),
            )
            btn.pack(fill=tk.X)
            self.buttons[key] = btn

    def _on_click(self, key: str) -> None:
        """Kullanıcı menüye tıkladığında: görünümü güncelle + sekmeyi aç."""
        self.highlight(key)
        self.on_tab_change(key)

    def highlight(self, key: str) -> None:
        """
        Yalnızca görsel seçimi güncelle (geri çağrı tetiklemez).
        main._show_tab içinden çağrılır; sonsuz döngüyü önler.
        """
        for k, btn in self.buttons.items():
            if k == key:
                btn.configure(bg=self.colors['bg_light'], fg='white')
            else:
                btn.configure(bg=self.colors['bg_medium'], fg=self.colors['text'])
