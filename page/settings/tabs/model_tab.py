"""
page/settings/tabs/model_tab.py
───────────────────────────────
Model Seçimi sekmesi — YOLO nesne algılama modeli.

Akış:
  1. dosyalar/ altında best.pt / best.onnx / best.engine ve *_openvino_model
     klasörlerini tarar
  2. Kullanıcı listeden bir satır seçer (henüz DB'ye yazılmaz)
  3. "Modeli Uygula" → db_set('active_model', ...) → video.py bunu okur

Bu dosyada yapılandırma slider/radio yoktur; sadece model işleri.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk

from core.config import Settings
from core.exporter import FORMATS, export_model
from core.logger import get_logger
from core.paths import DOSYALAR_DIR as _DOSYALAR_PATH
from page.settings.db import db_get, db_set
from page.settings.tabs.base import BaseSettingsTab
from page.settings.ui_utils import add_hover
from page.settings.widgets import ContentFooter

DOSYALAR_DIR = str(_DOSYALAR_PATH)
MODEL_FILE_NAMES = ('best.pt', 'best.onnx', 'best.engine')
log = get_logger('ui.model_tab')


class ModelTab(BaseSettingsTab):
    """Sol menü: Model Seçimi — aktif YOLO modelini belirleme."""

    key = 'model'

    def __init__(self, parent, colors, show_toast, on_model_applied=None):
        super().__init__(parent, colors, show_toast)
        self.on_model_applied = on_model_applied
        self.model_buttons: dict[str, tk.Button] = {}  # model yolu → satır butonu
        self._selected_model: str | None = None       # henüz kaydedilmemiş seçim
        self._export_queue: 'queue.Queue[tuple[str, str]]' = queue.Queue()
        self._exporting = False
        self.build()

    def build(self) -> None:
        parent = self.frame
        colors = self.colors

        # ── Üst bar: başlık + yenile ───────────────────────────
        top_bar = tk.Frame(parent, bg=colors['bg_dark'])
        top_bar.pack(fill=tk.X, padx=30, pady=(30, 6))

        tk.Label(
            top_bar,
            text='Nesne Algılama Modeli',
            font=('Segoe UI', 14, 'bold'),
            bg=colors['bg_dark'],
            fg=colors['accent'],
        ).pack(side=tk.LEFT)

        # Klasörü yeniden tarayıp listeyi günceller
        refresh_btn = tk.Button(
            top_bar,
            text='🔄 Yenile',
            font=('Segoe UI', 9),
            bg=colors['bg_light'],
            fg=colors['text'],
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._refresh_model_list,
        )
        refresh_btn.pack(side=tk.RIGHT)
        add_hover(refresh_btn, colors['bg_light'], colors['accent'])

        # Kullanıcıya kısa açıklama
        tk.Label(
            parent,
            text='dosyalar/ klasöründeki best.pt, best.onnx, best.engine ve OpenVINO modelleri listelenir.\n'
                 'Bir .pt modelini seçip aşağıdan ONNX / OpenVINO / TensorRT\'ye dönüştürebilirsiniz\n(hız kazancı donanıma bağlıdır; tools/benchmark.py ile ölçün).',
            font=('Segoe UI', 9),
            bg=colors['bg_dark'],
            fg='#888888',
            justify=tk.LEFT,
        ).pack(anchor='w', padx=30, pady=(0, 16))

        # ── Orta: kaydırılabilir model listesi ─────────────────
        list_wrapper = tk.Frame(parent, bg=colors['bg_dark'])
        list_wrapper.pack(fill=tk.BOTH, expand=True, padx=30)

        self._list_canvas = tk.Canvas(
            list_wrapper, bg=colors['bg_dark'], highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            list_wrapper, orient='vertical', command=self._list_canvas.yview
        )
        # Canvas içindeki gerçek liste — her model bir satır (Frame)
        self.model_list_frame = tk.Frame(
            self._list_canvas, bg=colors['bg_dark']
        )
        self.model_list_frame.bind(
            '<Configure>',
            lambda e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox('all')
            ),
        )
        self._list_canvas.create_window(
            (0, 0), window=self.model_list_frame, anchor='nw'
        )
        self._list_canvas.configure(yscrollcommand=scrollbar.set)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Dışa aktarma çubuğu ────────────────────────────────
        export_bar = tk.Frame(parent, bg=colors['bg_dark'])
        export_bar.pack(fill=tk.X, padx=30, pady=(10, 10))
        tk.Label(export_bar, text='Seçili .pt modeli dönüştür:', font=('Segoe UI', 9),
                 bg=colors['bg_dark'], fg='#888888').pack(side=tk.LEFT)
        self._export_buttons = []
        for fmt, label in FORMATS.items():
            b = tk.Button(export_bar, text=label, font=('Segoe UI', 9), bg=colors['bg_light'],
                          fg=colors['text'], relief=tk.FLAT, padx=10, pady=4, cursor='hand2',
                          command=lambda f=fmt: self._start_export(f))
            b.pack(side=tk.LEFT, padx=(8, 0))
            add_hover(b, colors['bg_light'], colors['accent'])
            self._export_buttons.append(b)

        # ── Alt bar: aktif model bilgisi + Uygula ──────────────
        self.footer = ContentFooter(
            parent,
            colors,
            button_text='✅  Modeli Uygula',
            on_action=self._apply_model,
            status_text='Aktif model: —',
        )

        self._refresh_model_list()

    def _refresh_model_list(self) -> None:
        """dosyalar/ klasörünü tara, listeyi sıfırdan oluştur."""
        for w in self.model_list_frame.winfo_children():
            w.destroy()
        self.model_buttons.clear()
        self._selected_model = None

        models = self._scan_models()

        if not models:
            tk.Label(
                self.model_list_frame,
                text='dosyalar/ klasöründe model bulunamadı (best.pt / .onnx / .engine).',
                font=('Segoe UI', 11),
                bg=self.colors['bg_dark'],
                fg='#888888',
                pady=20,
            ).pack(anchor='w', padx=10)
            self.footer.set_status('Aktif model: —')
            return

        for name in models:
            self._create_model_row(name)

        # DB'de kayıtlı model varsa onu seçili göster
        saved = db_get('active_model')
        if saved and saved in self.model_buttons:
            self._select_model(saved)
            self.footer.set_status(f'Aktif model: {saved}')
        elif models:
            self._select_model(models[0])  # yoksa ilkini önizleme seçimi

    def _create_model_row(self, model_name: str) -> None:
        """Tek model için tıklanabilir satır + dosya boyutu etiketi."""
        row = tk.Frame(self.model_list_frame, bg=self.colors['bg_medium'])
        row.pack(fill=tk.X, pady=4, padx=4)

        btn = tk.Button(
            row,
            text=f'  🧠  {model_name}',
            font=('Segoe UI', 11),
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            relief=tk.FLAT,
            anchor='w',
            cursor='hand2',
            command=lambda m=model_name: self._select_model(m),
        )
        btn.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=5)
        add_hover(btn, self.colors['bg_medium'], self.colors['bg_light'])

        tk.Label(
            row,
            text=self._file_size_str(model_name),
            font=('Segoe UI', 9),
            bg=self.colors['bg_medium'],
            fg='#888888',
            padx=15,
        ).pack(side=tk.RIGHT, pady=10)

        self.model_buttons[model_name] = btn

    def _select_model(self, model_name: str) -> None:
        """Görsel seçim — DB'ye yazmaz; Uygula'ya basınca kaydedilir."""
        for name, btn in self.model_buttons.items():
            row = btn.master
            is_selected = name == model_name
            color = self.colors['accent'] if is_selected else self.colors['bg_medium']
            fg = 'white' if is_selected else self.colors['text']
            label_fg = 'white' if is_selected else '#888888'

            btn.configure(bg=color, fg=fg)
            row.configure(bg=color)
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=color, fg=label_fg)

        self._selected_model = model_name

    def _apply_model(self) -> None:
        """Seçili modeli veritabanına kaydet; ana sayfadaki YOLO modelini güncelle."""
        if not self._selected_model:
            return
        db_set('active_model', self._selected_model)
        self.footer.set_status(f'Aktif model: {self._selected_model}')
        self.show_toast(f'✅ Model kaydedildi: {self._selected_model}')
        if self.on_model_applied:
            self.on_model_applied()

    def _scan_models(self) -> list[str]:
        """
        dosyalar/ altında desteklenen model dosyalarını bul:
          best.pt · best.onnx · best.engine · *_openvino_model/ klasörleri
        Dönüş: DOSYALAR_DIR'e göre göreli yol listesi (sıralı).
        """
        if not os.path.isdir(DOSYALAR_DIR):
            return []

        found = []
        for kok, dizinler, dosyalar in os.walk(DOSYALAR_DIR):
            for d in list(dizinler):
                if d.endswith('_openvino_model'):
                    found.append(os.path.relpath(os.path.join(kok, d), DOSYALAR_DIR))
                    dizinler.remove(d)          # içine inme
            for dosya in dosyalar:
                if dosya in MODEL_FILE_NAMES:
                    found.append(os.path.relpath(os.path.join(kok, dosya), DOSYALAR_DIR))
        return sorted(found)

    def _file_size_str(self, model_name: str) -> str:
        """Satırın sağında gösterilecek boyut (dosya veya klasör)."""
        path = os.path.join(DOSYALAR_DIR, model_name)
        try:
            if os.path.isdir(path):
                size = sum(os.path.getsize(os.path.join(k, f))
                           for k, _, fs in os.walk(path) for f in fs)
            else:
                size = os.path.getsize(path)
        except OSError:
            return '?'
        if size >= 1_073_741_824:
            return f'{size / 1_073_741_824:.1f} GB'
        if size >= 1_048_576:
            return f'{size / 1_048_576:.1f} MB'
        return f'{size / 1024:.1f} KB'

    # ── dışa aktarma (arka plan thread'i; sonuç kuyrukla ana thread'e) ──
    def _start_export(self, fmt: str) -> None:
        if self._exporting:
            self.show_toast('⏳ Bir dönüştürme zaten sürüyor')
            return
        name = self._selected_model
        if not name or not name.endswith('.pt'):
            self.show_toast('Önce listeden bir .pt modeli seçin')
            return

        pt_path = os.path.join(DOSYALAR_DIR, name)
        imgsz = Settings.load().imgsz
        self._exporting = True
        for b in self._export_buttons:
            b.configure(state=tk.DISABLED)
        self.footer.set_status(f'Dönüştürülüyor: {FORMATS[fmt]} ... (birkaç dakika sürebilir)')

        def worker():
            try:
                out = export_model(pt_path, fmt, imgsz=imgsz, half=(fmt == 'engine'))
                self._export_queue.put(('ok', out))
            except Exception as e:
                log.exception('Dışa aktarma başarısız')
                self._export_queue.put(('err', f'{type(e).__name__}: {e}'))

        threading.Thread(target=worker, daemon=True, name='model-export').start()
        self.frame.after(300, self._poll_export)

    def _poll_export(self) -> None:
        try:
            kind, msg = self._export_queue.get_nowait()
        except queue.Empty:
            self.frame.after(300, self._poll_export)
            return
        self._exporting = False
        for b in self._export_buttons:
            b.configure(state=tk.NORMAL)
        if kind == 'ok':
            self.show_toast('✅ Dönüştürüldü — listeyi yenileyip modeli seçin')
            self._refresh_model_list()
        else:
            self.show_toast('❌ Dönüştürme başarısız (ayrıntı: dosyalar/logs/app.log)')
            self.footer.set_status(f'Hata: {msg[:80]}')
