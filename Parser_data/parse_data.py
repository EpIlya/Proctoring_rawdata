import json
from datetime import datetime, timedelta
from pathlib import Path


TIME_WINDOW_SECONDS = 10


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def load_events(file_path: str):
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    events = []
    for item in raw:
        ts = parse_timestamp(item["timestamp"])
        data = item.get("data", {})

        events.append({
            "timestamp": ts,
            "data": data,
            "event_type": data.get("event_type"),
            "message": data.get("message", ""),
            "current_status": data.get("current_status"),
            "cheating_trigger": data.get("cheating_trigger"),
        })

    events.sort(key=lambda x: x["timestamp"])
    return events


def is_manual_mark(event):
    return event["event_type"] == "manual_cheating_mark"


def is_system_mark(event):
    return event["current_status"] == "cheating"


def classify_marks(events, window_seconds=10):
    manual_marks = [e for e in events if is_manual_mark(e)]
    system_marks = [e for e in events if is_system_mark(e)]

    total_manual = len(manual_marks)
    total_system = len(system_marks)

    window = timedelta(seconds=window_seconds)

    real_manual = 0
    real_manual_details = []

    for m in manual_marks:
        start = m["timestamp"]
        end = start + window

        has_system_after = any(start <= s["timestamp"] <= end for s in system_marks)
        if has_system_after:
            real_manual += 1
            real_manual_details.append(m)

    false_system = 0
    false_system_details = []

    for s in system_marks:
        s_time = s["timestamp"]

        matched_manual = any(
            m["timestamp"] <= s_time <= m["timestamp"] + window
            for m in manual_marks
        )

        if not matched_manual:
            false_system += 1
            false_system_details.append(s)

    real_percent = (real_manual / total_manual * 100) if total_manual else 0.0
    false_percent = (false_system / total_system * 100) if total_system else 0.0

    return {
        "total_events": len(events),
        "total_manual_marks": total_manual,
        "total_system_marks": total_system,
        "real_manual_detected": real_manual,
        "not_detected_manual": total_manual - real_manual,
        "false_system_marks": false_system,
        "true_system_marks": total_system - false_system,
        "real_detection_percent": real_percent,
        "false_positive_percent": false_percent,
        "real_manual_details": real_manual_details,
        "false_system_details": false_system_details,
    }


def print_report(stats):
    print("=== СВОДКА ПО ЛОГАМ ===")
    print(f"Всего событий: {stats['total_events']}")
    print(f"Всего ручных отметок: {stats['total_manual_marks']}")
    print(f"Всего системных отметок: {stats['total_system_marks']}")
    print()
    print(f"Реально выявленных ручных попыток: {stats['real_manual_detected']}")
    print(f"Не подтвержденных системой ручных попыток: {stats['not_detected_manual']}")
    print(f"Истинных системных отметок: {stats['true_system_marks']}")
    print(f"Ложных системных срабатываний: {stats['false_system_marks']}")
    print()
    print(f"Процент реально выявленных попыток списать: {stats['real_detection_percent']:.2f}%")
    print(f"Процент ложных срабатываний системы: {stats['false_positive_percent']:.2f}%")

file_path = "../1/behavior_log.json"
events = load_events(file_path)
stats = classify_marks(events, window_seconds=TIME_WINDOW_SECONDS)
print_report(stats)

file_path = "../2/behavior_log.json"
events = load_events(file_path)
stats = classify_marks(events, window_seconds=TIME_WINDOW_SECONDS)
print_report(stats)

file_path = "../3/behavior_log.json"
events = load_events(file_path)
stats = classify_marks(events, window_seconds=TIME_WINDOW_SECONDS)
print_report(stats)

file_path = "../4/behavior_log.json"
events = load_events(file_path)
stats = classify_marks(events, window_seconds=TIME_WINDOW_SECONDS)
print_report(stats)

