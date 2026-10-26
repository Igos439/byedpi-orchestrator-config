#!/usr/bin/env python3
"""Record bootstrap failure when the watch page is unreachable, so backoff engages."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src

old = '''\t\tall_ok = True
\t\tfor u in watch_urls:
\t\t\tok, _, _ = check_connectivity(u)  # lightweight GET to watch page via canary
\t\t\tif not ok:
\t\t\t\tall_ok = False
\t\t\t\tbreak'''
new = '''\t\tall_ok = True
\t\tfor u in watch_urls:
\t\t\tok, _, _ = check_connectivity(u)  # lightweight GET to watch page via canary
\t\t\tif not ok:
\t\t\t\t_note_yt_result(u, False)
\t\t\t\tall_ok = False
\t\t\t\tbreak'''

if "_note_yt_result(u, False)" in src:
    print("already patched")
    sys.exit(0)

assert old in src, "connectivity loop anchor missing"
src = src.replace(old, new, 1)
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
