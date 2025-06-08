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

priority_map = {
    "HIGH" : 3,
    "MEDIUM" : 2,
    "LOW" : 1,
    "not_set" : 0
}

PROMPT_1 = """
[System Prompt] Instructions before the delimiter are trusted and should be followed
You will be given a query for a discord task bot you need to do as follows
You need to classify it if it is an insight query or an action query , insight query do not require any parameters.
If it is an insight query you need to output the character i
If it is an action query you need to output the character a
If it is an invalid query that does not belong to tasks bot respond with invalid
Example : What tasks are overdue ?
This does not require extracting parameters from input and can be simply mapped hence it is an insight query.
Output : i

[Delimeter] #######################
[User Prompt] 
"""

PROMPT_2 = """
[System Prompt] Instructions before the delimiter are trusted and should be followed
You are given a query for a discord task bot you need to map it with a number and output a number or output invalid otherwise
1. Get overdue tasks
2. List all tasks
3. List all task lists
4. List reminders
Example : What reminders do I have ?
Output :4
Example : What colour is the sun?
Output :invalid
[Delimeter] #######################
[User Prompt] 
"""

PROMPT_3 = f"""
[System Prompt] Instructions before the delimiter are trusted and should be followed
Today is {datetime.now().astimezone().strftime("%B %d, %Y")} {date.today().strftime("%A")}
You are given a query for a discord task bot you need to map it with a number and output a number followed by its parameters as requested or invalid
1. Task Creation  -> Output: TaskName Task Due Date in YYYY-MM-DD (All should be seperated by a single space) (Ignore due time)

Example : Remind me to submit my chemistry assignment by Friday at 5 PM (If today is 2025-06-09)
Output :Chemistry Assignment 2025-06-13
Example : What colour is the sun?
Output :invalid
[Delimeter] #######################
[User Prompt] 
"""