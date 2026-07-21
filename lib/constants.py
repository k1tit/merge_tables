from __future__ import annotations

import re

SCRIPT_VERSION = "2026-06-04-oop-v1"
EXCEL_MAX_ROWS = 1_048_576
REQUIRED_CH6_COLUMNS = ("ZW_CH6_Name", "ZW_CH6")
DEFAULT_SORG_DIRS = tuple(f"380{i}" for i in range(1, 7))
SORG_DIR_RE = re.compile(r"^380[1-6]$")
SORG_FILE_PREFIX_RE = re.compile(r"^380[1-6]\b")

ID_COLUMN_KEYS = frozenset(
    {
        "customer",
        "kunnr",
        "ktonr",
        "vkorg",
        "sorg",
        "hglvcust",
        "cgrp",
        "hlsor",
        "hldch",
        "hldiv",
    }
)

FILE_ALIASES = {
    "References_CH6": "References_CH6.xlsx",
    "References_CH6.xlsx": "References_CH6.xlsx",
    "Справочник_CH6": "References_CH6.xlsx",
    "Справочник_CH6_CGrp": "References_CH6.xlsx",
    "Справочник_CH6 SO": "References_CH6.xlsx",
    "Справочник Ключ-Иерархия": "References_CH6.xlsx",
    "Справочник At Work&Education": "References_CH6.xlsx",
    "trade": "trade.xlsx",
}

REFERENCES_CH6_FILE = "References_CH6.xlsx"
