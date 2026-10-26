#!/usr/bin/env python3
"""Tee orchestrator stdout into /app/state/orch_verbose.log when VERBOSE_LOGS=1."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src
applied = []

if "\nimport sys\n" not in src:
    assert "\nimport signal\n" in src
    src = src.replace("\nimport signal\n", "\nimport signal\nimport sys\n", 1)
    applied.append("import-sys")

tee = '''class _Tee:
\tdef __init__(self, *streams):
\t\tself.streams = streams

\tdef write(self, data):
\t\tfor st in self.streams:
\t\t\ttry:
\t\t\t\tst.write(data)
\t\t\t\tst.flush()
\t\t\texcept Exception:
\t\t\t\tpass
\t\treturn len(data)

\tdef flush(self):
\t\tfor st in self.streams:
\t\t\ttry:
\t\t\t\tst.flush()
\t\t\texcept Exception:
\t\t\t\tpass


'''
if "class _Tee:" not in src:
    anchor = "def _pass_timeout_handler(signum, frame):"
    assert anchor in src
    src = src.replace(anchor, tee + anchor, 1)
    applied.append("tee-class")

anchor2 = '''\tif VERBOSE_LOGS:
\t\tprint(f"[orchestrator] runtime: pass_timeout={PASS_TIMEOUT_SECONDS:.0f}s max_pending_passes={MAX_PENDING_PASSES} verbose={VERBOSE_LOGS}")'''
hook = anchor2 + '''
\tif VERBOSE_LOGS:
\t\ttry:
\t\t\t_log_path = os.path.join(STATE_DIR, "orch_verbose.log")
\t\t\tif os.path.exists(_log_path) and os.path.getsize(_log_path) > 5 * 1024 * 1024:
\t\t\t\tos.replace(_log_path, _log_path + ".1")
\t\t\t_log_f = open(_log_path, "a", encoding="utf-8", buffering=1)
\t\t\tsys.stdout = _Tee(sys.stdout, _log_f)
\t\t\tprint(f"[orchestrator] verbose log: {_log_path}")
\t\texcept Exception:
\t\t\tpass'''
if "verbose log:" not in src:
    assert anchor2 in src, "main verbose anchor missing"
    src = src.replace(anchor2, hook, 1)
    applied.append("tee-hookup")

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
