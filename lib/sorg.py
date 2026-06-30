from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .constants import DEFAULT_SORG_DIRS, SORG_FILE_PREFIX_RE

FOLDER_MISSING = "папка отсутствует"
FOLDER_XLSX_COUNT = "Excel-файлов: {n}"
ALL_SORG_LABEL = "ALL"
ALL_MENU_CHOICE = "__all__"


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

    def existing_folders(self) -> list[str]:
        """Существующие каталоги SOrg (3801–3806)."""
        return [name for name in self.choices if (self.base_dir / name).is_dir()]

    def available_folders(self) -> list[str]:
        """Папки SOrg с хотя бы одним Excel."""
        return [
            name
            for name in self.existing_folders()
            if self._count_xlsx(self.base_dir / name) > 0
        ]

    def prepare_all(self) -> list[tuple[dict[str, Any], str]]:
        """Конфиг для каждой папки SOrg (сначала с Excel, иначе все существующие)."""
        folders = self.available_folders() or self.existing_folders()
        if not folders:
            raise FileNotFoundError(
                "Нет папок SOrg. "
                f"Создайте каталоги {', '.join(self.choices)} в {self.base_dir.resolve()}"
            )
        if not self.available_folders():
            print(
                "  ВНИМАНИЕ: Excel в папках SOrg не найден — сборка по всем каталогам.",
                file=sys.stderr,
            )
        return [self.config_for(folder) for folder in folders]

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
        cli_all: bool = False,
    ) -> tuple[dict[str, Any] | None, str, list[tuple[dict[str, Any], str]] | None]:
        """
        Один SOrg: (cfg, folder, None).
        Все папки: (None, ALL_SORG_LABEL, [(cfg, folder), ...]).
        """
        if cli_all:
            runs = self.prepare_all()
            return None, ALL_SORG_LABEL, runs
        if cli_sorg:
            cfg, folder = self.config_for(cli_sorg)
            return cfg, folder, None
        if no_menu:
            cfg, folder = self.config_for(self.default)
            return cfg, folder, None
        if sys.stdin.isatty():
            picked = self._pick_interactive()
            if picked == ALL_MENU_CHOICE:
                runs = self.prepare_all()
                return None, ALL_SORG_LABEL, runs
            cfg, folder = self.config_for(picked)
            return cfg, folder, None
        cfg, folder = self.config_for(self.default)
        return cfg, folder, None

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
        existing = self.existing_folders()
        if existing:
            with_data = self.available_folders()
            scope = ", ".join(with_data) if with_data else ", ".join(existing)
            print(f"    a. Все папки — расширенная проверка ({scope})")
        print("    0. Выход")

        while True:
            try:
                raw = input(
                    f"\n  Номер [1–{len(self.choices)}], код "
                    f"({', '.join(self.choices)}), a = все папки, Enter = {self.default}: "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Отмена.")
                raise SystemExit(130) from None
            if not raw:
                return self.default
            if raw == "0":
                raise SystemExit(0)
            if raw.lower() in ("a", "all", "все", "*") and existing:
                return ALL_MENU_CHOICE
            if raw.isdigit():
                num = int(raw)
                if 1 <= num <= len(self.choices):
                    return self.choices[num - 1]
            if raw in self.choices:
                return raw
            print(
                f"  Неверный ввод. Укажите 1–{len(self.choices)}, код папки, "
                f"a = все папки, или Enter."
            )

    @staticmethod
    def _count_xlsx(folder: Path) -> int:
        if not folder.is_dir():
            return 0
        seen: set[str] = set()
        for pattern in ("*.xlsx", "*.xls", "*.XLSX", "*.XLS"):
            for path in folder.glob(pattern):
                seen.add(path.name.lower())
        return len(seen)
