from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from .builder import build_merge
from .constants import REQUIRED_CH6_COLUMNS, SCRIPT_VERSION
from .log_sink import make_console_log
from .sorg import SorgSelector


class Application:
    """Точка входа: argparse, меню SOrg, интерактивный вывод сборки."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self.args = self._parse_args(argv)

    @staticmethod
    def _parse_args(argv: list[str] | None) -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description="Сборка merge_columns.xlsx из config.yaml"
        )
        parser.add_argument(
            "-c",
            "--config",
            type=Path,
            default=Path(__file__).resolve().parent.parent / "config.yaml",
            help="Путь к config.yaml",
        )
        parser.add_argument(
            "-s",
            "--sorg",
            metavar="3805",
            help="Папка SOrg (3801–3806) без меню",
        )
        parser.add_argument(
            "-i",
            "--interactive",
            action="store_true",
            help="Интерактивное меню SOrg (по умолчанию в терминале)",
        )
        parser.add_argument(
            "--no-menu",
            action="store_true",
            help="Без меню: source_dir/sorg из config.yaml",
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="Минимум вывода (только итог или ошибка)",
        )
        return parser.parse_args(argv)

    def _is_interactive(self) -> bool:
        if self.args.quiet or self.args.no_menu or self.args.sorg:
            return False
        return self.args.interactive or sys.stdin.isatty()

    @staticmethod
    def _print_banner() -> None:
        print()
        print("=" * 52)
        print(f"  merge_columns — сборка отчёта  ({SCRIPT_VERSION})")
        print("=" * 52)

    @staticmethod
    def _print_selection(selected: str, cfg: dict) -> None:
        prefix = str(cfg.get("sorg") or selected).strip()
        print()
        print(f"  Выбрано: папка данных {selected}")
        if prefix != selected:
            print(f"           префикс в именах файлов: {prefix}")
        print()
        print("  Сборка (шаги ниже)...")
        print()

    @staticmethod
    def _print_done(out: Path, *, exit_code: int, log_file: Path) -> None:
        print()
        print("-" * 52)
        if exit_code == 0:
            size = out.stat().st_size
            print(f"  Готово: {out.resolve()}")
            print(f"  Размер: {size:,} байт".replace(",", " "))
        else:
            print("  Сборка завершена с предупреждениями — см. вывод выше")
        print(f"  Журнал: {log_file.resolve()}")
        print("-" * 52)
        print()

    def run(self) -> int:
        config_path = self.args.config.resolve()
        base_dir = config_path.parent
        interactive = self._is_interactive()
        log_file = base_dir / "merge_build.log"

        try:
            with config_path.open(encoding="utf-8") as f:
                raw_cfg = yaml.safe_load(f)

            if interactive:
                self._print_banner()

            selector = SorgSelector(base_dir, raw_cfg)
            cfg, selected = selector.resolve(
                cli_sorg=self.args.sorg,
                no_menu=self.args.no_menu or bool(self.args.sorg),
                force_interactive=self.args.interactive,
            )

            cfg_run = dict(cfg)
            if self.args.quiet:
                cfg_run["verbose"] = False

            if interactive:
                self._print_selection(selected, cfg_run)
            elif not self.args.quiet and (self.args.sorg or self.args.no_menu):
                print(f"  SOrg: {selected}")

            log = (
                make_console_log(log_file)
                if (interactive or not self.args.quiet)
                else None
            )

            out = build_merge(config_path, cfg=cfg_run, log=log)
            exit_code = self._verify_output(out, quiet=self.args.quiet)

            if not self.args.quiet:
                self._print_done(out, exit_code=exit_code, log_file=log_file)

            if interactive and sys.stdin.isatty():
                try:
                    input("Enter — выход... ")
                except (EOFError, KeyboardInterrupt):
                    print()

            return exit_code
        except (FileNotFoundError, KeyError, ValueError, PermissionError) as e:
            print(f"\nОшибка: {e}\n", file=sys.stderr)
            if interactive and sys.stdin.isatty():
                try:
                    input("Enter — выход... ")
                except (EOFError, KeyboardInterrupt):
                    pass
            return 1

    @staticmethod
    def _verify_output(out: Path, *, quiet: bool) -> int:
        exit_code = 0
        try:
            hdr = pd.read_excel(out, nrows=0)
            cols = list(hdr.columns)
            if quiet:
                return 0
            print(f"  Колонок в файле: {len(cols)}")
            for c in REQUIRED_CH6_COLUMNS:
                if c in cols:
                    print(f"    {c} — колонка №{cols.index(c) + 1}")
                else:
                    print(
                        f"    {c} — НЕТ в файле! "
                        f"Нужен {SCRIPT_VERSION} и config с enrich_from"
                    )
                    exit_code = 1
        except Exception as e:
            if not quiet:
                print(f"  (не удалось проверить заголовки: {e})")
            exit_code = 1
        return exit_code


def main() -> int:
    return Application().run()
