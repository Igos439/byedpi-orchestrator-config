"""Шаг 3, часть 3: канареечный прокси переводим на удалённое разрешение имён (socks5h).

Причина: bootstrap и резолвинг googlevideo шли через socks5://127.0.0.1:1081 с флагом -4.
yt-dlp разрешал имя локально и отдавал канарейке IP, а ciadpi на этих IP отвечал
"Host unreachable" — при том что подключение по домену через тот же прокси проходит.
Плюс -4 убираем: разрешение имени теперь делает сама канарейка.
"""
import shutil
import time

TARGET = "/opt/orchestrator/orchestrator_with_canary.py"
BAK = f"{TARGET}.bak-step3proxy-{time.strftime('%Y%m%dT%H%M%S')}"

OLD_PROXY = 'CANARY_PROXY = os.environ.get("CANARY_PROXY", f"socks5://127.0.0.1:{CANARY_PORT}")'
NEW_PROXY = 'CANARY_PROXY = os.environ.get("CANARY_PROXY", f"socks5h://127.0.0.1:{CANARY_PORT}")'

OLD_CMD = '\t\t\t"yt-dlp", "-4", "-g", "-f", "bv*+ba/b",'
NEW_CMD = '\t\t\t"yt-dlp", "-g", "-f", "bv*+ba/b",'

src = open(TARGET, encoding="utf-8").read()
changed = []
if NEW_PROXY in src:
    print("прокси уже socks5h")
elif OLD_PROXY in src:
    src = src.replace(OLD_PROXY, NEW_PROXY, 1)
    changed.append("CANARY_PROXY -> socks5h")
else:
    print("не нашёл строку CANARY_PROXY")

if NEW_CMD in src:
    print("флаг -4 уже убран")
elif OLD_CMD in src:
    src = src.replace(OLD_CMD, NEW_CMD, 1)
    changed.append("убран -4 из yt-dlp")
else:
    print("не нашёл команду yt-dlp")

if not changed:
    raise SystemExit(0)

shutil.copy2(TARGET, BAK)
open(TARGET, "w", encoding="utf-8").write(src)
print(f"бэкап: {BAK}")
print("изменено:", ", ".join(changed))
try:
    compile(src, TARGET, "exec")
    print("компиляция ок")
except SyntaxError as e:
    shutil.copy2(BAK, TARGET)
    print("ошибка компиляции, откат:", e)
    raise SystemExit(1)
