#!/usr/bin/env python3
"""Windows entrypoint for google-colab-cli (termios is Linux-only)."""

from __future__ import annotations

import sys
import types


def _shim_posix_tty() -> None:
    if sys.platform != "win32":
        return
    if "termios" not in sys.modules:
        termios = types.ModuleType("termios")
        termios.TCSANOW = 0
        termios.tcgetattr = lambda _fd: []  # type: ignore[attr-defined]
        termios.tcsetattr = lambda *_a, **_k: None  # type: ignore[attr-defined]
        sys.modules["termios"] = termios
    if "tty" not in sys.modules:
        tty = types.ModuleType("tty")
        tty.setraw = lambda *_a, **_k: None  # type: ignore[attr-defined]
        sys.modules["tty"] = tty


def main() -> None:
    _shim_posix_tty()
    from colab_cli.cli import main as colab_main

    colab_main()


if __name__ == "__main__":
    main()
