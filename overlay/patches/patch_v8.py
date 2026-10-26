#!/usr/bin/env python3
"""Add --round (-R) op: apply desync to the Nth request."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src
applied = []

# 1. to_short
old_ts = '''\tif op == "udp_fake":
\t\treturn f"-a{val}" if val is not None else "-a"'''
new_ts = old_ts + '''
\tif op == "round":
\t\treturn f"-R{val}" if val else "-R"'''
if 'if op == "round":' not in src:
    assert old_ts in src
    src = src.replace(old_ts, new_ts, 1)
    applied.append("to_short")

# 2. value selection
old_val = '''\t\telif op == "udp_fake":
\t\t\t# Already config-first, keep as is
\t\t\tval = str(random.choice(flags.get("udp_fake", [0, 1])))'''
new_val = old_val + '''
\t\telif op == "round":
\t\t\tval = str(random.choice(flags.get("round", [1, 2, 3])))'''
if 'flags.get("round"' not in src:
    assert old_val in src
    src = src.replace(old_val, new_val, 1)
    applied.append("value")

# 3. normalize short -> long
old_norm = '''\t\telif p.startswith("-a") and p != "-a":
\t\t\targs.extend(["--udp-fake", p[2:]])'''
new_norm = '''\t\telif p.startswith("-R") and p != "-R":
\t\t\targs.extend(["--round", p[2:]])
\t\telif p.startswith("-a") and p != "-a":
\t\t\targs.extend(["--udp-fake", p[2:]])'''
if '"--round"' not in src:
    assert old_norm in src
    src = src.replace(old_norm, new_norm, 1)
    applied.append("normalize")

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
print("applied:", ", ".join(applied))
