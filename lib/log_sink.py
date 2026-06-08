from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .context import BuildContext


def emit(ctx: BuildContext, message: str, *, newline: bool = True) -> None:
    """Сообщение в GUI/консоль и в merge_build.log (если задан log_file)."""
    text = message if message.endswith("\n") or not newline else message + "\n"
    if ctx.log is not None:
        ctx.log(text)
    else:
        end = "\n" if newline else ""
        try:
            print(message, end=end, flush=True)
        except Exception:
            pass
    # GUI пишет merge_build.log через log(); без дубля
    if ctx.log_file is not None and ctx.log is None:
        append_log_file(ctx.log_file, text)


def append_log_file(path: Path, text: str) -> None:
    line = text if text.endswith("\n") else text + "\n"
    try:
        with path.open("a", encoding="utf-8-sig") as fh:
            fh.write(line)
            fh.flush()
    except OSError:
        pass


def open_build_log(base_dir: Path) -> Path:
    """Создать/очистить merge_build.log рядом с программой."""
    path = base_dir / "merge_build.log"
    path.write_text("", encoding="utf-8-sig")
    return path
