#!/usr/bin/env python3
"""Throttle YouTube bootstrap: cache guard, strategy cap, sleep-requests."""
import shutil, sys, time, py_compile

PATH = "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src
applied = []

# 1. constants
anchor = 'YT_DLP_TIMEOUT_SECONDS = float(os.environ.get("YT_DLP_TIMEOUT_SECONDS", "20"))'
if "BOOTSTRAP_MAX_STRATEGIES =" not in src:
    assert anchor in src
    src = src.replace(anchor, anchor + '''
BOOTSTRAP_MAX_STRATEGIES = int(os.environ.get("BOOTSTRAP_MAX_STRATEGIES", "2"))
YT_SLEEP_REQUESTS = float(os.environ.get("YT_SLEEP_REQUESTS", "2"))''', 1)
    applied.append("constants")

# 2. runtime overrides
old_runtime = '\t\t\tVERBOSE_LOGS = int(rt.get("verbose_logs", VERBOSE_LOGS))'
if 'rt.get("bootstrap_max_strategies"' not in src:
    assert old_runtime in src
    src = src.replace(old_runtime, old_runtime + '''
\t\t\tBOOTSTRAP_MAX_STRATEGIES = int(rt.get("bootstrap_max_strategies", BOOTSTRAP_MAX_STRATEGIES))
\t\t\tYT_SLEEP_REQUESTS = float(rt.get("yt_sleep_requests", YT_SLEEP_REQUESTS))''', 1)
    src = src.replace(
        "\t\tglobal MAX_PENDING_PASSES, PASS_TIMEOUT_SECONDS, VERBOSE_LOGS",
        "\t\tglobal MAX_PENDING_PASSES, PASS_TIMEOUT_SECONDS, VERBOSE_LOGS\n\t\tglobal BOOTSTRAP_MAX_STRATEGIES, YT_SLEEP_REQUESTS",
        1)
    applied.append("runtime-overrides")

# 3. yt-dlp sleep between requests
old_cmd = '''\t\t\t"yt-dlp", "-4", "-g", "-f", "bv*+ba/b",
\t\t\t"--proxy", CANARY_PROXY,'''
new_cmd = '''\t\t\t"yt-dlp", "-4", "-g", "-f", "bv*+ba/b",
\t\t\t"--proxy", CANARY_PROXY,
\t\t\t"--sleep-requests", str(max(0.0, YT_SLEEP_REQUESTS)),'''
if '"--sleep-requests"' not in src:
    assert old_cmd in src
    src = src.replace(old_cmd, new_cmd, 1)
    applied.append("sleep-requests")

# 4. cache freshness helper before bootstrap
helper = '''def _yt_cache_fresh_for(url: str, cache: Dict[str, Any], now: float, margin: int = 600) -> bool:
\t"""True when the cache already holds unexpired media links for this url."""
\ttry:
\t\titem = cache.get(url) or {}
\t\tts = float(item.get("ts", 0) or 0)
\t\tif not ts or (now - ts) > max(60, YT_CACHE_TTL):
\t\t\treturn False
\t\tmedia = item.get("media") or []
\t\tif not media:
\t\t\treturn False
\t\tfor link in media:
\t\t\texp = _link_expire(str(link))
\t\t\tif exp is None or exp - now < margin:
\t\t\t\treturn False
\t\treturn True
\texcept Exception:
\t\treturn False


'''
anchor_boot = "def bootstrap_youtube_rr_hosts(watch_urls: List[str]) -> None:"
if "_yt_cache_fresh_for" not in src:
    assert anchor_boot in src
    src = src.replace(anchor_boot, helper + anchor_boot, 1)
    applied.append("cache-helper")

# 5. bootstrap guard + strategy cap
old_head = '''\tif not watch_urls:
\t\treturn
\tprint(f"[orchestrator] bootstrap: resolving YouTube for {len(watch_urls)} url(s)")
\tfound_any = False
\tfor idx, strat in enumerate(YOUTUBE_BOOTSTRAP_STRATEGIES, start=1):
\t\ttry:
\t\t\tprint(f"[orchestrator] bootstrap: trying strategy {idx}/{len(YOUTUBE_BOOTSTRAP_STRATEGIES)}")'''
new_head = '''\tif not watch_urls:
\t\treturn
\t_cache0 = _load_yt_cache()
\t_now0 = time.time()
\tif all(_yt_cache_fresh_for(u, _cache0, _now0) for u in watch_urls):
\t\tprint("[orchestrator] bootstrap: cache is fresh for all urls; skipping")
\t\treturn
\tprint(f"[orchestrator] bootstrap: resolving YouTube for {len(watch_urls)} url(s)")
\tfound_any = False
\t_boot_strats = YOUTUBE_BOOTSTRAP_STRATEGIES[:max(1, BOOTSTRAP_MAX_STRATEGIES)]
\tfor idx, strat in enumerate(_boot_strats, start=1):
\t\ttry:
\t\t\tprint(f"[orchestrator] bootstrap: trying strategy {idx}/{len(_boot_strats)}")'''
if "cache is fresh for all urls" not in src:
    assert old_head in src, "bootstrap head anchor missing"
    src = src.replace(old_head, new_head, 1)
    applied.append("cache-guard")

# 6. spacing between watch urls inside a strategy
old_loop = '''\t\t\tfor u in watch_urls:
\t\t\t\tlinks = resolve_youtube_to_googlevideo(u, max_links=max(1, YT_MAX_MEDIA_URLS))'''
new_loop = '''\t\t\tfor _ui, u in enumerate(watch_urls):
\t\t\t\tif _ui and YT_SLEEP_REQUESTS > 0:
\t\t\t\t\ttime.sleep(float(YT_SLEEP_REQUESTS))
\t\t\t\tlinks = resolve_youtube_to_googlevideo(u, max_links=max(1, YT_MAX_MEDIA_URLS))'''
if "if _ui and YT_SLEEP_REQUESTS" not in src:
    assert old_loop in src, "url loop anchor missing"
    src = src.replace(old_loop, new_loop, 1)
    applied.append("url-spacing")

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
