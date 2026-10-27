#!/bin/sh
# Обёртка запуска контейнера orchestrator: повторно применяет наши патчи к файлу
# приложения после обновления образа, затем запускает штатный entrypoint.
# Файл лежит в примонтированном каталоге /usb1/orchestrator-data (= /app) и
# переживает смену образа контейнера.

APP=/app
TARGET=/opt/orchestrator/orchestrator_with_canary.py
LOG="$APP/state/entry_local.log"
MARK="_link_expire"

mkdir -p "$APP/state" 2>/dev/null
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG" 2>/dev/null; }

log "старт обёртки, цель: $TARGET"

# hermes:dpi-core — при старте контейнера ставим ядро ciadpi из /app/dpi-core
sh /app/dpi-core/install_core.sh >> "$APP/state/entry_local.log" 2>&1 || true

# hermes:stats-paths — держим статистику на постоянном томе /app/state
python3 /app/patch_stats_paths.py --quiet >> "$APP/state/entry_local.log" 2>&1 || true

if [ ! -f "$TARGET" ]; then
    log "файл приложения не найден — патчи пропущены"
    exec /usr/local/bin/entry_orchestrator.sh
fi

if grep -q "$MARK" "$TARGET" 2>/dev/null; then
    log "патчи уже на месте — применение не нужно"
    exec /usr/local/bin/entry_orchestrator.sh
fi

cp -f "$TARGET" "$TARGET.bak-entry" 2>/dev/null

# Патчи применяем по очереди и не прерываемся на ошибке: часть скриптов
# идемпотентна и сама сообщает "already patched" ненулевым кодом.
for p in "$APP/patch_orch.py" "$APP/patch_cache.py" "$APP"/patch_v2.py "$APP"/patch_v3.py \
         "$APP"/patch_v4.py "$APP"/patch_v5.py "$APP"/patch_v6.py "$APP"/patch_v7.py \
         "$APP"/patch_v8.py "$APP"/patch_v9.py "$APP"/patch_media_probe.py; do
    [ -f "$p" ] || continue
    if python3 "$p" "$TARGET" >>"$LOG" 2>&1; then
        log "применён $(basename "$p")"
    else
        log "предупреждение: $(basename "$p") завершился с ошибкой (продолжаем)"
    fi
done

# Итоговая проверка: маркер патча на месте и файл компилируется.
if grep -q "$MARK" "$TARGET" 2>/dev/null && python3 -m py_compile "$TARGET" 2>>"$LOG"; then
    log "патчи применены, синтаксис в порядке"
else
    if [ -f "$TARGET.bak-entry" ]; then
        cp -f "$TARGET.bak-entry" "$TARGET"
        log "ОТКАТ: файл приложения восстановлен из бэкапа"
    fi
fi

exec /usr/local/bin/entry_orchestrator.sh
