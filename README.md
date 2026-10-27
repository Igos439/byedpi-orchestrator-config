# byedpi-orchestrator-config

Оверлей и сборка для контейнера `orchestrator` (образ `vindibona/byedpi-orchestrator`) на MikroTik CHR. Здесь лежат все локальные правки, которые раньше жили только на USB-накопителе роутера: обёртка запуска, патчи приложения, конфиг сбора статистики, установщик ядра DPI.

## Состав

```
Dockerfile                     сборка образа: базовый образ + ciadpi 17.3 + наш конфиг статистики
.github/workflows/build.yml    сборка и публикация в ghcr.io при пуше в main
overlay/
  entry_local.sh               обёртка запуска (= /app/entry_local.sh на роутере)
  config/stats.json            конфиг коллектора статистики (пути на /app/state)
  config/strategy_space.json   статический набор стратегий
  patches/                     патчи приложения: patch_orch, patch_cache, patch_v2..v9, patch_step3, fix_*
  tools/                       утилиты: check_cache, ensure_deps, reset_orch_state, reset_thresholds, patch_stats_paths
  dpi-core/                    установка ядра ciadpi (install_core.sh, patch_entry_dpi.py) + архив byedpi-17.3
```

## Как это работает на роутере

- Каталог `/usb1/orchestrator-data` на CHR смонтирован в контейнер как `/app`. Он переживает обновление образа, поэтому обёртка и патчи лежат именно там.
- Команда запуска контейнера: `/bin/sh /app/entry_local.sh`.
- Обёртка при каждом старте:
  1. ставит ядро `ciadpi` из `/app/dpi-core`, если версия отличается (`install_core.sh`, подмена атомарная через `mv`);
  2. применяет `patch_stats_paths.py` — держит статистику коллектора на постоянном томе `/app/state`;
  3. если в `orchestrator_with_canary.py` нет маркера `_link_expire`, применяет `patch_orch` → `patch_v2…v9` и проверяет синтаксис; при сбое откатывается из `.bak-entry`;
  4. запускает штатный `/usr/local/bin/entry_orchestrator.sh`.
- Секреты (`TG_TOKEN`, `TG_CHAT_ID`, `CANARY_PROXY`) задаются env-листом `byedpi-env` в RouterOS и в репозиторий не попадают.

## Важные пути внутри контейнера

| Что | Где | Живёт |
|---|---|---|
| обёртка, патчи, состояние | `/app` (= `/usb1/orchestrator-data`) | постоянно |
| приложение и его бэкапы | `/opt/orchestrator` | слой контейнера |
| ядро DPI | `/usr/local/bin/ciadpi` | слой контейнера (ставится из `/app/dpi-core`) |
| статистика, динамический набор | `/app/state/arg_stats.json`, `/app/state/strategy_space.dynamic.json` | постоянно |
| логи оркестратора | `/app/state/orch_verbose.log` | постоянно |

## Обновление образа

1. Пуш в `main` → GitHub Actions собирает `ghcr.io/igos439/byedpi-orchestrator:latest` (тег `sha-<commit>` тоже).
2. На CHR в контейнере `orchestrator`: `remote-image=ghcr.io/igos439/byedpi-orchestrator:latest`.
3. Пакет **публичный**, поэтому на роутере авторизация не нужна — образ тянется анонимно. Если видимость когда-нибудь закроют, понадобится токен с правом `read:packages` и настройка `registry-url` в контейнере.
4. Пересоздание контейнера: остановить, обновить образ, стартовать. `/app` и состояние сохраняются.

## Восстановление на новом роутере

```sh
# на роутере: /usb1/orchestrator-data = содержимое overlay/
# 1. скопировать overlay/* в /usb1/orchestrator-data (кроме config/ и dpi-core/ — их разложить по местам)
# 2. конфиг статистики: overlay/config/stats.json -> /opt/orchestrator/config/stats.json (или дать patch_stats_paths.py переписать)
# 3. ядро: архив byedpi-17.3 распаковать в /usb1/orchestrator-data/dpi-core/ciadpi-x86_64
# 4. создать контейнер: image=ghcr.io/igos439/byedpi-orchestrator:latest, cmd=/bin/sh /app/entry_local.sh,
#    mountlists=orchestrator-mount, envlists=byedpi-env, dns=10.0.10.1, start-on-boot=yes
```

## Откат

- Ядро: `/app/dpi-core/ciadpi-17.2.backup` → скопировать в `/usr/local/bin/ciadpi`.
- Патчи: `/opt/orchestrator/orchestrator_with_canary.py.bak-entry` или бэкапы `.bak-hermes-*`.
- Конфиг статистики: `stats.json.bak-hermes-*`.
- Образ: тег `sha-<commit>` предыдущей сборки.

## Что в репозиторий не попадает

`/app/state` целиком (статистика, логи, чекпоинты, бэкапы состояния), секреты, а также 100-килобайтные дампы `orch_src.py` / `orch_patched.py` и одноразовые `diag_*`/`inspect_*` скрипты.

## Текущее состояние (26.10.2026)

- контейнер `orchestrator` на CHR работает с образа **`ghcr.io/igos439/byedpi-orchestrator:latest`** (переключён с апстрима, авторизация не нужна — пакет публичный);
- ядро DPI: **ciadpi 17.3** (было 17.2 из образа от 13.12.2025);
- статистика коллектора пишется в `/app/state/arg_stats.json`, генератор динамического набора её видит, оркестратор работает по `strategy_space.dynamic.json`;
- патчи применяются обёрткой `/app/entry_local.sh` при старте (в журнале: `patch_v8.py`, `patch_v9.py`,
  `patch_media_probe.py`, `патчи применены, синтаксис в порядке`);
- `patch_media_probe.py` (27.10): `save_last_results()` пишет `last_results.json` даже при отказе кандидата
  (раньше `return` в блоке accept пропускал `save_state`), порог серии по умолчанию 1 вместо 2 —
  иначе победитель меняется каждый проход и streak никогда не доходил до 2; неудачные медиа-пробы
  логируются строкой `probe FAIL` с кодом, байтами и скоростью;
- порог медиа-пробы приведён к реальности: `rr_min_throughput_kbps` 700 → **300**, выборка
  `rr_range_bytes` 512 КиБ → **1 МиБ** (на 512 КиБ замер тонул в TLS-хендшейке и давал 300–560 КБ/с,
  из-за чего все кандидаты отбивались с `media_avail<0.40`);
- кэш медиа обновляется кроном Hermes каждые 30 минут (`yt_cache_sync.py`, `MAX_AGE=1200`);
- на 27.10 приём проходит (`ok=True score≈0.888 avail=1.00`), но кандидаты валят медиа-пробы
  с `SSL: UNEXPECTED_EOF` — генератор выдаёт комбинации, рвущие TLS к googlevideo; это следующий шаг.
