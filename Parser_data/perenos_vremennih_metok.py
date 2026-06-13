import json
import re
from pathlib import Path
from datetime import datetime


GAZE_LOG_FILE = "../../4/gaze_log.txt"
BEHAVIOR_LOG_FILE = "../../4/behavior_log_with_model.json"
OUTPUT_FILE = "../../4/behavior_log_with_model_updated.json"

MANUAL_MARK_TEXT = "Отмечена попытка списывания (по нажатию кнопки)"
MANUAL_EVENT_TYPE = "manual_cheating_mark"
MANUAL_EVENT_MESSAGE = "Пользователь отметил попытку списывания по нажатию кнопки"

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}):\s*(.+)$")


def parse_gaze_manual_marks(gaze_log_path: Path):
    manual_events = []

    with gaze_log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = LINE_RE.match(line)
            if not match:
                continue

            timestamp_str, message = match.groups()

            if message == MANUAL_MARK_TEXT:
                manual_events.append({
                    "timestamp": timestamp_str,
                    "data": {
                        "event_type": MANUAL_EVENT_TYPE,
                        "message": MANUAL_EVENT_MESSAGE
                    }
                })

    return manual_events


def merge_and_sort_events(behavior_events, manual_events):
    merged = behavior_events + manual_events
    merged.sort(
        key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S")
    )
    return merged


def main():
    gaze_log_path = Path(GAZE_LOG_FILE)
    behavior_log_path = Path(BEHAVIOR_LOG_FILE)
    output_path = Path(OUTPUT_FILE)

    if not gaze_log_path.exists():
        raise FileNotFoundError(f"Не найден файл: {gaze_log_path}")

    if not behavior_log_path.exists():
        raise FileNotFoundError(f"Не найден файл: {behavior_log_path}")

    manual_events = parse_gaze_manual_marks(gaze_log_path)

    with behavior_log_path.open("r", encoding="utf-8") as f:
        behavior_events = json.load(f)

    merged_events = merge_and_sort_events(behavior_events, manual_events)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(merged_events, f, ensure_ascii=False, indent=2)

    print("Готово.")
    print(f"Найдено ручных отметок в gaze_log.txt: {len(manual_events)}")
    print(f"Было событий в behavior_log_with_model.json: {len(behavior_events)}")
    print(f"Стало событий после объединения: {len(merged_events)}")
    print(f"Результат сохранён в: {output_path}")


if __name__ == "__main__":
    main()