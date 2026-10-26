"""Шаг 3, часть 2: bootstrap резолвинга rr-хостов пробует сначала проверенный набор.

Причина правки: в журнале "bootstrap: failed to resolve YouTube rr-hosts" и
"test-prewarm: start media=0" — значит медиа-целей нет вообще, медиа-доступность
считается нулевой и приёмка всегда падает по media_avail, хотя главная открывается 3/3.
Bootstrap использовал только слабые наборы из YOUTUBE_BOOTSTRAP_STRATEGIES, которые
сейчас режутся на youtubei.
"""
import shutil
import time

TARGET = "/opt/orchestrator/orchestrator_with_canary.py"
BAK = f"{TARGET}.bak-step3boot-{time.strftime('%Y%m%dT%H%M%S')}"

OLD = "\t_boot_strats = YOUTUBE_BOOTSTRAP_STRATEGIES[:max(1, BOOTSTRAP_MAX_STRATEGIES)]"
NEW = ("\t# шаг 3: сначала пробуем проверенный набор, затем штатные bootstrap-стратегии\n"
       "\t_champ_args = _flatten_units(_load_champion_units())\n"
       "\t_boot_strats = ([_champ_args] if _champ_args else []) + list(YOUTUBE_BOOTSTRAP_STRATEGIES)\n"
       "\t_boot_strats = _boot_strats[:max(1, BOOTSTRAP_MAX_STRATEGIES) + (1 if _champ_args else 0)]")

src = open(TARGET, encoding="utf-8").read()
if NEW.splitlines()[0] in src:
    print("уже пропатчено")
    raise SystemExit(0)
if OLD not in src:
    print("не нашёл точку вставки")
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
