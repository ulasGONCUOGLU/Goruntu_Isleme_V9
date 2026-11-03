"""
core/paths.py
─────────────
Tüm yollar burada. V8'deki göreli yollar ("dosyalar/...") uygulama başka
bir klasörden başlatılınca model ve veritabanını bulamıyordu; artık yollar
bu dosyanın konumuna (veya PyInstaller .exe'nin konumuna) göre hesaplanır.
"""

import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
# GORUNTU_DATA_DIR ortam değişkeni ile veri klasörü başka yere taşınabilir
# (testler, taşınabilir kurulum, birden çok proje).
DOSYALAR_DIR = Path(os.environ.get("GORUNTU_DATA_DIR") or (BASE_DIR / "dosyalar"))
VIDEO_DIR = DOSYALAR_DIR / "video"          # kaydedilen analiz videoları
MODEL_TRAIN_DIR = DOSYALAR_DIR / "Model"    # eğitim çıktıları (best.pt ...)
AREAS_DIR = DOSYALAR_DIR / "alanlar"        # kaydedilen alan şablonları (.json)
LOG_DIR = DOSYALAR_DIR / "logs"
DB_PATH = DOSYALAR_DIR / "database.db"


def ensure_dirs() -> None:
    for d in (DOSYALAR_DIR, VIDEO_DIR, MODEL_TRAIN_DIR, AREAS_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
