#!/usr/bin/env python3
"""Алиас merge_columns.py — тот же пакет lib."""

from merge_columns import SCRIPT_VERSION, build_merge, main

__all__ = ["SCRIPT_VERSION", "build_merge", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
