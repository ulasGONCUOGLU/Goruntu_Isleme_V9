"""
page/main_container/save.py
───────────────────────────
Analiz videosu kaydı + sayımların veritabanına yazılması.

V8'den farklar:
  * Yollar core.paths'ten gelir (çalışma dizininden bağımsız).
  * Veritabanı işleri core.database üzerinden (ortak bağlantı/şema).
  * Sayımlar yalnızca toplam değil, sınıf bazlı ve alan girişleriyle de kaydedilir.
"""

import os
from datetime import datetime

import cv2

from core.database import connect, save_counts
from core.logger import get_logger
from core.paths import VIDEO_DIR, ensure_dirs

log = get_logger("save")


class VideoRecorder:
    """Video kayıt ve veritabanı işlemleri"""

    def __init__(self):
        self.video_writer = None
        self.recording = False
        self.frame_count = 0
        self.temp_video_path = None
        self.video_dir = str(VIDEO_DIR)
        ensure_dirs()

    # ── kayıt ──────────────────────────────────────────────────────
    def start_recording(self, frame_width, frame_height, fps=30):
        if self.recording:
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(self.video_dir, f"temp_{timestamp}.mp4")
        writer = cv2.VideoWriter(
            temp_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame_width, frame_height)
        )
        if not writer.isOpened():
            log.error("VideoWriter açılamadı: %s", temp_path)
            return False

        self.video_writer = writer
        self.temp_video_path = temp_path
        self.frame_count = 0
        self.recording = True
        return True

    def write_frame(self, frame):
        """İşçi thread'inden çağrılır (cv2.VideoWriter thread içinde kullanılabilir)."""
        w = self.video_writer
        if self.recording and w is not None:
            w.write(frame)
            self.frame_count += 1

    def stop_recording(self, name=None, snapshot=None):
        """
        Kaydı durdur.
        name      : None ise geçici dosya silinir (kayıt iptal)
        snapshot  : core.zones.CountSnapshot (veya eski tarz {(a,b): n} sözlüğü)
        """
        if not self.recording:
            return None
        self.recording = False

        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        temp = self.temp_video_path
        if not name:
            if temp and os.path.exists(temp):
                os.remove(temp)
            return None

        safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip() or "kayit"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = os.path.join(self.video_dir, f"{safe_name}_{timestamp}.mp4")

        if temp and os.path.exists(temp):
            if os.path.exists(video_path):
                os.remove(video_path)
            os.rename(temp, video_path)

        record_id = self._insert_record(name, video_path, self.frame_count, snapshot)
        return {"id": record_id, "name": name, "video_path": video_path,
                "frame_count": self.frame_count}

    def save_transition_counts_only(self, name, snapshot):
        """Video dosyası oluşturmadan yalnızca sayımları kaydet."""
        if not _has_any_count(snapshot):
            return None
        return self._insert_record(name, "", 0, snapshot)

    # ── veritabanı ─────────────────────────────────────────────────
    @staticmethod
    def _insert_record(name, video_path, frame_count, snapshot):
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO video_records (name, video_path, frame_count) VALUES (?, ?, ?)",
                (name, video_path, frame_count),
            )
            record_id = cur.lastrowid
            if snapshot is not None:
                save_counts(conn, record_id, snapshot)
        log.info("Kayıt eklendi: id=%s ad=%s", record_id, name)
        return record_id

    def get_all_records(self):
        with connect() as conn:
            return conn.execute(
                "SELECT id, name, video_path, created_at, frame_count"
                " FROM video_records ORDER BY created_at DESC"
            ).fetchall()

    def get_transition_counts(self, video_record_id):
        with connect() as conn:
            return conn.execute(
                "SELECT from_area, to_area, count FROM transition_counts"
                " WHERE video_record_id = ?",
                (video_record_id,),
            ).fetchall()

    def get_class_counts(self, video_record_id):
        with connect() as conn:
            return conn.execute(
                "SELECT from_area, to_area, class_name, count FROM transition_class_counts"
                " WHERE video_record_id = ?",
                (video_record_id,),
            ).fetchall()

    def cleanup(self):
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        self.recording = False


def _has_any_count(snapshot) -> bool:
    if snapshot is None:
        return False
    data = snapshot if isinstance(snapshot, dict) else snapshot.transitions
    return any(n > 0 for n in data.values())
