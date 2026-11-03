"""
core/database.py
────────────────
Ortak SQLite katmanı.

V8'de her sınıf kendi bağlantısını açıyor ve şemayı kendi başına
oluşturuyordu. V9'da:
  * şema tek yerde (init_db) ve `PRAGMA user_version` ile sürümlenir,
  * bağlantı `connect()` bağlam yöneticisiyle açılır/kapanır/commit edilir,
  * hatalar sessizce yutulmaz, loglanır.

Eski (V8) veritabanları olduğu gibi açılır: tablolar `IF NOT EXISTS`,
yeni tablolar ve sütunlar eklenir, eski veri korunur.
"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from core.logger import get_logger
from core.paths import DB_PATH, ensure_dirs

log = get_logger("db")

SCHEMA_VERSION = 2


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Bağlantı aç; hata olursa rollback, yoksa commit; her durumda kapat."""
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Tüm tabloları oluştur (idempotent). Uygulama açılışında bir kez çağrılır."""
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS video_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                video_path  TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                frame_count INTEGER,
                duration    REAL
            );

            -- Alan→alan geçişlerinin TOPLAMI (V8 ile uyumlu; grafik sayfası bunu okur)
            CREATE TABLE IF NOT EXISTS transition_counts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_record_id INTEGER,
                from_area       TEXT NOT NULL,
                to_area         TEXT NOT NULL,
                count           INTEGER NOT NULL,
                FOREIGN KEY (video_record_id) REFERENCES video_records(id)
            );

            -- V9: sınıf bazlı geçişler (Araba / Kamyon / Otobus ...)
            CREATE TABLE IF NOT EXISTS transition_class_counts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_record_id INTEGER,
                from_area       TEXT NOT NULL,
                to_area         TEXT NOT NULL,
                class_name      TEXT NOT NULL,
                count           INTEGER NOT NULL,
                FOREIGN KEY (video_record_id) REFERENCES video_records(id)
            );

            -- V9: alana giren benzersiz araç sayısı (takip ID'si değişse bile alan bazlı veri)
            CREATE TABLE IF NOT EXISTS zone_visit_counts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_record_id INTEGER,
                area            TEXT NOT NULL,
                class_name      TEXT NOT NULL,
                count           INTEGER NOT NULL,
                FOREIGN KEY (video_record_id) REFERENCES video_records(id)
            );
            """
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    log.info("Veritabanı hazır (şema v%d): %s", SCHEMA_VERSION, DB_PATH)


# ── Ayarlar (key/value) ──────────────────────────────────────────────
def get_setting(key: str, default: str | None = None) -> str | None:
    try:
        with connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
            )
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default
    except Exception:
        log.exception("Ayar okunamadı: %s", key)
        return default


def set_setting(key: str, value: str) -> bool:
    try:
        with connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        return True
    except Exception:
        log.exception("Ayar yazılamadı: %s", key)
        return False


# ── Sayım kaydı ──────────────────────────────────────────────────────
def save_counts(conn: sqlite3.Connection, record_id: int, snapshot) -> None:
    """
    CountSnapshot'ı (core.zones) veritabanına yaz.
    `snapshot` yerine eski tarz {(from,to): count} sözlüğü de kabul edilir.
    """
    if isinstance(snapshot, dict):
        transitions, by_class, visits = snapshot, {}, {}
    else:
        transitions = snapshot.transitions
        by_class = snapshot.transitions_by_class
        visits = snapshot.zone_visits_by_class

    for (a, b), n in transitions.items():
        if n > 0:
            conn.execute(
                "INSERT INTO transition_counts (video_record_id, from_area, to_area, count)"
                " VALUES (?, ?, ?, ?)",
                (record_id, a, b, n),
            )
    for (a, b), per_class in by_class.items():
        for cls, n in per_class.items():
            if n > 0:
                conn.execute(
                    "INSERT INTO transition_class_counts"
                    " (video_record_id, from_area, to_area, class_name, count)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (record_id, a, b, cls, n),
                )
    for area, per_class in visits.items():
        for cls, n in per_class.items():
            if n > 0:
                conn.execute(
                    "INSERT INTO zone_visit_counts"
                    " (video_record_id, area, class_name, count) VALUES (?, ?, ?, ?)",
                    (record_id, area, cls, n),
                )
