"""
page/settings/db.py
───────────────────
Ayarların kalıcı saklanması — artık core.database üzerinden.

V8'de burada ayrı bir bağlantı açılıyor ve hatalar `except: pass` ile
yutuluyordu. V9'da hatalar loglanır (dosyalar/logs/app.log).

API aynı kalır:
    db_get('active_model')            →  "egitim1/weights/best.pt"
    db_set('active_model', 'x/best.pt')
"""

from core.database import get_setting, set_setting


def db_get(key: str) -> str | None:
    return get_setting(key)


def db_set(key: str, value: str) -> None:
    set_setting(key, value)
