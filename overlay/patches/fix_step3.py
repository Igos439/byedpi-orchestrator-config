"""Исправление шага 3: max_candidates читается из space, а не из локальной переменной,
которая на момент вызова ещё не определена."""
import shutil
import time

TARGET = "/opt/orchestrator/orchestrator_with_canary.py"
BAK = f"{TARGET}.bak-step3fix-{time.strftime('%Y%m%dT%H%M%S')}"

src = open(TARGET, encoding="utf-8").read()
before = src

src = src.replace(
    "\ttry:\n\t\tchampion_mutants = generate_champion_mutants(space, max_candidates)",
    '\t_mc = int(space.get("max_candidates", 100))\n\ttry:\n\t\tchampion_mutants = generate_champion_mutants(space, _mc)', 1)
src = src.replace("\t\ttarget_random = max(4, max_candidates // 4)",
                  "\t\ttarget_random = max(4, _mc // 4)", 1)

if src == before:
    print("нечего менять — возможно, уже исправлено")
else:
    shutil.copy2(TARGET, BAK)
    open(TARGET, "w", encoding="utf-8").write(src)
    print(f"бэкап: {BAK}")
    try:
        compile(src, TARGET, "exec")
        print("компиляция ок")
    except SyntaxError as e:
        shutil.copy2(BAK, TARGET)
        print("ошибка компиляции, откат:", e)
