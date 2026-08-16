"""
config/settings.py
──────────────────
Re-export for ergonomic imports: `from config.settings import get_settings`
"""
from config import get_settings, Settings, ROOT_DIR

__all__ = ["get_settings", "Settings", "ROOT_DIR"]
