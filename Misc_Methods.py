from typing import Tuple
from datetime import datetime,date,timedelta
def str_to_task(validated_input : str) -> Tuple[str, str | None,str]:
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
    if len(tokenized) - 1 > d_index :
        notes = "".join(tokenized[d_index+1:])
    else:
        notes = None

    return task_name,notes,task_due