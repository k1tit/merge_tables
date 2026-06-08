# -*- coding: utf-8 -*-
"""Корректный UTF-8 в .exe на Windows (интерфейс и print в журнал)."""

from __future__ import annotations

import os
import sys


def bootstrap() -> None:
    if sys.platform != "win32":
        return

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# При импорте пакета на Windows — сразу включить UTF-8 в консоли
bootstrap()
