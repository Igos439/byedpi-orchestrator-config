#!/usr/bin/env python3
"""Добавляет в /app/entry_local.sh блок установки ядра ciadpi (идемпотентно)."""
import os
import shutil
import time

ENTRY = "/app/entry_local.sh"
MARK = "# hermes:dpi-core"
BLOCK = """
# hermes:dpi-core — при старте контейнера ставим ядро ciadpi из /app/dpi-core
sh /app/dpi-core/install_core.sh >> "$APP/state/entry_local.log" 2>&1 || true
"""


def main() -> None:
    with open(ENTRY, "r", encoding="utf-8") as f:
        text = f.read()
    if MARK in text:
        print("блок уже есть")
        return
    anchor = 'log "старт обёртки'
    idx = text.find(anchor)
    if idx == -1:
        print("якорь не найден — правка не применена")
        raise SystemExit(1)
    end = text.find("\n", idx)
    backup = f"{ENTRY}.bak-hermes-dpi-{time.strftime('%Y%m%dT%H%M%S')}"
    shutil.copy2(ENTRY, backup)
    text = text[:end + 1] + BLOCK + text[end + 1:]
    with open(ENTRY, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(ENTRY, 0o755)
    print(f"блок добавлен, бэкап: {backup}")


if __name__ == "__main__":
    main()
