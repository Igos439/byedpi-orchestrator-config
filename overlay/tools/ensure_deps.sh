#!/bin/sh
# Restores yt-dlp + Deno after container image update (run inside container).
set -e
command -v deno >/dev/null 2>&1 || apk add --no-cache ca-certificates deno
python3 -c 'import yt_dlp_ejs' 2>/dev/null || python3 -m pip install --upgrade --break-system-packages "yt-dlp[default]"
python3 -c 'import yt_dlp,sys; print("yt-dlp", yt_dlp.version.__version__)'
