#!/usr/bin/env python3
"""Сводит пути статистики оркестратора: коллектор пишет в /app/state (постоянный том),
генератор динамического пространства читает оттуда же.

Идемпотентно. Запускается внутри контейнера orchestrator.
"""
import json
import os
import shutil
import time

CONFIG = "/opt/orchestrator/config/stats.json"
ENTRY = "/app/entry_local.sh"
SRC_DIR = "/opt/orchestrator/state"
DST_DIR = "/app/state"
FILES = ["arg_stats.json", "arg_stats.ckpt.json"]
MARK = "# hermes:stats-paths"

PERSIST_BLOCK = """
# hermes:stats-paths — держим статистику на постоянном томе /app/state
python3 /app/patch_stats_paths.py --quiet >> "$APP/state/entry_local.log" 2>&1 || true
"""


def fix_config() -> str:
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    st = cfg.setdefault("storage", {})
    st["state_dir"] = DST_DIR
    st["cumulative_path"] = f"{DST_DIR}/arg_stats.json"
    st["dedup_checkpoint"] = f"{DST_DIR}/arg_stats.ckpt.json"
    st["runs_dir"] = f"{DST_DIR}/runs"
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)
    return st["cumulative_path"]


def migrate_stats() -> list[str]:
    done = []
    os.makedirs(DST_DIR, exist_ok=True)
    for name in FILES:
        src = os.path.join(SRC_DIR, name)
        dst = os.path.join(DST_DIR, name)
        if not os.path.exists(src):
            continue
        if os.path.exists(dst) and os.path.getsize(dst) >= os.path.getsize(src) and \
                os.path.getmtime(dst) >= os.path.getmtime(src):
            continue
        shutil.copy2(src, dst)
        done.append(f"{name} ({os.path.getsize(dst)} байт)")
    return done


def patch_entry() -> bool:
    if not os.path.exists(ENTRY):
        return False
    with open(ENTRY, "r", encoding="utf-8") as f:
        text = f.read()
    if MARK in text:
        return False
    anchor = 'log "старт обёртки'
    idx = text.find(anchor)
    if idx == -1:
        return False
    end = text.find("\n", idx)
    if end == -1:
        return False
    backup = f"{ENTRY}.bak-hermes-stats-{time.strftime('%Y%m%dT%H%M%S')}"
    shutil.copy2(ENTRY, backup)
    new_text = text[:end + 1] + PERSIST_BLOCK + text[end + 1:]
    with open(ENTRY, "w", encoding="utf-8") as f:
        f.write(new_text)
    os.chmod(ENTRY, 0o755)
    return True


def main() -> None:
    quiet = "--quiet" in os.sys.argv
    backup = f"{CONFIG}.bak-hermes-{time.strftime('%Y%m%dT%H%M%S')}"
    if os.path.exists(CONFIG):
        shutil.copy2(CONFIG, backup)
    path = fix_config()
    moved = migrate_stats()
    entry = patch_entry()
    if not quiet:
        print(f"конфиг переключён на {path}")
        print(f"бэкап конфига: {backup}")
        print("перенесено: " + (", ".join(moved) if moved else "нечего (файлы уже на месте)"))
        print("entry_local.sh обновлён" if entry else "entry_local.sh уже содержит блок (или не найден якорь)")


if __name__ == "__main__":
    main()
