"""
page/settings/main.py
─────────────────────
Ayarlar sayfasının ana kabuğu (iskelet).

Bu dosya yalnızca yerleşimi ve sekme geçişini yönetir; model listesi,
yapılandırma formları gibi içerikler ayrı dosyalardadır (tabs/).

Ana uygulama (main.py) sağ panelde bu sınıfı oluşturur:
    SettingsContainer(settings_frame, self.colors)

Diğer modüllerden aktif model okumak için:
    SettingsContainer.get_active_model()
"""

import tkinter as tk

from page.settings.db import db_get
from page.settings.sidebar import SettingsSidebar
from page.settings.tabs import ConfigTab, ModelTab
from page.settings.ui_utils import show_toast


class SettingsContainer:
    """Ayarlar paneli — sol sekme menüsü + sağ içerik alanı."""

    def __init__(self, parent_frame, colors, on_model_applied=None):
        """
        parent_frame       : Ana uygulamanın sağ panelindeki boş çerçeve
        colors             : Tema renkleri sözlüğü (bg_dark, accent, text, ...)
        on_model_applied   : Modeli Uygula sonrası ana sayfayı güncellemek için callback
        """
        self.parent_frame = parent_frame
        self.colors = colors
        self.on_model_applied = on_model_applied

        # Tüm ayar arayüzünün kök çerçevesi
        self.frame = tk.Frame(parent_frame, bg=colors['bg_dark'])
        self.frame.pack(fill=tk.BOTH, expand=True)

        self._build_shell()   # Üst başlık + sol menü + sağ alan
        self._init_tabs()     # Sekme sınıflarını oluştur
        self._show_tab('model')  # Açılışta Model sekmesi

    def _build_shell(self) -> None:
        """Üst başlık çubuğu ve gövde (sidebar + content_area) oluşturur."""

        # ── Üst başlık ─────────────────────────────────────────────
        header = tk.Frame(self.frame, bg=self.colors['bg_medium'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text='⚙️  Ayarlar',
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            padx=20,
        ).pack(side=tk.LEFT, pady=15)

        # ── Gövde: sol menü | sağ içerik ─────────────────────────
        body = tk.Frame(self.frame, bg=self.colors['bg_dark'])
        body.pack(fill=tk.BOTH, expand=True)

        # Sağ taraf — seçilen sekmeye göre değişen içerik buraya gelir
        self.content_area = tk.Frame(body, bg=self.colors['bg_dark'])
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Sol taraf — kategori butonları (sidebar.py)
        self.sidebar = SettingsSidebar(
            body, self.colors, on_tab_change=self._show_tab
        )

    def _init_tabs(self) -> None:
        """
        Her sekme kendi dosyasında ayrı sınıftır.
        Yeni sekme eklemek: tabs/ altında sınıf yaz + buraya ve sidebar'a ekle.
        """
        # Tüm sekmelerin kullandığı kısa bildirim (toast) fonksiyonu
        toast = lambda msg: show_toast(self.frame, msg, self.colors['accent'])

        self.tabs = {
            'model': ModelTab(
                self.content_area,
                self.colors,
                toast,
                on_model_applied=self.on_model_applied,
            ),
            'config': ConfigTab(self.content_area, self.colors, toast),
        }

    def _show_tab(self, key: str) -> None:
        """
        Aktif sekmeyi değiştir.
        key : 'model' | 'config'  (sidebar.TAB_DEFS ile aynı anahtarlar)
        """
        for tab in self.tabs.values():
            tab.hide()
        self.tabs[key].show()
        self.sidebar.highlight(key)  # Sol menüde seçili görünüm

    @staticmethod
    def get_active_model() -> str | None:
        """
        Veritabanından kayıtlı aktif YOLO model yolunu döndürür.
        video.py bu metodu oynatma başlarken model yüklemek için kullanır.
        """
        return db_get('active_model')

    def cleanup(self):
        """Panel kapanırken kaynak temizliği (şimdilik boş)."""
        pass
