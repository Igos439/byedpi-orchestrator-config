#!/usr/bin/env python3
"""Let sanitize_tokens keep the new -R (round) token."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src

old = "\t\t\t# positional with caps\n"
new = (
    "\t\t\t# non-positional: round\n"
    "\t\t\tif t.startswith(\"-R\"):\n"
    "\t\t\t\tkey = \"round\"\n"
    "\t\t\t\tif key in seen_singletons: continue\n"
    "\t\t\t\tseen_singletons.add(key); out.append(t); continue\n"
    "\t\t\t# positional with caps\n"
)

if 'key = "round"' in src:
    print("already patched")
    sys.exit(0)
assert src.count(old) >= 1, "anchor not found"
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
