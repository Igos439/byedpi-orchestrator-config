"""Сброс порогов приёмки к базовым и очистка накопленных блокировок.

Пороги адаптив за два дня поднял сам себе (media_min_avail 0.40 -> 0.59, p95 6.2),
из-за чего приёмка стала недостижимой. Возвращаем базовые значения из
/opt/orchestrator/config/adaptive_thresholds.json и чистим yt_fail_backoff/pending_accept.
"""
import json
import shutil
import time

STATE = "/app/state/adaptive_thresholds.json"
BASE = "/opt/orchestrator/config/adaptive_thresholds.json"
STAMP = time.strftime("%Y%m%dT%H%M%S")

state = json.load(open(STATE))
base = json.load(open(BASE))

shutil.copy2(STATE, f"{STATE}.bak-hermes-{STAMP}")
print(f"бэкап порогов: {STATE}.bak-hermes-{STAMP}")

base_accept = base.get("orchestrator", {}).get("accept", {})
print("было:", json.dumps(state.get("orchestrator", {}).get("accept", {}), ensure_ascii=False))
state.setdefault("orchestrator", {}).setdefault("accept", {}).update(base_accept)
print("стало:", json.dumps(state["orchestrator"]["accept"], ensure_ascii=False))

pre_gate_base = base.get("orchestrator", {}).get("post_check", {}).get("pre_gate", {})
if pre_gate_base:
    state["orchestrator"].setdefault("post_check", {}).setdefault("pre_gate", {}).update(pre_gate_base)
    print("pre_gate:", json.dumps(state["orchestrator"]["post_check"]["pre_gate"], ensure_ascii=False))

json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=1)

for path, empty in (("/app/state/yt_fail_backoff.json", {}),
                    ("/app/state/pending_accept.json", {}),
                    ("/app/state/pending_attempts.json", {"key": "", "attempts": 0})):
    try:
        shutil.copy2(path, f"{path}.bak-hermes-{STAMP}")
    except Exception:
        pass
    json.dump(empty, open(path, "w"))
    print("очищено:", path)
