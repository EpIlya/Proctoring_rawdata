#!/usr/bin/env python3
"""
analyze_cheating_directions.py
==============================
Анализ направлений взгляда и головы при списывании.

Считаются только наблюдения, попавшие в окно [mark_ts, mark_ts + 10 сек]
после каждой ручной отметки (manual_cheating_mark).

Поддерживаемые форматы
-----------------------
v1  — behavior_log.json      (gaze_history = список строк, timestamp вида "2025-05-21 184232")
v2  — behavior_log-2.json    (gaze_history = список объектов {direction, timestamp, ...},
                               timestamp наблюдения — строка, отдельные timestamps внутри
                               каждой записи gaze_history — unix float)
v3  — behavior_log-Urezannyi-3.json  (конкатенированные JSON-объекты, те же поля что v2,
                               плюс head_history = список объектов {direction, ...})

Запуск
------
  python analyze_cheating_directions.py
      -- ищет три файла в текущей директории с именами по умолчанию

  python analyze_cheating_directions.py file1.json v1 file2.json v2 file3.json v3
      -- явное указание файлов и версий форматов
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════
# Настройки
# ═══════════════════════════════════════════════
CHEATING_WINDOW_SEC = 10.0          # секунд после отметки

DIRECTION_COLS = [
    "Влево", "Вправо", "Вниз", "Вверх",
    "Влево-вниз", "Влево-вверх", "Вправо-вниз", "Вправо-вверх",
    "Центр", "Моргает",
]

DIR_MAP = {
    "left":       "Влево",
    "right":      "Вправо",
    "down":       "Вниз",
    "up":         "Вверх",
    "left down":  "Влево-вниз",
    "left up":    "Влево-вверх",
    "right down": "Вправо-вниз",
    "right up":   "Вправо-вверх",
    "center":     "Центр",
    "blink":      "Моргает",
    # вариации со знаком подчёркивания
    "left_down":  "Влево-вниз",
    "left_up":    "Влево-вверх",
    "right_down": "Вправо-вниз",
    "right_up":   "Вправо-вверх",
}

def normalize_dir(s) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    return DIR_MAP.get(s, s)   # если неизвестно — оставить как есть


# ═══════════════════════════════════════════════
# Парсеры временны́х меток
# ═══════════════════════════════════════════════

def parse_ts_str(ts: str) -> Optional[float]:
    """Разбирает строковый timestamp вида '2025-05-21 184232' -> unix float."""
    ts = str(ts).strip()
    # Формат без двоеточий: "YYYY-MM-DD HHMMSS"
    for fmt in ("%Y-%m-%d %H%M%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt).timestamp()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        pass
    return None

def to_float_ts(v) -> Optional[float]:
    """Конвертирует произвольное значение timestamp в unix float."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return parse_ts_str(str(v))


# ═══════════════════════════════════════════════
# Загрузчики форматов
# ═══════════════════════════════════════════════

def _gaze_dirs_from_list(gaze_raw) -> list[str]:
    """Извлекает список direction из gaze_history (поддерживает строки и объекты)."""
    dirs = []
    if not gaze_raw:
        return dirs
    for g in gaze_raw:
        if isinstance(g, dict):
            dirs.append(normalize_dir(g.get("direction")))
        elif isinstance(g, str):
            dirs.append(normalize_dir(g))
    return [d for d in dirs if d]

def _head_dirs_from_list(head_raw) -> list[str]:
    """Извлекает список direction из head_history."""
    dirs = []
    if not head_raw:
        return dirs
    for h in head_raw:
        if isinstance(h, dict):
            dirs.append(normalize_dir(h.get("direction")))
        elif isinstance(h, str):
            dirs.append(normalize_dir(h))
    return [d for d in dirs if d]


def _classify_event(rec: dict) -> dict:
    """
    Универсальная классификация одной записи.
    Возвращает dict с ключами:
      event_type  — 'manual_cheating_mark' | 'observation' | 'other'
      ts          — unix float или None
      gaze_dirs   — list[str]
      head_dirs   — list[str]
      gaze_ts     — list[float]   (unix timestamps отдельных измерений, для v2/v3)
    """
    ts_raw = rec.get("timestamp")
    ts = to_float_ts(ts_raw)

    data = rec.get("data") or {}

    # Определяем тип события
    et = (data.get("event_type") or data.get("eventtype") or "").lower().replace("_", "")
    is_mark = et in ("manualcheatingmark",)

    if is_mark:
        return {"event_type": "manual_cheating_mark", "ts": ts,
                "gaze_dirs": [], "head_dirs": [], "gaze_ts": []}

    gaze_raw = data.get("gaze_history") or data.get("gazehistory") or []
    head_raw = data.get("head_history") or data.get("headhistory") or []

    # Для v2/v3: извлекаем timestamp каждого измерения взгляда
    gaze_ts = []
    for g in gaze_raw:
        if isinstance(g, dict):
            t = to_float_ts(g.get("timestamp"))
            if t:
                gaze_ts.append(t)

    gaze_dirs = _gaze_dirs_from_list(gaze_raw)
    head_dirs = _head_dirs_from_list(head_raw)

    if gaze_dirs or head_dirs:
        return {"event_type": "observation", "ts": ts,
                "gaze_dirs": gaze_dirs, "head_dirs": head_dirs, "gaze_ts": gaze_ts}

    return {"event_type": "other", "ts": ts,
            "gaze_dirs": [], "head_dirs": [], "gaze_ts": []}


def load_v1(path: str) -> list[dict]:
    """behavior_log.json v1 — массив объектов, gaze_history — список строк."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [_classify_event(rec) for rec in data]


def load_v2(path: str) -> list[dict]:
    """behavior_log-2.json v2 — массив объектов, gaze_history — список объектов."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [_classify_event(rec) for rec in data]


def load_v3(path: str) -> list[dict]:
    """
    behavior_log-Urezannyi-3.json v3 — конкатенированные JSON-объекты.
    Не массив — поэтому читаем через raw_decode.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    decoder = json.JSONDecoder()
    events = []
    pos = 0
    while True:
        raw_slice = raw[pos:].lstrip()
        if not raw_slice:
            break
        try:
            obj, consumed = decoder.raw_decode(raw_slice)
            # Если верхний уровень — массив объектов, разворачиваем его
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        events.append(_classify_event(item))
            elif isinstance(obj, dict):
                events.append(_classify_event(obj))
            # иначе пропускаем скаляры и прочее
            pos += len(raw[pos:]) - len(raw_slice) + consumed
        except json.JSONDecodeError:
            pos += 1   # пропускаем один символ и пробуем дальше
    return events


# ═══════════════════════════════════════════════
# Подсчёт направлений в окнах списывания
# ═══════════════════════════════════════════════

def collect_cheating_dirs(events: list[dict]) -> tuple[dict, dict]:
    """
    Для каждого manual_cheating_mark берём наблюдения, timestamp
    которых попадает в [mark_ts, mark_ts + CHEATING_WINDOW_SEC].

    Если у наблюдения есть gaze_ts (v2/v3) — применяем окно к каждому
    отдельному измерению, а не ко всей записи.

    Возвращает (gaze_counts, head_counts): dict направление -> кол-во.
    """
    mark_times = [
        e["ts"] for e in events
        if e["event_type"] == "manual_cheating_mark" and e["ts"] is not None
    ]

    gaze_counts: dict[str, int] = defaultdict(int)
    head_counts: dict[str, int] = defaultdict(int)

    def in_any_window(t: float) -> bool:
        return any(mt <= t <= mt + CHEATING_WINDOW_SEC for mt in mark_times)

    for e in events:
        if e["event_type"] != "observation":
            continue

        gaze_dirs = e.get("gaze_dirs", [])
        head_dirs = e.get("head_dirs", [])
        gaze_ts   = e.get("gaze_ts", [])
        rec_ts    = e.get("ts")

        # ── Взгляд ──────────────────────────────────────────
        if gaze_ts and len(gaze_ts) == len(gaze_dirs):
            # Для v2/v3: фильтруем по timestamp каждого измерения
            for t, d in zip(gaze_ts, gaze_dirs):
                if d and in_any_window(t):
                    gaze_counts[d] += 1
        elif gaze_ts and gaze_dirs:
            # timestamps есть, но числа не совпадают — берём первый ts записи
            first_ts = gaze_ts[0] if gaze_ts else rec_ts
            if first_ts and in_any_window(first_ts):
                for d in gaze_dirs:
                    if d:
                        gaze_counts[d] += 1
        elif rec_ts and in_any_window(rec_ts):
            # v1: нет индивидуальных timestamps — используем timestamp записи
            for d in gaze_dirs:
                if d:
                    gaze_counts[d] += 1

        # ── Голова ──────────────────────────────────────────
        # head_history в v3 не имеет отдельных timestamps внутри,
        # используем timestamp записи
        if head_dirs and rec_ts and in_any_window(rec_ts):
            for d in head_dirs:
                if d:
                    head_counts[d] += 1

    return dict(gaze_counts), dict(head_counts)


# ═══════════════════════════════════════════════
# Форматирование таблицы
# ═══════════════════════════════════════════════

def make_row(num: int, label: str, counts: dict) -> tuple:
    def c(k):
        return counts.get(k, 0)
    return (
        num, label,
        c("Влево"), c("Вправо"), c("Вниз"), c("Вверх"),
        c("Влево-вниз"), c("Влево-вверх"), c("Вправо-вниз"), c("Вправо-вверх"),
        c("Центр"), c("Моргает"),
    )


def print_table(rows: list[tuple]):
    headers = ["№", "Признак"] + DIRECTION_COLS
    col_w = [max(len(str(r[i])) for r in ([tuple(headers)] + rows)) for i in range(len(headers))]

    sep = "+" + "+".join("-" * (w + 2) for w in col_w) + "+"
    def fmt(row):
        cells = " | ".join(str(row[i]).center(col_w[i]) for i in range(len(headers)))
        return f"| {cells} |"

    print(sep)
    print(fmt(headers))
    print(sep)
    for row in rows:
        print(fmt(row))
        print(sep)


# ═══════════════════════════════════════════════
# Главная функция
# ═══════════════════════════════════════════════

def analyze(files: list[tuple[str, str]]) -> list[tuple]:
    loaders = {"v1": load_v1, "v2": load_v2, "v3": load_v3}
    all_rows = []
    row_num = 1

    for file_path, version in files:
        if not Path(file_path).exists():
            print(f"[!] Файл не найден: {file_path}")
            continue

        loader = loaders.get(version)
        if loader is None:
            print(f"[!] Неизвестная версия формата: {version}. Доступны: v1, v2, v3")
            continue

        print(f"\nЗагрузка: {file_path}  (формат {version})")
        events = loader(file_path)

        marks = [e for e in events if e["event_type"] == "manual_cheating_mark"]
        obs   = [e for e in events if e["event_type"] == "observation"]
        print(f"  Записей всего:                    {len(events)}")
        print(f"  Ручных отметок (manual_cheating_mark): {len(marks)}")
        print(f"  Наблюдений (observation):         {len(obs)}")

        gaze_counts, head_counts = collect_cheating_dirs(events)

        fname = Path(file_path).name

        # Строка взгляда — всегда
        all_rows.append(make_row(row_num, f"Взгляд ({fname})", gaze_counts))
        row_num += 1

        # Строка головы — только если данные есть (файл v3)
        if head_counts:
            all_rows.append(make_row(row_num, f"Голова ({fname})", head_counts))
            row_num += 1

        # Подробный вывод счётчиков
        total_g = sum(gaze_counts.values())
        total_h = sum(head_counts.values())
        print(f"  Направления взгляда в окнах: {total_g} измерений")
        for col in DIRECTION_COLS:
            n = gaze_counts.get(col, 0)
            if n:
                print(f"    {col}: {n}")
        if head_counts:
            print(f"  Направления головы в окнах:  {total_h} измерений")
            for col in DIRECTION_COLS:
                n = head_counts.get(col, 0)
                if n:
                    print(f"    {col}: {n}")

    return all_rows


def main():
    args = sys.argv[1:]
    if args:
        if len(args) % 2 != 0:
            sys.exit(1)
        files = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    else:
        files = [
            ("../1/behavior_log.json", "v1"),
            ("../2/behavior_log.json", "v2"),
            ("../3/behavior_log.json", "v3"),
            ("../4/behavior_log.json", "v3"),
        ]

    print("=" * 70)
    print("АНАЛИЗ НАПРАВЛЕНИЙ ПРИ СПИСЫВАНИИ")
    print(f"Окно: {CHEATING_WINDOW_SEC} секунд после ручной отметки")
    print("=" * 70)

    rows = analyze(files)

    print("\n" + "=" * 70)
    print("ИТОГОВАЯ ТАБЛИЦА")
    print("=" * 70)
    print_table(rows)


if __name__ == "__main__":
    main()
