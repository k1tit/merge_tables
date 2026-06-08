#!/usr/bin/env python3
"""
Собирает merge_columns.xlsx из указанных колонок исходных Excel-файлов.
Настройка — в config.yaml (рядом со скриптом).

Логика в пакете lib/ (классы ReportBuilder, SorgSelector, DataMerger, …).
"""

from __future__ import annotations

from lib import SCRIPT_VERSION, build_merge, main

__all__ = ["SCRIPT_VERSION", "build_merge", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
