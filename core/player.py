"""
core/player.py
──────────────
Video okuma + işleme thread'i.

NEDEN AYRI?  V8'de işleme thread'i Tkinter widget'larına doğrudan dokunuyordu
(update_video_frame, update_info_panel). Tkinter thread-safe DEĞİLDİR; rastgele
donma/çökme nedeni budur. V9'da kural şu:

    İŞÇİ THREAD  : kare oku → tespit/takip → say → çiz → kayıt → kuyruğa koy
    ANA THREAD   : kuyruğu `after()` ile okur, yalnızca orada widget günceller

İşçi thread'inin Tkinter ile hiçbir teması yoktur. Bu yüzden bu modül
tkinter'i hiç import etmez ve komut satırı araçlarında da kullanılabilir.

Zamanlama: video kendi gerçek FPS'ine göre oynar (sabit 0.033 sn yok).
`realtime_sync` açıksa ve işlem yetişemiyorsa kare atlanır (grab); alan bazlı
sayım kare atlamalarına dayanıklı olduğu için sayım bozulmaz.
"""

import queue
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
import supervision as sv

from core.annotate import FrameAnnotator
from core.config import Settings
from core.detection import DetectionEngine
from core.logger import get_logger
from core.zones import CountSnapshot, ZoneCounter

log = get_logger("player")


@dataclass
class Packet:
    kind: str                                  # 'frame' | 'eof' | 'error'
    display_rgb: np.ndarray | None = None      # ekrana çizilecek (RGB, ölçekli)
    snapshot: CountSnapshot | None = None      # sayımlar değiştiyse
    frame_idx: int = 0
    fps: float = 0.0
    message: str = ""


class VideoPlayer:
    def __init__(self, engine: DetectionEngine, counter: ZoneCounter,
                 annotator: FrameAnnotator, recorder=None):
        self.engine = engine
        self.counter = counter
        self.annotator = annotator
        self.recorder = recorder

        self.queue: "queue.Queue[Packet]" = queue.Queue(maxsize=3)
        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._display_size = (0, 0)
        self._last_version = -1

        self.frame_width = 0
        self.frame_height = 0
        self.source_fps = 30.0
        self.frame_count = 0
        self.frame_idx = 0
        # (ham kare, son tespitler) — duraklatılmışken yeniden çizmek için
        self.last_raw: np.ndarray | None = None
        self.last_det: sv.Detections | None = None

    # ── video ──────────────────────────────────────────────────────
    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def open(self, path: str) -> bool:
        self.stop()
        self.release()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return False
        self._cap = cap
        self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.frame_idx = 0
        self.last_raw = self.last_det = None
        return True

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self.last_raw = self.last_det = None

    def first_frame(self) -> np.ndarray | None:
        """İlk kareyi oku ve başa sar (yalnızca oynatma yokken çağır)."""
        if not self.is_open or self.playing:
            return None
        ok, frame = self._cap.read()
        self.rewind()
        if ok:
            self.last_raw = frame
            return frame
        return None

    def rewind(self) -> None:
        if self.is_open:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.frame_idx = 0

    def set_display_size(self, w: int, h: int) -> None:
        self._display_size = (int(w), int(h))

    # ── kontrol ────────────────────────────────────────────────────
    def start(self, settings: Settings, record: bool) -> bool:
        if not self.is_open:
            return False
        if self._thread is not None and self._thread.is_alive():
            log.warning("Önceki işleme thread'i hâlâ çalışıyor; başlatılamadı.")
            return False
        self._stop.clear()
        self._last_version = -1
        self._thread = threading.Thread(
            target=self._run, args=(settings, record), daemon=True, name="video-worker")
        self._thread.start()
        return True

    def stop(self, timeout: float = 3.0) -> None:
        """Thread'i durdur ve bitmesini bekle (en fazla `timeout` sn)."""
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout)
            if t.is_alive():
                log.warning("İşleme thread'i %.1f sn içinde durmadı.", timeout)
                return
        self._thread = None

    def drain(self) -> None:
        try:
            while True:
                self.queue.get_nowait()
        except queue.Empty:
            pass

    # ── işçi thread ────────────────────────────────────────────────
    def _put(self, pkt: Packet) -> None:
        """Kuyruk doluysa en eski paketi at (UI yetişemiyorsa gecikme birikmesin)."""
        while True:
            try:
                self.queue.put_nowait(pkt)
                return
            except queue.Full:
                try:
                    old = self.queue.get_nowait()
                    # Kontrol paketini (eof/error) ve sayım güncellemesini asla kaybetme
                    if old.kind != "frame":
                        self.queue.put_nowait(old)
                        time.sleep(0.005)
                    elif old.snapshot is not None and pkt.snapshot is None:
                        pkt.snapshot = old.snapshot
                except queue.Empty:
                    pass

    def _run(self, settings: Settings, record: bool) -> None:
        cap = self._cap
        try:
            self.annotator.trace_length = settings.trace_length
            target_fps = max(1.0, min(self.source_fps, float(settings.fps_limit)))
            interval = 1.0 / target_fps
            can_drop = settings.realtime_sync and not record
            next_t = time.perf_counter()
            step = 1                      # önceki işlenen kareden bu yana geçen video karesi
            ema_fps = 0.0
            have_model = self.engine.loaded

            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    self._put(Packet("eof", frame_idx=self.frame_idx))
                    return
                self.frame_idx += 1
                t0 = time.perf_counter()

                if settings.brightness:
                    frame = cv2.convertScaleAbs(frame, alpha=1.0, beta=settings.brightness)

                det = None
                if have_model:
                    det = self.engine.infer(frame)
                    self.counter.update(det, frame_step=step)

                raw = frame.copy() if frame is not None else None
                annotated = self.annotator.draw(
                    frame, det, self.counter.areas, self.counter.zone_current())
                self.last_raw, self.last_det = raw, det

                if record and self.recorder is not None:
                    self.recorder.write_frame(annotated)

                dw, dh = self._display_size
                if dw > 1 and dh > 1:
                    interp = cv2.INTER_AREA if dw < annotated.shape[1] else cv2.INTER_LINEAR
                    shown = cv2.resize(annotated, (dw, dh), interpolation=interp)
                else:
                    shown = annotated
                rgb = cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)

                snap = None
                v = self.counter.version
                if v != self._last_version:
                    self._last_version = v
                    snap = self.counter.snapshot()

                dt = time.perf_counter() - t0
                inst = 1.0 / dt if dt > 0 else 0.0
                ema_fps = inst if ema_fps == 0 else 0.9 * ema_fps + 0.1 * inst
                self._put(Packet("frame", rgb, snap, self.frame_idx, ema_fps))

                # ── zamanlama ──
                next_t += interval
                step = 1
                slack = next_t - time.perf_counter()
                if slack > 0:
                    self._stop.wait(slack)
                else:
                    if can_drop:
                        n_skip = int(-slack / interval)
                        skipped = 0
                        for _ in range(n_skip):
                            if not cap.grab():
                                break
                            self.frame_idx += 1
                            skipped += 1
                        next_t += n_skip * interval
                        step = 1 + skipped
                    else:
                        next_t = time.perf_counter()  # borç biriktirme
        except Exception as e:  # işçi thread'i sessizce ölmesin
            log.exception("İşleme thread'inde hata")
            self._put(Packet("error", message=f"{type(e).__name__}: {e}"))
