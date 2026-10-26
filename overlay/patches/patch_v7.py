#!/usr/bin/env python3
"""Nicer label for backoff log lines (video id instead of tail of url)."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()

old = '''\t\t\td[url] = {"fails": fails, "until": time.time() + delay}
\t\t\tprint(f"[orchestrator] bootstrap: backoff for {url[-11:]} after {fails} failure(s), {delay // 60} min")'''
new = '''\t\t\td[url] = {"fails": fails, "until": time.time() + delay}
\t\t\t_label = url
\t\t\ttry:
\t\t\t\t_q = urlparse(url).query
\t\t\t\tfor _part in _q.split("&"):
\t\t\t\t\tif _part.startswith("v="):
\t\t\t\t\t\t_label = _part[2:]
\t\t\t\t\t\tbreak
\t\t\t\telse:
\t\t\t\t\t_label = urlparse(url).path.rsplit("/", 1)[-1] or url[-11:]
\t\t\texcept Exception:
\t\t\t\t_label = url[-11:]
\t\t\tprint(f"[orchestrator] bootstrap: backoff for {_label} after {fails} failure(s), {delay // 60} min")'''

if "_label = url" in src:
    print("already patched")
    sys.exit(0)

assert old in src, "note label anchor missing"
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
print("patched:", PATH, "backup:", bak)
