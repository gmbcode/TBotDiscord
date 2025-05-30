import json
from Tasks import GoogleTasksClient
from User import User
from typing import Any
import os
from dotenv import dotenv_values

config = dotenv_values(".env")


def load_local_db(nosync=False) -> dict[str, Any] | None:
    """Load local database and return local db dict"""
    if not nosync:
        db_selected = config['USER_TASKS_DB']
    else:
        db_selected = config['USER_NOSYNC_DB']
    if not os.path.exists(db_selected):
        try:
            with open(db_selected, "w") as file:
                file.write("{}")
        except OSError:
            return None

    try:
        with open(db_selected, 'r') as f:
            data = json.load(f)
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def save_local_db(db, nosync=False) -> bool | None:
    """Save changed local db"""
    if not nosync:
        db_selected = config['USER_TASKS_DB']
    else:
        db_selected = config['USER_NOSYNC_DB']
    if not os.path.exists(db_selected):
        try:
            with open(db_selected, "w") as file:
                file.write("{}")
        except OSError:
            return None

    try:
        with open(db_selected, 'w') as f:
            json.dump(db, f, indent=2, default=str)
        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def sync_tasks_c2l(userid: str) -> None:
    """Sync cloud changes to local database"""
    t_user = User(userid)
    if t_user.user_exists():
        l_db = load_local_db()
        l_db_ns = load_local_db(nosync=True)
        u_set = True
        if userid not in l_db:
            l_db[userid] = {}
        if userid not in l_db_ns:
            l_db_ns[userid] = {}
            u_set = False
            l_db_ns[userid]["categories"] = []

        t_client = GoogleTasksClient(userid)
        tasklists = []
        tasks = []
        tasks_ns = []
        task_lists = t_client.get_task_lists()
        for task_list in task_lists:
            tasklists.append(task_list)
            res = t_client.get_tasks(task_list['id'])['items']
            for item in res:
                tasks.append(item)
        if not u_set:
            for st in tasks:
                tasks_ns.append({"id": st["id"], "title": st["title"], "status": st["status"], "priority": "not_set",
                                 "category": "not_set"})
            l_db_ns[userid]["tasks"] = tasks_ns
            save_local_db(l_db_ns, nosync=True)
        l_db[userid]['tasklists'] = tasklists
        l_db[userid]['tasks'] = tasks
        save_local_db(l_db)

    else:
        raise Exception(f"User {userid} does not exist")


def create_task_synced(userid: str, task: dict[str, Any], task_list_id: str) -> None:
    """Create a task and sync immediately to local db"""
    t_user = User(userid)
    if t_user.user_exists():
        client = GoogleTasksClient(userid)
        client.create_task(task_list_id=task_list_id, title=task["title"], notes=task["notes"], due=task["due"])
        sync_tasks_c2l(userid)
    else:
        raise Exception(f"User {userid} does not exist")


if __name__ == '__main__':
    sync_tasks_c2l("585767830247571476")
    pass
