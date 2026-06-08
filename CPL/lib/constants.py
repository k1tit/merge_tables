from __future__ import annotations

import re

SCRIPT_VERSION = "2026-06-04-oop-v1"
REQUIRED_CH6_COLUMNS = ("ZW_CH6_Name", "HgLvCust.")
DEFAULT_SORG_DIRS = tuple(f"380{i}" for i in range(1, 7))
SORG_DIR_RE = re.compile(r"^380[1-6]$")

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
    "Справочник_CH6": "Справочник_CH6_CGrp.xlsx",
    "Справочник_CH6_CGrp": "Справочник_CH6_CGrp.xlsx",
    "Справочник Ключ-Иерархия": "Справочник Ключ-Иерархия.xlsx",
}
