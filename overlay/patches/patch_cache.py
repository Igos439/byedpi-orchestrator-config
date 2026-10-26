#!/usr/bin/env python3
"""Drop expired records from yt_hosts_cache on save."""
import shutil, sys, time, py_compile

PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()

old = '''def _save_yt_cache(data: Dict[str, Any]) -> None:
\ttry:
\t\tos.makedirs(STATE_DIR, exist_ok=True)'''
new = '''def _save_yt_cache(data: Dict[str, Any]) -> None:
\ttry:
\t\t_now = time.time()
\t\tdata = {
\t\t\tk: v for k, v in (data or {}).items()
\t\t\tif isinstance(v, dict) and _media_fresh(v.get("media") or [], _now)
\t\t}
\t\tos.makedirs(STATE_DIR, exist_ok=True)'''

if "data = {\n\t\t\tk: v for k, v in" in src:
    print("already patched")
    sys.exit(0)
if old not in src:
    print("FAIL: _save_yt_cache anchor not found")
    sys.exit(2)

bak = PATH + ".bak-hermes-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(PATH, bak)
open(PATH, "w", encoding="utf-8").write(src.replace(old, new, 1))
try:
    py_compile.compile(PATH, doraise=True)
except Exception as e:
    shutil.copy2(bak, PATH)
    print("COMPILE FAILED, rolled back:", e)
    sys.exit(3)
print("purge patch applied; backup:", bak)
