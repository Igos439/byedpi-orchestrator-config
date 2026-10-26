"""Шаг 3, часть 5: увеличиваем таймауты httpx-клиента.

Проверка доступности watch-страницы шла с read=5s, а через DPI-обход страница
открывается 4,7–8 с: клиент рвал соединение, bootstrap объявлял ролик недоступным,
медиа-целей не появлялось (media=0) и приёмка всегда падала по media_avail.
"""
import shutil
import time

TARGET = "/opt/orchestrator/orchestrator_with_canary.py"
BAK = f"{TARGET}.bak-step3timeout-{time.strftime('%Y%m%dT%H%M%S')}"

OLD = "\ttimeout=httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)"
NEW = "\ttimeout=httpx.Timeout(connect=10.0, read=25.0, write=10.0, pool=10.0)"

src = open(TARGET, encoding="utf-8").read()
if NEW in src:
    print("таймауты уже увеличены")
    raise SystemExit(0)
if OLD not in src:
    print("не нашёл строку таймаута")
    raise SystemExit(1)

shutil.copy2(TARGET, BAK)
src = src.replace(OLD, NEW, 1)
open(TARGET, "w", encoding="utf-8").write(src)
print(f"бэкап: {BAK}")
try:
    compile(src, TARGET, "exec")
    print("компиляция ок")
except SyntaxError as e:
    shutil.copy2(BAK, TARGET)
    print("ошибка компиляции, откат:", e)
    raise SystemExit(1)
