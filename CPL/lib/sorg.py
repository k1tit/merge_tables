from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from .constants import DEFAULT_SORG_DIRS


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

    def resolve(
        self,
        *,
        cli_sorg: str | None,
        no_menu: bool,
    ) -> tuple[dict[str, Any], str]:
        if cli_sorg:
            selected = str(cli_sorg).strip()
        elif no_menu:
            selected = self.default
        elif sys.stdin.isatty():
            selected = self._pick_interactive()
        else:
            selected = self.default

        if selected not in self.choices:
            print(
                f"  ВНИМАНИЕ: папка SOrg {selected!r} не в списке {self.choices!r}",
                file=sys.stderr,
            )

        folder = self.base_dir / selected
        if not folder.is_dir():
            raise FileNotFoundError(
                f"Папка SOrg {selected!r} не найдена: {folder.resolve()}\n"
                f"Создайте каталог и скопируйте в него Excel (как для шаблона {self.template!r})."
            )

        return self._prepare(selected), selected

    def _prepare(self, sorg: str) -> dict[str, Any]:
        out = copy.deepcopy(self.cfg)
        if self.template != sorg:
            self._rewrite_files(out, self.template, sorg)
        out["source_dir"] = sorg
        return out

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
        print("\n=== Выбор папки SOrg (данные для сборки) ===\n")
        for i, name in enumerate(self.choices, 1):
            folder = self.base_dir / name
            n = self._count_xlsx(folder)
            exists = "да" if folder.is_dir() else "нет"
            hint = ""
            if name == self.default:
                hint += " [по умолчанию из config]"
            if name == self.template:
                hint += f" [шаблон имён файлов: {self.template}]"
            print(f"  {i}. {name}  — папка: {exists}, файлов Excel: {n}{hint}")
        print("  0. Выход")

        while True:
            try:
                raw = input(
                    f"\nНомер [1-{len(self.choices)}] или код "
                    f"({', '.join(self.choices)}), Enter = {self.default}: "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nОтмена.")
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
