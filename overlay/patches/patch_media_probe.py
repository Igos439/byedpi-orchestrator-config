#!/usr/bin/env python3
"""Патч приёма: сохраняем итоги прохода и логируем неудачные медиа-пробы.

Проблемы, которые лечим:
1) save_state() вызывался только в конце прохода, а при отказе или недоборе
   гистерезиса функция делала return раньше — best_strategies.json и
   last_results.json не обновлялись вовсе (замирали на дате последнего приёма).
2) Порог серии по умолчанию 2 при том, что победитель каждый проход разный:
   streak никогда не достигал 2, приём не фиксировался.

Патч идемпотентен: если маркер уже есть — выходим без изменений.
"""
import shutil
import sys
import time
import py_compile

PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/orchestrator/orchestrator_with_canary.py"
MARK = "hermes:save-last-results"

src = open(PATH, encoding="utf-8").read()

if MARK in src or ("def save_last_results" in src and "probe FAIL" in src):
    print("already patched")
    sys.exit(0)

orig = src

# 1. Своя функция сохранения итогов прохода (только last_results)
anchor = "def save_state(best_per_domain"
helper = (
    'def save_last_results(results: Dict[str, Any]) -> None:\n'
    '\t"""%s: пишем итоги прохода даже при отказе кандидата."""\n'
    '\ttry:\n'
    '\t\tos.makedirs(STATE_DIR, exist_ok=True)\n'
    '\t\twith open(os.path.join(STATE_DIR, "last_results.json"), "w", encoding="utf-8") as f:\n'
    '\t\t\tjson.dump(results, f, ensure_ascii=False, indent=2)\n'
    '\texcept Exception:\n'
    '\t\tpass\n'
    '\n\n'
) % MARK
if anchor not in src:
    print("anchor save_state not found")
    sys.exit(2)
src = src.replace(anchor, helper + anchor, 1)

# 2. Сохраняем результаты перед ранними return в блоке accept
old_reject = '\t\t\t\t\t\tprint(f"[orchestrator] accept: REJECT update (below thresholds): {reasons}")\n\t\t\t\t\t\treturn'
new_reject = old_reject.replace("\t\t\t\t\t\treturn", "\t\t\t\t\t\tsave_last_results(all_results)\n\t\t\t\t\t\treturn")
if old_reject in src:
    src = src.replace(old_reject, new_reject, 1)
else:
    print("warn: REJECT anchor not found")

old_wait = '\t\t\t\t\t\tprint(f"[orchestrator] accept: WAIT hysteresis streak={streak}/{ACCEPT_REQUIRE_CONSECUTIVE}")\n\t\t\t\t\t\treturn'
new_wait = old_wait.replace("\t\t\t\t\t\treturn", "\t\t\t\t\t\tsave_last_results(all_results)\n\t\t\t\t\t\treturn")
if old_wait in src:
    src = src.replace(old_wait, new_wait, 1)
else:
    print("warn: WAIT anchor not found")

# 3. Порог серии по умолчанию 1 (значение из strategy_space может переопределить)
old_hyst = "ACCEPT_REQUIRE_CONSECUTIVE = 2"
new_hyst = 'ACCEPT_REQUIRE_CONSECUTIVE = int(os.environ.get("ACCEPT_REQUIRE_CONSECUTIVE", "1"))'
if old_hyst in src:
    src = src.replace(old_hyst, new_hyst, 1)
else:
    print("warn: ACCEPT_REQUIRE_CONSECUTIVE default not found")

# 4. Логируем только неудачные медиа-пробы, чтобы не забивать журнал
old_probe = (
    '\t\t\t\tif ok:\n'
    '\t\t\t\t\tall_success_latencies.append(lat)'
)
new_probe = (
    '\t\t\t\tif (not ok) and (("googlevideo.com" in d) or ("/videoplayback" in d)):\n'
    '\t\t\t\t\tprint(f"[orchestrator] probe FAIL | {short_label(d)} lat={lat:.3f} {note}", flush=True)\n'
    '\t\t\t\tif ok:\n'
    '\t\t\t\t\tall_success_latencies.append(lat)'
)
if old_probe in src:
    src = src.replace(old_probe, new_probe, 1)
else:
    print("warn: probe anchor not found")

if src == orig:
    print("nothing to change")
    sys.exit(0)

bak = PATH + ".bak-hermes-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(PATH, bak)
open(PATH, "w", encoding="utf-8").write(src)
try:
    py_compile.compile(PATH, doraise=True)
except Exception as e:
    shutil.copy2(bak, PATH)
    print("COMPILE FAILED, rolled back:", e)
    sys.exit(5)

print("patched:", PATH)
print("backup:", bak)
