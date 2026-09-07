"""
config/settings.py
──────────────────
Re-export for ergonomic imports: `from backend.app.core.config.settings import get_settings`
"""
from backend.app.core.config import get_settings, Settings, ROOT_DIR

__all__ = ["get_settings", "Settings", "ROOT_DIR"]
