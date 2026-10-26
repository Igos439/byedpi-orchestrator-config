FROM registry-1.docker.io/vindibona/byedpi-orchestrator:latest

# --- Ядро DPI: byedpi (ciadpi) 17.3, версия и контрольная сумма зафиксированы ---
ARG CIADPI_URL=https://github.com/hufrea/byedpi/releases/download/v0.17.3/byedpi-17.3-x86_64.tar.gz
ADD --checksum=sha256:98f73c32eacb571ebd88d790f6376ed9e70f02d44c1fe862472ecea75cd7117d \
    ${CIADPI_URL} /tmp/byedpi.tar.gz
RUN tar xzf /tmp/byedpi.tar.gz -C /tmp \
 && install -m 0755 /tmp/ciadpi-x86_64 /usr/local/bin/ciadpi \
 && rm -f /tmp/byedpi.tar.gz /tmp/ciadpi-x86_64 \
 && /usr/local/bin/ciadpi --version

# --- Статистика коллектора пишется на постоянный том /app/state ---
# (в апстрим-образе ./state, то есть слой контейнера: генератор статистику не видел)
COPY overlay/config/stats.json /opt/orchestrator/config/stats.json

# --- Снимок оверлея: источник для восстановления /usb1/orchestrator-data (= /app) ---
# Патчи применяются на старте контейнера из /app, а не на этапе сборки, чтобы
# не получить полу-пропатченный образ при сбое одного из скриптов.
COPY overlay/ /opt/hermes-overlay/
RUN chmod 0755 /opt/hermes-overlay/entry_local.sh \
              /opt/hermes-overlay/dpi-core/install_core.sh 2>/dev/null || true

LABEL org.opencontainers.image.title="byedpi-orchestrator (patched)" \
      org.opencontainers.image.description="byedpi-orchestrator + ciadpi 17.3 + статистика на постоянном томе" \
      org.opencontainers.image.source="https://github.com/Igos439/byedpi-orchestrator-config"
