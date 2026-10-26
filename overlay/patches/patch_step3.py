"""Шаг 3: генератор кандидатов от «чемпиона» вместо случайных цепочек с нуля.

Что было: generate_candidates_from_space() строил каждую стратегию случайной цепочкой
из 4–12 операций. В нынешних условиях TSPU такие урезанные наборы режутся reset'ом
на youtubei, поэтому медиа-проверка падала и приёмка не проходила 2 дня.

Что стало: базой берётся текущий рабочий набор из /app/state/best_strategies.json
(проверен вручную 5/5 на googlevideo) и из него делаются мутанты:
  - сам чемпион;
  - минус одна случайная операция (и её значение);
  - минус две-три операции;
  - плюс одна новая операция из пространства флагов;
  - одна числовая позиция сдвинута на ±1..3.
Плюс 25% кандидатов остаются полностью случайными — чтобы не застрять в локальном
оптимуме, если TSPU снова изменит поведение.

Скрипт делает бэкап, патчит, проверяет компиляцию и откатывается при ошибке.
"""
import json
import os
import shutil
import sys
import time

TARGET = "/opt/orchestrator/orchestrator_with_canary.py"
BACKUP = f"{TARGET}.bak-step3-{time.strftime('%Y%m%dT%H%M%S')}"
CHAMPION_FILE = "/app/state/best_strategies.json"

NEW_CODE = '''

# --- шаг 3 (Hermes): генерация кандидатов мутациями от проверенного «чемпиона» ---

CHAMPION_CACHE = {"path": None, "mtime": 0.0, "units": None}


def _parse_units(tokens: List[str]) -> List[List[str]]:
\t"""Разбирает плоский список аргументов на единицы: флаг + его значение (если есть)."""
\tunits: List[List[str]] = []
\ti = 0
\twhile i < len(tokens):
\t\ttok = tokens[i]
\t\tif tok.startswith("--"):
\t\t\tif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
\t\t\t\tunits.append([tok, tokens[i + 1]])
\t\t\t\ti += 2
\t\t\telse:
\t\t\t\tunits.append([tok])
\t\t\t\ti += 1
\t\telse:
\t\t\ti += 1
\treturn units


def _flatten_units(units: List[List[str]]) -> List[str]:
\tout: List[str] = []
\tfor u in units:
\t\tout.extend(u)
\treturn out


def _load_champion_units() -> List[List[str]]:
\t"""Читает рабочий набор из best_strategies.json, кешируя по mtime."""
\ttry:
\t\tst = os.stat(CHAMPION_FILE)
\texcept Exception:
\t\treturn []
\tif CHAMPION_CACHE["units"] is not None and CHAMPION_CACHE["mtime"] == st.st_mtime:
\t\treturn CHAMPION_CACHE["units"]
\ttry:
\t\tdata = json.load(open(CHAMPION_FILE))
\t\tbest = data.get("__global__") or []
\t\tif isinstance(best, str):
\t\t\tbest = best.split()
\t\tunits = _parse_units(list(best))
\texcept Exception as e:
\t\tprint(f"[orchestrator] champion load failed: {e}")
\t\treturn []
\tCHAMPION_CACHE.update({"path": CHAMPION_FILE, "mtime": st.st_mtime, "units": units})
\treturn units


def _random_unit_from_space(space: Dict[str, Any]) -> List[str] | None:
\tflags: Dict[str, List[Any]] = space.get("flags", {})
\tpool = []
\tfor name in ("disorder", "split", "oob", "disoob", "tlsrec"):
\t\tvals = [str(v) for v in flags.get(name, []) if v is not None]
\t\tfor v in vals:
\t\t\tpool.append([f"--{name}", v])
\tfor pair in (["--fake", "-1"], ["--md5sig"], ["--fake-sni", "m.vk.com"],
\t\t\t\t["--ttl", "10"], ["--auto=torst"], ["--auto=ssl_err"]):
\t\tpool.append(list(pair))
\treturn random.choice(pool) if pool else None


def generate_champion_mutants(space: Dict[str, Any], limit: int) -> List[List[str]]:
\tunits = _load_champion_units()
\tif not units:
\t\treturn []
\tout: List[List[str]] = []
\tseen: set[str] = set()

\tdef add(u: List[List[str]]) -> None:
\t\tif not u:
\t\t\treturn
\t\tkey = " ".join(_flatten_units(u))
\t\tif key in seen:
\t\t\treturn
\t\tseen.add(key)
\t\tout.append(_flatten_units(u))

\tadd([list(x) for x in units])  # сам чемпион
\tif len(units) > 3:
\t\tfor _ in range(max(6, limit // 6)):
\t\t\tk = random.choice([1, 1, 1, 2, 3])
\t\t\tidx = set(random.sample(range(len(units)), min(k, len(units) - 1)))
\t\t\tadd([list(x) for i, x in enumerate(units) if i not in idx])
\tfor _ in range(max(4, limit // 8)):
\t\tu = [list(x) for x in units]
\t\tnu = _random_unit_from_space(space)
\t\tif nu:
\t\t\tu.append(nu)
\t\tadd(u)
\tnumeric_idx = [i for i, x in enumerate(units) if len(x) == 2 and x[1][:1].isdigit()]
\tfor _ in range(max(4, limit // 8)):
\t\tif not numeric_idx:
\t\t\tbreak
\t\ti = random.choice(numeric_idx)
\t\tu = [list(x) for x in units]
\t\ttry:
\t\t\tnum = int("".join(ch for ch in u[i][1] if ch.isdigit()))
\t\t\tsuffix = u[i][1][len(str(num)):]
\t\t\tu[i][1] = f"{max(1, num + random.choice([-3, -2, -1, 1, 2, 3]))}{suffix}"
\t\texcept Exception:
\t\t\tcontinue
\t\tadd(u)
\treturn out[:limit]
'''

MARKER = "def generate_candidates_from_space(space: Dict[str, Any]) -> List[List[str]]:"

HOOK = '''\t# --- шаг 3 (Hermes): 75% кандидатов — мутации проверенного набора, 25% — случайные ---
\ttry:
\t\tchampion_mutants = generate_champion_mutants(space, max_candidates)
\texcept Exception as e:
\t\tprint(f"[orchestrator] champion mutants failed: {e}")
\t\tchampion_mutants = []
\tif champion_mutants:
\t\trandom_part = []
\t\ttarget_random = max(4, max_candidates // 4)
\t\tpre_for_random = space.get("pre_strategy", [])
\t\tattempts_r = 0
\t\twhile len(random_part) < target_random and attempts_r < target_random * 40:
\t\t\tattempts_r += 1
\t\t\tcli = generate_random_chain(space, bool(space.get("linux_profile", True)), pre_for_random)
\t\t\tkey = " ".join(cli)
\t\t\tif key and key not in (" ".join(s) for s in champion_mutants):
\t\t\t\trandom_part.append(cli)
\t\tcombined = champion_mutants + random_part
\t\tprint(f"[orchestrator] step3: кандидатов от чемпиона {len(champion_mutants)}, случайных {len(random_part)}")
\t\treturn combined
'''


def main():
    src = open(TARGET, encoding="utf-8").read()
    if "generate_champion_mutants" in src:
        print("уже пропатчено, выходим")
        return 0
    if MARKER not in src:
        print("не нашёл точку вставки — отказ")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"бэкап: {BACKUP}")

    # 1) добавляем функции мутатора перед generate_candidates_from_space
    patched = src.replace(MARKER, NEW_CODE.strip("\n") + "\n\n" + MARKER, 1)
    # 2) вставляем ранний возврат внутрь generate_candidates_from_space
    anchor = MARKER + "\n"
    idx = patched.index(anchor) + len(anchor)
    patched = patched[:idx] + HOOK + patched[idx:]

    open(TARGET, "w", encoding="utf-8").write(patched)
    try:
        compile(patched, TARGET, "exec")
        print("компиляция ок")
        print(f"строк было {len(src.splitlines())}, стало {len(patched.splitlines())}")
        return 0
    except SyntaxError as e:
        shutil.copy2(BACKUP, TARGET)
        print(f"ошибка компиляции, откат: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
