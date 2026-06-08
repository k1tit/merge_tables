from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


CYRILLIC_FONTS = ("Segoe UI", "Tahoma", "Arial", "Microsoft Sans Serif", "Verdana")


def pick_font(size: int = 10) -> tuple[str, int]:
    try:
        families = set(tkfont.families())
        for name in CYRILLIC_FONTS:
            if name in families:
                return (name, size)
    except tk.TclError:
        pass
    return ("TkDefaultFont", size)


def apply_ttk_theme(root: tk.Tk) -> tuple[str, int]:
    font = pick_font(10)
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "winnative" in style.theme_names():
            style.theme_use("winnative")
        style.configure(".", font=font)
        style.configure("TButton", font=font)
        style.configure("TLabel", font=font)
        style.configure("TCombobox", font=(font[0], font[1] + 1))
    except tk.TclError:
        root.option_add("*Font", f"{font[0]} {font[1]}")
    return font
