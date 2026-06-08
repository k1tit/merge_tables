from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """Корень дистрибутива: рядом с .exe или с merge_columns.py."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return project_root() / "config.yaml"
