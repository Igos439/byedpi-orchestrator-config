#!/bin/sh
# hermes:dpi-core — ставит ядро ciadpi из /app/dpi-core, если версия отличается.
# Атомарная подмена через mv: запущенные процессы остаются на старой версии,
# новые запуски берут новую. Идемпотентно.
SRC=/app/dpi-core/ciadpi-x86_64
DST=/usr/local/bin/ciadpi
LOG=/app/state/dpi_core.log

[ -f "$SRC" ] || exit 0
[ -f "$DST" ] || exit 0

cur=$("$DST" --version 2>/dev/null | head -1 | tr -d '\r')
new=$("$SRC" --version 2>/dev/null | head -1 | tr -d '\r')
[ -n "$new" ] || exit 0
[ "$cur" = "$new" ] && exit 0

[ -n "$cur" ] && cp -f "$DST" "/app/dpi-core/ciadpi-$cur.backup" 2>/dev/null
cp -f "$SRC" "$DST.new" || exit 1
chmod 755 "$DST.new" || exit 1
mv -f "$DST.new" "$DST" || exit 1
echo "$(date '+%Y-%m-%d %H:%M:%S') ciadpi $cur -> $("$DST" --version 2>/dev/null | head -1)" >> "$LOG"
