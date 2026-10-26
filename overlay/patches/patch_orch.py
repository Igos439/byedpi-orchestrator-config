#!/usr/bin/env python3
"""Patch orchestrator_with_canary.py: IPv4-only, cookies, expire filtering."""
import os, re, shutil, sys, time, py_compile

PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/orchestrator/orchestrator_with_canary.py"
src = open(PATH, encoding="utf-8").read()
orig = src

# 1) import parse_qs
if "parse_qs" not in src:
    src = src.replace(
        "from urllib.parse import urlparse",
        "from urllib.parse import urlparse, parse_qs",
        1,
    )

# 2) helpers after YT_CACHE_TTL
helpers = '''

def _link_expire(url: str):
\t"""Return expire timestamp from a googlevideo URL or None."""
\ttry:
\t\tq = parse_qs(urlparse(url).query)
\t\tv = q.get("expire") or q.get("expire_at")
\t\treturn int(v[0]) if v else None
\texcept Exception:
\t\treturn None


def _media_fresh(media, now_ts: float, min_ttl: int = 120) -> bool:
\t"""True when at least one cached media link is still valid."""
\tif not media:
\t\treturn False
\tfor m in media:
\t\texp = _link_expire(m)
\t\tif exp is None or exp - now_ts > min_ttl:
\t\t\treturn True
\treturn False
'''
if "_media_fresh" not in src:
    m = re.search(r"^YT_CACHE_TTL = .*$", src, re.M)
    if not m:
        print("FAIL: YT_CACHE_TTL not found")
        sys.exit(2)
    src = src[:m.end()] + helpers + src[m.end():]

# 3) yt-dlp command: -4, cookies support
old_cmd = '''\t\tcmd = [
\t\t\t"yt-dlp", "-g", "-f", "bv*+ba/b",
\t\t\t"--proxy", CANARY_PROXY,
\t\t\t"--socket-timeout", str(int(max(1, YT_DLP_TIMEOUT_SECONDS))),
\t\t\turl,
\t\t]'''
new_cmd = '''\t\tcmd = [
\t\t\t"yt-dlp", "-4", "-g", "-f", "bv*+ba/b",
\t\t\t"--proxy", CANARY_PROXY,
\t\t\t"--extractor-args", "youtube:player_client=android_vr,default",
\t\t\t"--socket-timeout", str(int(max(1, YT_DLP_TIMEOUT_SECONDS))),
\t\t]
\t\t_cookies = os.environ.get("YT_DLP_COOKIES", "/app/cookies.txt")
\t\tif _cookies and os.path.exists(_cookies):
\t\t\tcmd += ["--cookies", _cookies]
\t\tcmd.append(url)'''
if old_cmd in src:
    src = src.replace(old_cmd, new_cmd, 1)
elif '"-4", "-g"' not in src:
    print("FAIL: yt-dlp cmd block not found")
    sys.exit(3)

# 4) drop expired links
old_loop = '''\t\tif proc.returncode == 0:
\t\t\tfor line in proc.stdout.splitlines():
\t\t\t\tline = line.strip()
\t\t\t\tif not line:
\t\t\t\t\tcontinue
\t\t\t\tif "googlevideo.com" in line:
\t\t\t\t\tlinks.append(line)
\t\t\t\t\tif len(links) >= max_links:
\t\t\t\t\t\tbreak'''
new_loop = '''\t\tif proc.returncode == 0:
\t\t\t_now = time.time()
\t\t\t_skipped = 0
\t\t\tfor line in proc.stdout.splitlines():
\t\t\t\tline = line.strip()
\t\t\t\tif not line or "googlevideo.com" not in line:
\t\t\t\t\tcontinue
\t\t\t\t_exp = _link_expire(line)
\t\t\t\tif _exp is not None and _exp - _now < 120:
\t\t\t\t\t_skipped += 1
\t\t\t\t\tcontinue
\t\t\t\tlinks.append(line)
\t\t\t\tif len(links) >= max_links:
\t\t\t\t\tbreak
\t\t\tif _skipped:
\t\t\t\ttry:
\t\t\t\t\tprint(f"[orchestrator] yt-dlp: skipped {_skipped} expired link(s)")
\t\t\t\texcept Exception:
\t\t\t\t\tpass'''
if old_loop in src:
    src = src.replace(old_loop, new_loop, 1)
elif "_skipped" not in src:
    print("FAIL: link loop not found")
    sys.exit(4)

# 5) cache read: require fresh media
src = src.replace(
    'if rec and (now_ts - float(rec.get("ts", 0)) < YT_CACHE_TTL):',
    'if rec and (now_ts - float(rec.get("ts", 0)) < YT_CACHE_TTL) and _media_fresh(rec.get("media") or [], now_ts):',
)

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
print("checks:",
      "-4" if '"-4", "-g"' in src else "NO-4",
      "| cookies" if "YT_DLP_COOKIES" in src else "| NO-COOKIES",
      "| expire" if "_link_expire" in src else "| NO-EXPIRE",
      "| cache-fresh" if "_media_fresh(rec" in src else "| NO-CACHE")
