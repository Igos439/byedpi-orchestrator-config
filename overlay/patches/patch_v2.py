#!/usr/bin/env python3
"""Add MAX_PENDING_PASSES, PASS_TIMEOUT_SECONDS, VERBOSE_LOGS to orchestrator."""
import shutil, sys, time, py_compile

PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src
applied = []

# 1. constants
anchor = 'RECHECK_INTERVAL_SECONDS = float(os.environ.get("RECHECK_INTERVAL_SECONDS", "300"))'
add = anchor + '''
MAX_PENDING_PASSES = int(os.environ.get("MAX_PENDING_PASSES", "3"))
PASS_TIMEOUT_SECONDS = float(os.environ.get("PASS_TIMEOUT_SECONDS", "900"))
VERBOSE_LOGS = int(os.environ.get("VERBOSE_LOGS", "1"))'''
if "MAX_PENDING_PASSES =" not in src:
    assert anchor in src, "constants anchor missing"
    src = src.replace(anchor, add, 1)
    applied.append("constants")

# 2. runtime config from JSON
old_rt = '''\t\tglobal ATTEMPTS_PER_STRATEGY, TEST_TIMEOUT_SECONDS, RECHECK_INTERVAL_SECONDS
\t\ttry:
\t\t\tATTEMPTS_PER_STRATEGY = int(rt.get("attempts_per_strategy", ATTEMPTS_PER_STRATEGY))
\t\t\tTEST_TIMEOUT_SECONDS = float(rt.get("test_timeout_seconds", TEST_TIMEOUT_SECONDS))
\t\t\tRECHECK_INTERVAL_SECONDS = float(rt.get("recheck_interval_seconds", RECHECK_INTERVAL_SECONDS))'''
new_rt = '''\t\tglobal ATTEMPTS_PER_STRATEGY, TEST_TIMEOUT_SECONDS, RECHECK_INTERVAL_SECONDS
\t\tglobal MAX_PENDING_PASSES, PASS_TIMEOUT_SECONDS, VERBOSE_LOGS
\t\ttry:
\t\t\tATTEMPTS_PER_STRATEGY = int(rt.get("attempts_per_strategy", ATTEMPTS_PER_STRATEGY))
\t\t\tTEST_TIMEOUT_SECONDS = float(rt.get("test_timeout_seconds", TEST_TIMEOUT_SECONDS))
\t\t\tRECHECK_INTERVAL_SECONDS = float(rt.get("recheck_interval_seconds", RECHECK_INTERVAL_SECONDS))
\t\t\tMAX_PENDING_PASSES = int(rt.get("max_pending_passes", MAX_PENDING_PASSES))
\t\t\tPASS_TIMEOUT_SECONDS = float(rt.get("pass_timeout_seconds", PASS_TIMEOUT_SECONDS))
\t\t\tVERBOSE_LOGS = int(rt.get("verbose_logs", VERBOSE_LOGS))'''
if 'rt.get("max_pending_passes"' not in src:
    assert old_rt in src, "runtime anchor missing"
    src = src.replace(old_rt, new_rt, 1)
    applied.append("runtime-config")

# 3. helpers before orchestrate_once
helpers = '''def _pending_attempts_file() -> str:
\treturn os.path.join(STATE_DIR, "pending_attempts.json")


def _load_pending_attempts() -> Tuple[str, int]:
\ttry:
\t\twith open(_pending_attempts_file(), "r", encoding="utf-8") as f:
\t\t\td = json.load(f)
\t\treturn str(d.get("key", "")), int(d.get("attempts", 0))
\texcept Exception:
\t\treturn "", 0


def _save_pending_attempts(key: str, attempts: int) -> None:
\ttry:
\t\tos.makedirs(STATE_DIR, exist_ok=True)
\t\twith open(_pending_attempts_file(), "w", encoding="utf-8") as f:
\t\t\tjson.dump({"key": key, "attempts": int(attempts)}, f)
\texcept Exception:
\t\tpass


'''
anchor2 = "def orchestrate_once() -> None:"
if "def _pending_attempts_file" not in src:
    assert anchor2 in src, "orchestrate_once anchor missing"
    src = src.replace(anchor2, helpers + anchor2, 1)
    applied.append("helpers")

# 4. attempt accounting before best_per_domain
anchor3 = "\tbest_per_domain: Dict[str, List[str]] = {}"
block = '''\t# Bound retries of the sticky pending candidate
\tif pending_strat is not None:
\t\t_pk, _pa = _load_pending_attempts()
\t\t_key_now = _normalize_strategy_key(pending_strat)
\t\t_pa = _pa + 1 if _pk == _key_now else 1
\t\tif MAX_PENDING_PASSES > 0 and _pa > MAX_PENDING_PASSES:
\t\t\tif VERBOSE_LOGS:
\t\t\t\tprint(f"[orchestrator] pending: giving up after {_pa - 1} attempt(s); full search resumes")
\t\t\t_save_pending_accept("")
\t\t\t_save_pending_attempts("", 0)
\t\t\tpending_strat = None
\t\telse:
\t\t\t_save_pending_attempts(_key_now, _pa)
\t\t\tif VERBOSE_LOGS:
\t\t\t\tprint(f"[orchestrator] pending: attempt {_pa}/{MAX_PENDING_PASSES} key={_key_now[:60]}")
\t
'''
if "Bound retries of the sticky pending" not in src:
    assert anchor3 in src, "best_per_domain anchor missing"
    src = src.replace(anchor3, block + anchor3, 1)
    applied.append("pending-accounting")

# 5. verbose pass summary
anchor4 = '''\t\tif best is not None:
\t\t\t# optional post-check of top-N with overlays across full candidate set'''
summary = '''\t\tif VERBOSE_LOGS:
\t\t\ttry:
\t\t\t\t_n_cand = 1 if pending_strat is not None else len(strategies)
\t\t\t\t_n_eval = len(results) if hasattr(results, "__len__") else 0
\t\t\t\tprint(f"[orchestrator] pass: targets={len(targets_once)} candidates={_n_cand} evaluated={_n_eval} best={'yes' if best is not None else 'none'}")
\t\t\texcept Exception:
\t\t\t\tpass
\t\tif best is not None:
\t\t\t# optional post-check of top-N with overlays across full candidate set'''
if "[orchestrator] pass: targets=" not in src:
    assert anchor4 in src, "best-is-not-none anchor missing"
    src = src.replace(anchor4, summary, 1)
    applied.append("verbose-summary")

# 6. keep pending on failure instead of clearing it
old_pend = '''\t\t\t\t# Manage sticky pending key
\t\t\t\tif ACCEPT_STICKY_UNTIL_ACCEPT:
\t\t\t\t\tif ok_acc and streak < max(1, ACCEPT_REQUIRE_CONSECUTIVE):
\t\t\t\t\t\t_save_pending_accept(key, final_best)
\t\t\t\t\telse:
\t\t\t\t\t\t_save_pending_accept("")'''
new_pend = '''\t\t\t\t# Manage sticky pending key
\t\t\t\tif ACCEPT_STICKY_UNTIL_ACCEPT:
\t\t\t\t\tif ok_acc and streak < max(1, ACCEPT_REQUIRE_CONSECUTIVE):
\t\t\t\t\t\t_save_pending_accept(key, final_best)
\t\t\t\t\t\t_save_pending_attempts(key, 0)
\t\t\t\t\telif not ok_acc:
\t\t\t\t\t\t# retry the same candidate on the next pass; attempts are bounded
\t\t\t\t\t\t_save_pending_accept(key, final_best)
\t\t\t\t\t\tif VERBOSE_LOGS:
\t\t\t\t\t\t\ttry:
\t\t\t\t\t\t\t\tprint(f"[orchestrator] accept: pending kept for retry (reasons={';'.join(reasons) if reasons else 'none'})")
\t\t\t\t\t\t\texcept Exception:
\t\t\t\t\t\t\t\tpass
\t\t\t\t\telse:
\t\t\t\t\t\t_save_pending_accept("")
\t\t\t\t\t\t_save_pending_attempts("", 0)'''
if "pending kept for retry" not in src:
    assert old_pend in src, "pending-manage anchor missing"
    src = src.replace(old_pend, new_pend, 1)
    applied.append("pending-retry")

# 7. pass timeout in main loop
old_main = '''def main() -> None:
\tsignal.signal(signal.SIGTERM, signal_handler)
\tsignal.signal(signal.SIGINT, signal_handler)
\t
\twhile True:
\t\ttry:
\t\t\torchestrate_once()
\t\texcept Exception as e:
\t\t\tprint(f"[orchestrator] error: {e}")
\t\ttime.sleep(RECHECK_INTERVAL_SECONDS)'''
new_main = '''def _pass_timeout_handler(signum, frame):
\traise TimeoutError(f"pass exceeded {PASS_TIMEOUT_SECONDS:.0f}s")


def main() -> None:
\tsignal.signal(signal.SIGTERM, signal_handler)
\tsignal.signal(signal.SIGINT, signal_handler)
\tsignal.signal(signal.SIGALRM, _pass_timeout_handler)
\tif VERBOSE_LOGS:
\t\tprint(f"[orchestrator] runtime: pass_timeout={PASS_TIMEOUT_SECONDS:.0f}s max_pending_passes={MAX_PENDING_PASSES} verbose={VERBOSE_LOGS}")
\twhile True:
\t\ttry:
\t\t\tif PASS_TIMEOUT_SECONDS > 0:
\t\t\t\tsignal.alarm(int(max(60, PASS_TIMEOUT_SECONDS)))
\t\t\torchestrate_once()
\t\texcept TimeoutError:
\t\t\tprint("[orchestrator] pass timeout; stopping canary and continuing")
\t\t\ttry:
\t\t\t\tstop_canary_ciadpi()
\t\t\texcept Exception:
\t\t\t\tpass
\t\texcept Exception as e:
\t\t\tprint(f"[orchestrator] error: {e}")
\t\tfinally:
\t\t\tif PASS_TIMEOUT_SECONDS > 0:
\t\t\t\tsignal.alarm(0)
\t\ttime.sleep(RECHECK_INTERVAL_SECONDS)'''
if "def _pass_timeout_handler" not in src:
    assert old_main in src, "main anchor missing"
    src = src.replace(old_main, new_main, 1)
    applied.append("pass-timeout")

if src == orig:
    print("nothing to change (already patched?)")
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
print("applied:", ", ".join(applied))
