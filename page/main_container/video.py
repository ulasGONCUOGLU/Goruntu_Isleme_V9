"""
page/main_container/video.py
────────────────────────────
Ana Sayfa — video + sayım ARAYÜZÜ.

V8'de bu dosya 1053 satırdı ve arayüz, model yükleme, tespit, sayım, çizim
ve kayıt işlerini tek sınıfta yapıyordu. V9'da yalnızca arayüz kaldı:

    core.detection.DetectionEngine   YOLO + takip
    core.zones.ZoneCounter           alan bazlı sayım (supervision)
    core.annotate.FrameAnnotator     çizim (supervision)
    core.player.VideoPlayer          video thread'i
    page.main_container.area_editor  alan çizme/düzenleme
    page.main_container.info_panel   sağdaki sayım paneli

THREAD KURALI: Tkinter yalnızca ana thread'den güncellenir. İşçi thread'i
kareleri kuyruğa koyar; `_poll()` her 15 ms'de kuyruğu boşaltıp en yeni kareyi çizer.
"""

import os
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import cv2
import numpy as np
from PIL import Image, ImageTk

from core.annotate import FrameAnnotator
from core.config import Settings
from core.detection import YOLO_AVAILABLE, DetectionEngine
from core.logger import get_logger
from core.paths import DOSYALAR_DIR
from core.player import Packet, VideoPlayer
from core.zones import ZoneCounter
from page.main_container.area_editor import AreaEditor
from page.main_container.info_panel import InfoPanel
from page.main_container.save import VideoRecorder
from page.settings.db import db_get

log = get_logger("ui.main")

POLL_MS = 15


class MainVideoContainer:
    """Ana Sayfa için video container bileşeni."""

    def __init__(self, parent_frame, colors):
        self.parent_frame = parent_frame
        self.colors = colors
        self.root = parent_frame.winfo_toplevel()

        # ── çekirdek ──
        self.settings = Settings.load()
        self.engine = DetectionEngine(self.settings)
        self.counter = ZoneCounter(self.settings.min_frames_in_zone)
        self.annotator = FrameAnnotator(self.settings.trace_length)
        self.video_recorder = VideoRecorder()
        self.player = VideoPlayer(self.engine, self.counter, self.annotator, self.video_recorder)

        # ── durum ──
        self.frame_width = 0
        self.frame_height = 0
        self.scale_x = self.scale_y = 1.0
        self.image_x = self.image_y = 0
        self.should_save_on_stop = False
        self._session_active = False            # Oynat'a basıldı, Bitir/Sıfırla'ya kadar
        self._loaded_model_name: str | None = None
        self._pending_model_reload = False
        self._image_item = None
        self._photo = None
        self._poll_job = None
        self._notify_job = None
        self._last_fps_update = 0.0
        self._warned_no_model = False

        self.area_editor = AreaEditor(
            self.root, colors, self.counter,
            get_frame_size=lambda: (self.frame_width, self.frame_height),
            notify=self.show_notification,
            on_changed=self._on_areas_changed,
            redraw_overlay=self._draw_overlay,
        )

        self.setup_ui()
        self._poll()

    # ═══════════════════════════ ARAYÜZ ═══════════════════════════
    def setup_ui(self):
        c = self.colors
        main = tk.Frame(self.parent_frame, bg=c["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Sağ: sayım paneli
        self.info_panel = InfoPanel(main, c)
        self.info_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_panel.update(None)

        # Sol: alan düğmeleri + video
        left = tk.Frame(main, bg=c["bg_dark"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        bar = tk.Frame(left, bg=c["bg_medium"])
        bar.pack(fill=tk.X, pady=(0, 10))
        inner = tk.Frame(bar, bg=c["bg_medium"])
        inner.pack(pady=10, padx=15)
        ed = self.area_editor
        for text, cmd in [
            ("➕ Ekle", ed.add_area), ("✏️ Düzenle", ed.edit_area), ("🗑️ Sil", ed.delete_area),
            ("↶ Geri Al", ed.undo_point), ("✓ Tamamla", ed.finish_area),
            ("💾 Alanları Kaydet", ed.save_to_file), ("📂 Alanları Yükle", ed.load_from_file),
        ]:
            self._button(inner, text, cmd, padx=10, pady=6, size=9).pack(side=tk.LEFT, padx=4)

        self.video_frame = tk.Canvas(left, bg=c["bg_medium"], highlightthickness=0)
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        self._placeholder = self.video_frame.create_text(
            400, 300, text="🎥 Video Oynatıcı\n\nVideo yüklemek için aşağıdaki butonları kullanın",
            font=("Segoe UI", 18), fill=c["text"], justify=tk.CENTER)

        self.create_control_panel()

        self.video_frame.bind("<Configure>", self.on_canvas_resize)
        self.video_frame.bind("<Button-1>", self.on_canvas_click)
        self.video_frame.bind("<Button-3>", lambda e: self.area_editor.on_right_click())

    def _button(self, parent, text, command, padx=15, pady=8, size=10, bg=None, hover=None):
        c = self.colors
        bg = bg or c["accent"]
        hover = hover or c["accent_hover"]
        btn = tk.Button(parent, text=text, font=("Segoe UI", size), bg=bg, fg="white",
                        relief=tk.FLAT, padx=padx, pady=pady, cursor="hand2", command=command)
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    def create_control_panel(self):
        c = self.colors
        frame = tk.Frame(self.parent_frame, bg=c["bg_medium"])
        frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        row = tk.Frame(frame, bg=c["bg_medium"])
        row.pack(pady=15, padx=15)

        self._button(row, "📂 Dosya Seç", self.load_video).pack(side=tk.LEFT, padx=5)
        self._button(row, "▶️ Oynat", self.play_video).pack(side=tk.LEFT, padx=5)
        self._button(row, "⏸️ Duraklat", self.pause_video).pack(side=tk.LEFT, padx=5)
        self._button(row, "🛑 Bitir", self.finish_video, bg="#e74c3c", hover="#c0392b").pack(side=tk.LEFT, padx=5)
        self._button(row, "🔄 Sıfırla", self.reset_video).pack(side=tk.LEFT, padx=5)

        self.video_record_button = tk.Button(
            row, text="🎥 Video Kaydı Aç/Kapa", font=("Segoe UI", 10), fg="white", relief=tk.FLAT,
            padx=15, pady=8, cursor="hand2", command=self.toggle_video_recording)
        self.video_record_button.pack(side=tk.LEFT, padx=5)
        self.video_record_button.bind("<Enter>", lambda e: self._paint_record_button(hover=True))
        self.video_record_button.bind("<Leave>", lambda e: self._paint_record_button())
        self._paint_record_button()

        status_row = tk.Frame(frame, bg=c["bg_dark"])
        status_row.pack(fill=tk.X, padx=15, pady=(0, 15))
        self.status_bar = tk.Label(status_row, text="Durum: Hazır", font=("Segoe UI", 10),
                                   bg=c["bg_dark"], fg=c["text"], anchor=tk.W, padx=15, pady=10)
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.fps_label = tk.Label(status_row, text="", font=("Segoe UI", 10), bg=c["bg_dark"],
                                  fg="#4fc3f7", anchor=tk.E, padx=15)
        self.fps_label.pack(side=tk.RIGHT)

    def _paint_record_button(self, hover=False):
        on = self.should_save_on_stop
        color = ("#27ae60" if hover else "#2ecc71") if on else ("#c0392b" if hover else "#e74c3c")
        self.video_record_button.configure(bg=color, activebackground=color)

    # ══════════════════════ KUYRUK → EKRAN (ANA THREAD) ══════════════════════
    def _poll(self):
        try:
            self._drain_queue()
        except Exception:
            log.exception("Kuyruk işlenirken hata")
        finally:
            self._poll_job = self.parent_frame.after(POLL_MS, self._poll)

    def _drain_queue(self):
        latest: Packet | None = None
        snapshot = None
        control: list[Packet] = []
        while True:
            try:
                p = self.player.queue.get_nowait()
            except queue.Empty:
                break
            if p.kind == "frame":
                latest = p
                if p.snapshot is not None:
                    snapshot = p.snapshot
            else:
                control.append(p)

        if latest is not None:
            self._show_rgb(latest.display_rgb)
            now = time.monotonic()
            if now - self._last_fps_update > 0.5:
                self._last_fps_update = now
                self.fps_label.configure(text=f"{latest.fps:.1f} FPS  ·  kare {latest.frame_idx}")
        if snapshot is not None:
            self.info_panel.update(snapshot)

        for p in control:
            if p.kind == "eof":
                self.finish_video(auto=True)
            elif p.kind == "error":
                self.player.stop()
                messagebox.showerror("İşleme Hatası", p.message)
                self.show_notification("İşleme hatası — ayrıntı: dosyalar/logs/app.log")

    # ══════════════════════════ GÖRÜNTÜ ══════════════════════════
    def _fit_size(self, w, h):
        cw, ch = self.video_frame.winfo_width(), self.video_frame.winfo_height()
        if cw <= 1 or ch <= 1 or w <= 0 or h <= 0:
            return 0, 0
        ratio = w / h
        if cw / ch > ratio:
            return max(int(ch * ratio), 1), ch
        return cw, max(int(cw / ratio), 1)

    def _show_rgb(self, rgb: np.ndarray | None):
        """RGB kareyi canvas'a koy (tek image item yeniden kullanılır)."""
        if rgb is None or self.frame_width <= 0:
            return
        h, w = rgb.shape[:2]
        cw, ch = self.video_frame.winfo_width(), self.video_frame.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        x, y = (cw - w) // 2, (ch - h) // 2
        self.scale_x = w / self.frame_width
        self.scale_y = h / self.frame_height
        self.image_x, self.image_y = x, y

        if self._image_item is None:
            self._image_item = self.video_frame.create_image(x, y, anchor=tk.NW, image=self._photo)
        else:
            self.video_frame.coords(self._image_item, x, y)
            self.video_frame.itemconfigure(self._image_item, image=self._photo)
        self.video_frame.tag_lower(self._image_item)
        self._draw_overlay()

    def refresh_view(self):
        """Oynatma yokken (duraklatıldı / alan düzenlendi) mevcut kareyi yeniden çiz."""
        if self.player.playing:
            return
        raw = self.player.last_raw
        if raw is None:
            return
        frame = self.annotator.draw(raw.copy(), self.player.last_det, self.counter.areas,
                                    self.counter.zone_current(), update_history=False)
        w, h = self._fit_size(frame.shape[1], frame.shape[0])
        if w > 0:
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
        self._show_rgb(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def _draw_overlay(self):
        """Çizim modundaki (henüz kaydedilmemiş) poligonu canvas üstüne çiz."""
        cv = self.video_frame
        cv.delete("drawing")
        ed = self.area_editor
        if not ed.drawing_mode or not ed.current_polygon:
            return
        pts = [(self.image_x + int(px * self.scale_x), self.image_y + int(py * self.scale_y))
               for px, py in ed.current_polygon]
        for a, b in zip(pts, pts[1:]):
            cv.create_line(*a, *b, fill="#ffff00", width=2, tags="drawing")
        if len(pts) >= 3:
            cv.create_line(*pts[-1], *pts[0], fill="#ffff00", width=1, dash=(4, 4), tags="drawing")
        for px, py in pts:
            cv.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#ffff00", outline="#ffff00", tags="drawing")
        cv.tag_raise("drawing")

    def _on_areas_changed(self):
        self.info_panel.update(self.counter.snapshot())
        self._draw_overlay()
        self.refresh_view()

    def on_canvas_click(self, event):
        ed = self.area_editor
        if not ed.drawing_mode or self.frame_width <= 0 or self.scale_x <= 0:
            return
        x = (event.x - self.image_x) / self.scale_x
        y = (event.y - self.image_y) / self.scale_y
        if 0 <= x <= self.frame_width and 0 <= y <= self.frame_height:
            ed.on_click(int(x), int(y))

    def on_canvas_resize(self, event):
        if self.frame_width > 0:
            w, h = self._fit_size(self.frame_width, self.frame_height)
            self.player.set_display_size(w, h)
            self.refresh_view()
        elif self._image_item is None:
            try:
                self.video_frame.coords(self._placeholder, event.width // 2, event.height // 2)
            except tk.TclError:
                pass

    # ══════════════════════════ MODEL ══════════════════════════
    def _load_model_from_settings(self, force: bool = False) -> bool:
        """
        Ayarlar'daki aktif modeli yükle (değiştiyse veya force ise).
        Model: dosyalar/<aktif model yolu> — .pt, .onnx, .engine veya OpenVINO klasörü.
        """
        if not YOLO_AVAILABLE:
            if not self._warned_no_model:
                self._warned_no_model = True
                messagebox.showwarning("ultralytics yok",
                                       "Tespit için ultralytics kurulu olmalı:\npip install -r requirements.txt")
            return False

        model_name = db_get("active_model")
        if not model_name:
            messagebox.showerror("Model Bulunamadı",
                                 "Ayarlar > Model Seçimi bölümünden bir model seçip uygulayın.")
            return False
        if not force and model_name == self._loaded_model_name and self.engine.loaded:
            return True

        model_path = DOSYALAR_DIR / model_name
        if not model_path.exists():
            messagebox.showerror("Dosya Bulunamadı", f"Model dosyası bulunamadı:\n{model_path}")
            return False

        self.show_notification(f"Model yükleniyor: {model_name} ...")
        self.parent_frame.update_idletasks()
        try:
            self.engine.configure(self.settings)
            self.engine.load(str(model_path))
        except Exception as e:
            log.exception("Model yüklenemedi")
            messagebox.showerror("Hata", f"Model yüklenirken hata:\n{e}")
            return False

        self._loaded_model_name = model_name
        self._pending_model_reload = False
        self.annotator.set_classes(self.engine.names)
        self.counter.reset_tracking_state()
        self.annotator.reset_history()
        self.show_notification(f"Model yüklendi: {model_name}  ({self.engine.device})")
        return True

    def reload_model_from_settings(self) -> None:
        """Ayarlar > Modeli Uygula sonrası çağrılır."""
        if not YOLO_AVAILABLE:
            return
        if self.player.playing:
            self._pending_model_reload = True
            self.show_notification("Model kaydedildi. Durdurup tekrar başlattığınızda uygulanır.")
            return
        self.settings = Settings.load()
        self._load_model_from_settings(force=True)

    def _apply_pending_model_reload(self) -> None:
        if self._pending_model_reload and not self.player.playing:
            self._load_model_from_settings(force=True)

    # ══════════════════════════ VİDEO KONTROL ══════════════════════════
    def load_video(self):
        path = filedialog.askopenfilename(
            title="Video Dosyası Seç",
            filetypes=[("Video Dosyaları", "*.mp4 *.avi *.mkv *.mov"), ("Tüm Dosyalar", "*.*")])
        if path:
            self.open_video_path(path)

    def open_video_path(self, path: str) -> bool:
        """Videoyu aç (dosya penceresi olmadan; testler ve otomasyon için de kullanılır)."""
        self._abort_recording_silently()
        old_size = (self.frame_width, self.frame_height)

        if not self.player.open(path):
            messagebox.showerror("Hata", "Video dosyası açılamadı!")
            return False

        self.frame_width, self.frame_height = self.player.frame_width, self.player.frame_height
        self.area_editor.rescale(old_size, (self.frame_width, self.frame_height))
        self._session_active = False
        self._reset_analysis_state()

        self.video_frame.delete(self._placeholder)
        self._image_item = None
        w, h = self._fit_size(self.frame_width, self.frame_height)
        self.player.set_display_size(w, h)
        self.player.first_frame()
        self.refresh_view()
        self.show_notification(f"Video yüklendi: {os.path.basename(path)}")

        if YOLO_AVAILABLE:
            self._load_model_from_settings()
        return True

    def _reset_analysis_state(self):
        """Sayımlar, takip ID'leri ve iz geçmişi — yeni analiz için."""
        self.counter.reset_counts()
        self.counter.reset_tracking_state()
        self.engine.reset_tracker()
        self.annotator.reset_history()
        self.info_panel.update(self.counter.snapshot())

    def play_video(self):
        if not self.player.is_open:
            messagebox.showwarning("Uyarı", "Önce bir video yükleyin!")
            return
        if self.player.playing:
            return

        self.settings = Settings.load()           # Ayarlar'daki değişiklikler her başlatmada uygulanır
        self.engine.configure(self.settings)
        self.counter.configure(self.settings.min_frames_in_zone)
        if YOLO_AVAILABLE:
            self._load_model_from_settings()

        if not self._session_active:              # yeni analiz (duraklatıp devam değil)
            self.counter.reset_tracking_state()
            self.engine.reset_tracker()
            self.annotator.reset_history()
            self._session_active = True

        if self.should_save_on_stop and not self.video_recorder.recording:
            fps = self.player.source_fps
            if not self.video_recorder.start_recording(self.frame_width, self.frame_height, fps):
                messagebox.showwarning("Uyarı", "Video kaydı başlatılamadı.")

        if self.player.start(self.settings, record=self.video_recorder.recording):
            self.show_notification("Video oynatılıyor")
        else:
            self.show_notification("Oynatma başlatılamadı (önceki işlem hâlâ bitmedi)")

    def pause_video(self):
        if self.player.playing:
            self.player.stop()
            self._apply_pending_model_reload()
            self.fps_label.configure(text="")
            self.show_notification("Video duraklatıldı")

    def finish_video(self, auto: bool = False):
        """
        Analizi bitir: sayımları (ve açıksa videoyu) kaydet, ardından sıfırla.
        Video sonuna gelinince otomatik (auto=True), kullanıcı basınca elle çalışır.
        """
        if not self._session_active:
            if not auto:
                self.show_notification("Analiz başlatılmadı, bitirilemez")
            return

        self.player.stop()
        self.player.drain()
        self._session_active = False
        self.fps_label.configure(text="")
        self._apply_pending_model_reload()

        self.show_notification("Video bitiriliyor, kayıt yapılıyor...")
        snapshot = self.counter.snapshot()
        if self.video_recorder.recording:
            self._save_recording(snapshot)
        else:
            self._save_counts_only(snapshot)

        self._reset_analysis_state()
        self.player.rewind()
        self.player.first_frame()
        self.refresh_view()
        self.show_notification("Video bitirildi")

    def reset_video(self):
        """Her şeyi başlangıç durumuna döndür (video, alanlar, sayımlar)."""
        self.player.stop()
        self.player.drain()
        self._abort_recording_silently()
        self.player.release()
        self._session_active = False

        self.frame_width = self.frame_height = 0
        self.scale_x = self.scale_y = 1.0
        self.image_x = self.image_y = 0
        self.fps_label.configure(text="")

        self.area_editor.reset_drawing()
        self.counter.set_areas([])
        self._reset_analysis_state()

        self.video_frame.delete("all")
        self._image_item = None
        w = self.video_frame.winfo_width() or 800
        h = self.video_frame.winfo_height() or 600
        self._placeholder = self.video_frame.create_text(
            w // 2, h // 2, text="🎥 Video Oynatıcı\n\nVideo yüklemek için aşağıdaki butonları kullanın",
            font=("Segoe UI", 18), fill=self.colors["text"], justify=tk.CENTER)
        self.show_notification("Video sıfırlandı - Tüm alanlar ve sayımlar temizlendi")

    def toggle_video_recording(self):
        if self.player.playing:
            self.show_notification("Önce videoyu durdurun, sonra kayıt ayarını değiştirin")
            return
        self.should_save_on_stop = not self.should_save_on_stop
        self.show_notification(f"Video kaydı {'açık' if self.should_save_on_stop else 'kapalı'}")
        self._paint_record_button()

    # ══════════════════════════ KAYIT ══════════════════════════
    def _abort_recording_silently(self):
        try:
            if self.video_recorder.recording:
                self.video_recorder.stop_recording(name=None)
        except Exception:
            log.exception("Kayıt iptal edilirken hata")

    def _save_recording(self, snapshot):
        name = simpledialog.askstring("Video Kaydı", "Video kaydı için bir isim girin:",
                                      parent=self.root)
        try:
            result = self.video_recorder.stop_recording(name, snapshot)
            self.show_notification(f"Video kaydedildi: {result['name']}" if result
                                   else "Video kaydı iptal edildi")
        except Exception as e:
            log.exception("Video kaydedilemedi")
            messagebox.showerror("Hata", f"Video kaydedilirken hata oluştu: {e}")

    def _save_counts_only(self, snapshot):
        if snapshot.total_transitions == 0:
            return
        name = simpledialog.askstring("Geçiş Sayımları", "Geçiş sayımları için bir isim girin:",
                                      parent=self.root)
        if not name:
            self.show_notification("Sayım kaydı iptal edildi")
            return
        try:
            rid = self.video_recorder.save_transition_counts_only(name, snapshot)
            self.show_notification(f"Sayım kaydedildi: {name}" if rid else "Kaydedilecek geçiş bulunamadı")
        except Exception as e:
            log.exception("Sayım kaydedilemedi")
            messagebox.showerror("Hata", f"Sayım kaydedilirken hata oluştu: {e}")

    # ══════════════════════════ YARDIMCI ══════════════════════════
    def show_notification(self, message):
        self.status_bar.configure(text=f"Durum: {message}", bg=self.colors["accent"])
        if self._notify_job is not None:
            try:
                self.root.after_cancel(self._notify_job)
            except tk.TclError:
                pass

        def reset():
            try:
                if self.status_bar.winfo_exists():
                    self.status_bar.configure(bg=self.colors["bg_dark"])
            except tk.TclError:
                pass

        self._notify_job = self.root.after(2000, reset)

    def cleanup(self):
        if self._poll_job is not None:
            try:
                self.parent_frame.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None
        self.player.stop()
        self._abort_recording_silently()
        self.player.release()
        self.video_recorder.cleanup()
