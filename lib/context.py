from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BuildContext:
    """Параметры одного прогона сборки отчёта."""

    base_dir: Path
    config_path: Path
    config: dict[str, Any]
    read_engine: str
    write_engine: str
    lookup_dedupe: bool
    verbose: bool
    default_merge: Any = None
    log: Callable[[str], None] | None = field(default=None, repr=False)
    log_file: Path | None = field(default=None, repr=False)

    @property
    def source_dir(self) -> str | None:
        raw = self.config.get("source_dir")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    @property
    def sorg(self) -> str:
        """Префикс в именах выгрузок (3801–3806), не имя папки."""
        return str(self.config.get("sorg") or "3805").strip()

    @property
    def sorg_template(self) -> str:
        return self.sorg

    @property
    def zw_ch6_file(self) -> str:
        return f"{self.sorg_template} ZW CH6"

    @property
    def zw_file(self) -> str:
        return f"{self.sorg_template} ZW"
