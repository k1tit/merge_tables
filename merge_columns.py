#!/usr/bin/env python3
"""
Сборка merge_columns из config.yaml.

  python merge_columns.py              меню (одна папка или a = все)
  python merge_columns.py -s 3805      одна папка SOrg
  python merge_columns.py --all        все папки 3801-3806 -> merge_columns_3801.xlsx …
"""

from __future__ import annotations

from lib import SCRIPT_VERSION, build_merge, main

__all__ = ["SCRIPT_VERSION", "build_merge", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
