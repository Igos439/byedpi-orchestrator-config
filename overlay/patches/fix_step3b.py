"""Второе исправление шага 3: добавляет недостающую константу CHAMPION_FILE.

Без неё _load_champion_units() падал с NameError, ошибка глоталась в except,
и генератор молча возвращался к старым случайным цепочкам.
"""
import shutil
import time

TARGET = "/opt/orchestrator/orchestrator_with_canary.py"
BAK = f"{TARGET}.bak-step3fix2-{time.strftime('%Y%m%dT%H%M%S')}"

src = open(TARGET, encoding="utf-8").read()
if 'CHAMPION_FILE = ' in src:
    print("константа уже есть")
else:
    anchor = 'CHAMPION_CACHE = {"path": None, "mtime": 0.0, "units": None}'
    if anchor not in src:
        print("не нашёл точку вставки")
        raise SystemExit(1)
    shutil.copy2(TARGET, BAK)
    src = src.replace(anchor, 'CHAMPION_FILE = "/app/state/best_strategies.json"\n' + anchor, 1)
    open(TARGET, "w", encoding="utf-8").write(src)
    print(f"бэкап: {BAK}")
    try:
        compile(src, TARGET, "exec")
        print("компиляция ок")
    except SyntaxError as e:
        shutil.copy2(BAK, TARGET)
        print("ошибка компиляции, откат:", e)
        raise SystemExit(1)
