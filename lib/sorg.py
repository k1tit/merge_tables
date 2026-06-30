from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .constants import DEFAULT_SORG_DIRS, SORG_FILE_PREFIX_RE

FOLDER_MISSING = "папка отсутствует"
FOLDER_XLSX_COUNT = "Excel-файлов: {n}"


class SorgSelector:
    """Выбор папки SOrg (3801–3806) и подстановка имён файлов в config."""

    def __init__(self, base_dir: Path, cfg: dict[str, Any]) -> None:
        self.base_dir = base_dir
        self.cfg = cfg

    @property
    def template(self) -> str:
        return str(self.cfg.get("sorg") or self.cfg.get("source_dir") or "3805").strip()

    @property
    def choices(self) -> list[str]:
        configured = self.cfg.get("sorg_dirs")
        if configured:
            return [str(x).strip() for x in configured]
        return list(DEFAULT_SORG_DIRS)

    @property
    def default(self) -> str:
        return str(self.cfg.get("source_dir") or self.template).strip()

    def config_for(self, selected: str) -> tuple[dict[str, Any], str]:
        """Подготовить config для выбранной папки SOrg (GUI / --sorg)."""
        folder = str(selected).strip()
        if folder not in self.choices:
            print(
                f"  ВНИМАНИЕ: папка SOrg {folder!r} не в списке {self.choices!r}",
                file=sys.stderr,
            )
        data_path = self.base_dir / folder
        if not data_path.is_dir():
            raise FileNotFoundError(
                f"Папка SOrg {folder!r} не найдена: {data_path.resolve()}\n"
                f"Создайте каталог и скопируйте в него Excel (как для шаблона {self.template!r})."
            )
        prepared, file_prefix = self._prepare(folder)
        if file_prefix != folder:
            print(
                f"  Префикс в именах файлов: {file_prefix} "
                f"(папка данных: {folder})",
                file=sys.stderr,
            )
        return prepared, folder

    @staticmethod
    def detect_file_prefix(folder: Path) -> str | None:
        """Определить 3801–3806 по префиксу в именах Excel в папке."""
        if not folder.is_dir():
            return None
        counts: Counter[str] = Counter()
        for path in list(folder.glob("*.xlsx")) + list(folder.glob("*.xls")):
            match = SORG_FILE_PREFIX_RE.match(path.stem)
            if match:
                counts[match.group(0)] += 1
        if not counts:
            return None
        return counts.most_common(1)[0][0]

    def folder_status(self, sorg: str) -> str:
        folder = self.base_dir / sorg
        if not folder.is_dir():
            return FOLDER_MISSING
        n = self._count_xlsx(folder)
        return FOLDER_XLSX_COUNT.format(n=n)

    def resolve(
        self,
        *,
        cli_sorg: str | None,
        no_menu: bool,
    ) -> tuple[dict[str, Any], str]:
        if cli_sorg:
            return self.config_for(cli_sorg)
        if no_menu:
            return self.config_for(self.default)
        if sys.stdin.isatty():
            return self.config_for(self._pick_interactive())
        return self.config_for(self.default)

    def _prepare(self, folder: str) -> tuple[dict[str, Any], str]:
        out = copy.deepcopy(self.cfg)
        data_path = self.base_dir / folder
        file_prefix = self.detect_file_prefix(data_path) or folder
        if self.template != file_prefix:
            self._rewrite_files(out, self.template, file_prefix)
        out["source_dir"] = folder
        out["sorg"] = file_prefix
        return out, file_prefix

    @staticmethod
    def _rewrite_files(node: Any, template: str, sorg: str) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "file" and isinstance(val, str) and val.startswith(template):
                    node[key] = sorg + val[len(template) :]
                else:
                    SorgSelector._rewrite_files(val, template, sorg)
        elif isinstance(node, list):
            for item in node:
                SorgSelector._rewrite_files(item, template, sorg)

    def _pick_interactive(self) -> str:
        print("\n  Выбор папки SOrg (откуда читать Excel)\n")
        for i, name in enumerate(self.choices, 1):
            folder = self.base_dir / name
            n = self._count_xlsx(folder)
            exists = "да" if folder.is_dir() else "нет"
            prefix = self.detect_file_prefix(folder)
            prefix_hint = f", префикс файлов: {prefix}" if prefix else ""
            hint = "  ← Enter" if name == self.default else ""
            print(f"    {i}. {name}  — папка: {exists}, Excel: {n}{prefix_hint}{hint}")
        print("    0. Выход")

        while True:
            try:
                raw = input(
                    f"\n  Номер [1–{len(self.choices)}] или код "
                    f"({', '.join(self.choices)}), Enter = {self.default}: "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Отмена.")
                raise SystemExit(130) from None
            if not raw:
                return self.default
            if raw == "0":
                raise SystemExit(0)
            if raw.isdigit():
                num = int(raw)
                if 1 <= num <= len(self.choices):
                    return self.choices[num - 1]
            if raw in self.choices:
                return raw
            print(
                f"  Неверный ввод. Укажите 1–{len(self.choices)}, код папки "
                f"({', '.join(self.choices)}) или Enter."
            )

    @staticmethod
    def _count_xlsx(folder: Path) -> int:
        if not folder.is_dir():
            return 0
        return len(list(folder.glob("*.xlsx")) + list(folder.glob("*.xls")))
