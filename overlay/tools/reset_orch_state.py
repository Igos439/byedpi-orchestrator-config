"""Сброс состояния оркестратора: старт поиска стратегий с нуля.

Очищаем накопленный «лучший» набор и историю последних результатов, чтобы генератор
не отталкивался от чемпиона, а искал заново. Все файлы копируются рядом с суффиксом
.bak-hermes-<время>, откат — обратным копированием.
"""
import json
import os
import shutil
import time

STATE = "/app/state"
STAMP = time.strftime("%Y%m%dT%H%M%S")

# файл -> чем заменить
TARGETS = {
    "best_strategies.json": {},
    "last_results.json": {},
    "pending_accept.json": {},
    "pending_attempts.json": {"key": "", "attempts": 0},
    "yt_fail_backoff.json": {},
}

for name, empty in TARGETS.items():
    path = os.path.join(STATE, name)
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.bak-hermes-{STAMP}")
        print(f"бэкап: {name} -> {name}.bak-hermes-{STAMP}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(empty, f)
    print(f"очищено: {name}")

cand = os.path.join(STATE, "candidate_strategy.txt")
if os.path.exists(cand):
    shutil.copy2(cand, f"{cand}.bak-hermes-{STAMP}")
    open(cand, "w").close()
    print("очищено: candidate_strategy.txt")

print("состояние сброшено")
