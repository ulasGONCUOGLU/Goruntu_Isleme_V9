"""
page/settings/tabs/config_tab.py
────────────────────────────────
Yapılandırma sekmesi — algılama / sayım parametreleri.

V8'de bu sekme yalnızca önizlemeydi (değerler hiçbir yere bağlı değildi).
V9'da tüm değerler core.config.Settings'e okunur/yazılır (veritabanında
saklanır) ve video HER BAŞLATILDIĞINDA uygulanır.

  İşlem modu        → giriş çözünürlüğü (imgsz): hızlı 480 / dengeli 640 / kaliteli 960
  İzleyici          → ByteTrack | BoT-SORT
  Güven eşiği       → bir aracın gösterilmesi/sayılması için min. güven
  Alan onay karesi  → yeni alana geçişin onaylanması için ardışık kare sayısı
  FPS limiti        → işleme hızı üst sınırı
  Parlaklık         → görüntü parlaklığı düzeltmesi
  Gerçek zaman      → yetişemezse kare at (sayım alan bazlı olduğu için bozulmaz)
"""

import tkinter as tk
from tkinter import ttk

from core.config import Settings
from page.settings.tabs.base import BaseSettingsTab
from page.settings.widgets import ContentFooter


class ConfigTab(BaseSettingsTab):
    key = 'config'

    def __init__(self, parent, colors, show_toast):
        super().__init__(parent, colors, show_toast)
        s = Settings.load()
        self._mode_var = tk.StringVar(value=s.mode)
        self._tracker_var = tk.StringVar(value=s.tracker)
        self._sync_var = tk.BooleanVar(value=s.realtime_sync)
        self._conf_var = tk.IntVar(value=int(round(s.count_conf * 100)))
        self._fps_var = tk.IntVar(value=s.fps_limit)
        self._bright_var = tk.IntVar(value=s.brightness)
        self._frames_var = tk.IntVar(value=s.min_frames_in_zone)
        self._base = s                       # değişmeyen alanları (iou, device ...) korumak için
        self.build()

    # ── yardımcılar ─────────────────────────────────────────────────
    def _section(self, parent, title):
        box = tk.LabelFrame(parent, text=f'  {title}  ', font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg_medium'], fg=self.colors['text'],
                            padx=16, pady=10, labelanchor='nw')
        box.pack(fill=tk.X, pady=(0, 12))
        return box

    def _radio(self, parent, text, var, value):
        tk.Radiobutton(parent, text=text, variable=var, value=value, font=('Segoe UI', 10),
                       bg=self.colors['bg_medium'], fg=self.colors['text'],
                       selectcolor=self.colors['bg_light'],
                       activebackground=self.colors['bg_medium'],
                       activeforeground=self.colors['text'], anchor='w').pack(fill=tk.X, pady=3)

    def _slider(self, parent, title, var, lo, hi, unit='', hint=''):
        box = self._section(parent, title)
        lbl = tk.Label(box, text=f'{var.get()}{unit}', font=('Segoe UI', 9, 'bold'),
                       bg=self.colors['bg_medium'], fg=self.colors['accent'], width=6)
        lbl.pack(side=tk.RIGHT)

        def on_move(v, lbl=lbl, var=var, unit=unit):
            var.set(int(round(float(v))))
            lbl.configure(text=f'{var.get()}{unit}')

        scale = ttk.Scale(box, from_=lo, to=hi, orient=tk.HORIZONTAL, command=on_move)
        scale.set(var.get())
        scale.pack(fill=tk.X)
        if hint:
            tk.Label(box, text=hint, font=('Segoe UI', 8), bg=self.colors['bg_medium'],
                     fg='#888888', justify=tk.LEFT, anchor='w').pack(fill=tk.X, pady=(4, 0))

    # ── arayüz ──────────────────────────────────────────────────────
    def build(self) -> None:
        parent, colors = self.frame, self.colors

        tk.Label(parent, text='Yapılandırma', font=('Segoe UI', 14, 'bold'),
                 bg=colors['bg_dark'], fg=colors['accent']).pack(anchor='w', padx=30, pady=(30, 6))
        tk.Label(parent, text='Algılama ve sayım parametreleri. Kaydet\'ten sonra video bir '
                              'sonraki başlatılışta uygulanır.',
                 font=('Segoe UI', 9), bg=colors['bg_dark'], fg='#888888',
                 justify=tk.LEFT).pack(anchor='w', padx=30, pady=(0, 14))

        # Kaydırılabilir gövde
        wrap = tk.Frame(parent, bg=colors['bg_dark'])
        wrap.pack(fill=tk.BOTH, expand=True, padx=30)
        canvas = tk.Canvas(wrap, bg=colors['bg_dark'], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient='vertical', command=canvas.yview)
        body = tk.Frame(canvas, bg=colors['bg_dark'])
        win = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        mode = self._section(body, 'İşlem Modu (giriş çözünürlüğü)')
        for v, t in (('fast', 'Hızlı — 480 px, düşük gecikme'),
                     ('balanced', 'Dengeli — 640 px (önerilen)'),
                     ('quality', 'Kaliteli — 960 px, küçük/uzak araçlar için')):
            self._radio(mode, t, self._mode_var, v)

        trk = self._section(body, 'Nesne İzleyici')
        self._radio(trk, 'ByteTrack — hızlı, sabit kamera için yeterli (önerilen)', self._tracker_var, 'bytetrack')
        self._radio(trk, 'BoT-SORT — kamera hareketi telafisi, daha yavaş', self._tracker_var, 'botsort')

        self._slider(body, 'Güven Eşiği', self._conf_var, 5, 95, ' %',
                     'Bu değerin altındaki tespitler gösterilmez ve sayılmaz.')
        self._slider(body, 'Alan Onay Karesi', self._frames_var, 1, 10, ' kare',
                     'Araç yeni alanda bu kadar ardışık karede görülünce geçiş sayılır.\n'
                     '1 = en hızlı tepki, yüksek değer = sınırda titremeye karşı daha güvenli.')
        self._slider(body, 'FPS Limiti', self._fps_var, 1, 60, '',
                     'İşleme hızı üst sınırı (video kendi FPS değerinden hızlı oynamaz).')
        self._slider(body, 'Parlaklık', self._bright_var, -50, 50, '',
                     'Karanlık/aşırı parlak görüntülerde tespiti iyileştirebilir.')

        sync = self._section(body, 'Gerçek Zamanlı Senkron')
        tk.Checkbutton(sync, text='İşlem yetişemezse kare atla (video gerçek hızında aksın)',
                       variable=self._sync_var, font=('Segoe UI', 10), bg=colors['bg_medium'],
                       fg=colors['text'], selectcolor=colors['bg_light'],
                       activebackground=colors['bg_medium'], activeforeground=colors['text'],
                       anchor='w').pack(fill=tk.X)
        tk.Label(sync, text='Alan bazlı sayım kare atlamalarına dayanıklıdır. Video kaydı açıkken '
                            'kare atlanmaz.', font=('Segoe UI', 8), bg=colors['bg_medium'],
                 fg='#888888', justify=tk.LEFT, anchor='w').pack(fill=tk.X, pady=(4, 0))

        self.footer = ContentFooter(parent, colors, button_text='💾  Kaydet', on_action=self._on_save,
                                    status_text='Kayıtlı ayarlar yüklendi')

    def _on_save(self) -> None:
        s = self._base
        s.mode = self._mode_var.get()
        s.tracker = self._tracker_var.get()
        s.count_conf = self._conf_var.get() / 100.0
        s.min_frames_in_zone = self._frames_var.get()
        s.fps_limit = self._fps_var.get()
        s.brightness = self._bright_var.get()
        s.realtime_sync = self._sync_var.get()
        s.save()
        self.footer.set_status('Ayarlar kaydedildi')
        self.show_toast('💾 Ayarlar kaydedildi — sonraki başlatmada uygulanır')
