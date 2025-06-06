from typing import Tuple
from datetime import datetime, date, timedelta
from pytz import timezone as tz


def str_to_task(validated_input: str) -> Tuple[str, str | None, str]:
    """Convert string to task for creation"""
    tokenized = validated_input.split()
    index = 0
    d_index = 0
    d_obj = None
    d_toks = 0
    for token in tokenized:
        try:
            datetime.strptime(token, "%Y-%m-%d")
            d_toks += 1
            d_index = index
        except ValueError:
            pass
        index += 1

    task_name = tokenized[0:d_index]
    task_name = " ".join(task_name)

    task_due = tokenized[d_index] + 'T00:00:00.000Z'
    if len(tokenized) - 1 > d_index:
        notes = "".join(tokenized[d_index + 1:])
    else:
        notes = None

    return task_name, notes, task_due


def status_converter(status: str) -> str:
    """Miniature task status converter"""
    if status == "completed":
        return "✓"
    else:
        return "X"


def iso_localizer(dt: str, time_zone: str) -> datetime:
    """Convert ISO format str to UTC datetime"""
    dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")  # Convert to naive datetime object ( ie without tzinfo )
    dt = tz(time_zone).localize(dt)  # Localize naive object with user timezone
    out = dt.astimezone(tz('UTC'))  # Finally convert timezone aware datetime object to utc
    return out
