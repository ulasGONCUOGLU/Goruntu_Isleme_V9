"""
page/settings/tabs/
───────────────────
Sağ içerik alanındaki sekmeler — her biri ayrı dosyada.

main.py bu paketten sekme sınıflarını import eder.
Yeni sekme: yeni dosya + buraya import + sidebar.TAB_DEFS + main.tabs
"""

from page.settings.tabs.model_tab import ModelTab
from page.settings.tabs.config_tab import ConfigTab

__all__ = ['ModelTab', 'ConfigTab']
