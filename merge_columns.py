#!/usr/bin/env python3
"""Сборка merge_columns.xlsx из config.yaml."""

from __future__ import annotations

from lib import SCRIPT_VERSION, build_merge, main

__all__ = ["SCRIPT_VERSION", "build_merge", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
