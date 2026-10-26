#!/usr/bin/env python3
"""Bootstrap: resolve only missing urls, with failure backoff."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src
applied = []

helpers = '''def _yt_backoff_file() -> str:
\treturn os.path.join(STATE_DIR, "yt_fail_backoff.json")


def _load_yt_backoff() -> Dict[str, Any]:
\ttry:
\t\twith open(_yt_backoff_file(), "r", encoding="utf-8") as f:
\t\t\td = json.load(f)
\t\treturn d if isinstance(d, dict) else {}
\texcept Exception:
\t\treturn {}


def _yt_backoff_active(url: str, now: float) -> bool:
\titem = _load_yt_backoff().get(url) or {}
\ttry:
\t\treturn float(item.get("until", 0) or 0) > now
\texcept Exception:
\t\treturn False


def _note_yt_result(url: str, ok: bool) -> None:
\ttry:
\t\td = _load_yt_backoff()
\t\tif ok:
\t\t\td.pop(url, None)
\t\telse:
\t\t\tfails = int((d.get(url) or {}).get("fails", 0)) + 1
\t\t\tdelay = min(7200, 900 * (2 ** (fails - 1)))
\t\t\td[url] = {"fails": fails, "until": time.time() + delay}
\t\t\tprint(f"[orchestrator] bootstrap: backoff for {url[-11:]} after {fails} failure(s), {delay // 60} min")
\t\twith open(_yt_backoff_file(), "w", encoding="utf-8") as f:
\t\t\tjson.dump(d, f)
\texcept Exception:
\t\tpass


'''
anchor = "def _yt_cache_fresh_for(url: str, cache: Dict[str, Any], now: float, margin: int = 600) -> bool:"
if "_yt_backoff_active" not in src:
    assert anchor in src
    src = src.replace(anchor, helpers + anchor, 1)
    applied.append("backoff-helpers")

old_guard = '''\tif all(_yt_cache_fresh_for(u, _cache0, _now0) for u in watch_urls):
\t\tprint("[orchestrator] bootstrap: cache is fresh for all urls; skipping")
\t\treturn'''
new_guard = old_guard + '''
\t_need: List[str] = []
\t_skip_fresh = 0
\t_skip_backoff = 0
\tfor _u in watch_urls:
\t\tif _yt_cache_fresh_for(_u, _cache0, _now0):
\t\t\t_skip_fresh += 1
\t\t\tcontinue
\t\tif _yt_backoff_active(_u, _now0):
\t\t\t_skip_backoff += 1
\t\t\tcontinue
\t\t_need.append(_u)
\tif not _need:
\t\tprint(f"[orchestrator] bootstrap: nothing to resolve (fresh={_skip_fresh}, backoff={_skip_backoff}); skipping")
\t\treturn
\tif _skip_fresh or _skip_backoff:
\t\tprint(f"[orchestrator] bootstrap: resolving {len(_need)} of {len(watch_urls)} url(s) (fresh={_skip_fresh}, backoff={_skip_backoff})")
\twatch_urls = _need'''
if "nothing to resolve" not in src:
    assert old_guard in src, "guard anchor missing"
    src = src.replace(old_guard, new_guard, 1)
    applied.append("need-filter")

old_call = '''\t\t\t\tlinks = resolve_youtube_to_googlevideo(u, max_links=max(1, YT_MAX_MEDIA_URLS))'''
new_call = '''\t\t\t\tlinks = resolve_youtube_to_googlevideo(u, max_links=max(1, YT_MAX_MEDIA_URLS))
\t\t\t\t_note_yt_result(u, bool(links))'''
if "_note_yt_result(u, bool(links))" not in src:
    assert old_call in src, "resolve call anchor missing"
    src = src.replace(old_call, new_call, 1)
    applied.append("note-result")

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
