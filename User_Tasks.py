import json

from Mongo_Access import DB_Client

from Tasks import GoogleTasksClient
from User import User
from typing import Any
import os
from dotenv import dotenv_values

config = dotenv_values(".env")


def load_local_db(user_id : str,client : DB_Client,nosync=False) -> dict[str, Any] | None:
    """Load local database and return local db dict"""
    if not nosync:
        db_selected = 'tasks'
    else:
        db_selected = 'tasks_ns'

    try:
        client_inst = client
        client = client_inst.clt
        col = client['TBot_DB'][db_selected]
        usr = col.find_one({"user.user_id" : user_id})
        del client_inst
        if usr is not None:
            del usr['_id']
            return usr
        return None
    except Exception as e:
        return None


def save_local_db(user_id : str ,db, client : DB_Client,nosync=False) -> bool | None:
    """Save changed local db"""
    if not nosync:
        db_selected = 'tasks'
    else:
        db_selected = 'tasks_ns'

    try:
        client_inst = client
        client = client_inst.clt
        col = client['TBot_DB'][db_selected]
        data = db
        data["user"]["user_id"] = user_id
        result = col.update_one(
            {"user.user_id": user_id},  # Filter: documents that have uid field
            {"$set": data},
            upsert=True # Create if it does not exist
        )
        if result is not None:
            return True
        return False
    except Exception as e:
        raise e
        return None


def sync_tasks_c2l(userid: str,client : DB_Client) -> None:
    """Sync cloud changes to MongoDB"""
    t_user = User(userid,client)
    if t_user.user_exists():
        l_db = load_local_db(userid,client)
        l_db_ns = load_local_db(userid,client,nosync=True)
        u_set = True
        if l_db is None:
            l_db = {}
        if l_db_ns is None:
            l_db_ns = {}
            u_set = False
            l_db_ns['user'] = {}
            l_db_ns['user']["categories"] = []

        t_client = GoogleTasksClient(userid,client)
        tasklists = []
        tasks = []
        tasks_ns = []
        task_lists = t_client.get_task_lists()
        id_lst = []
        for task_list in task_lists:
            tasklists.append(task_list)
            res = t_client.get_tasks(task_list['id'])['items']
            for item in res:
                id_lst.append(item['id'])
                tasks.append(item)
        if not u_set:
            for st in tasks:
                tasks_ns.append({"id": st["id"], "title": st["title"], "status": st["status"], "priority": "not_set",
                                 "category": "not_set"})
            l_db_ns["user"]["tasks"] = tasks_ns
            save_local_db(userid,l_db_ns,client,nosync=True)
        else:
            t_list = l_db_ns['user']['tasks']
            t_list = [task for task in t_list if task['id'] in id_lst]
            l_db_ns['user']['tasks'] = t_list
            for task in t_list:
                t_sel = list(filter(lambda t: t['id'] == task['id'], tasks))[0]
                task['status'] = t_sel['status']
                task['title'] = t_sel['title']
            l_db_ns['user']['tasks'] = t_list
            save_local_db(userid,l_db_ns,client,nosync=True)

        l_db['user'] = {}
        l_db['user']['tasklists'] = tasklists
        l_db['user']['tasks'] = tasks
        save_local_db(userid,l_db,client)

    else:
        raise Exception(f"User {userid} does not exist")


def create_task_synced(userid: str, task: dict[str, Any], task_list_id: str,db_client) -> None:
    """Create a task and sync immediately to local db"""
    t_user = User(userid,db_client)
    if t_user.user_exists():
        client = GoogleTasksClient(userid,db_client)
        client.create_task(task_list_id=task_list_id, title=task["title"], notes=task["notes"], due=task["due"])
        sync_tasks_c2l(userid,db_client)
    else:
        raise Exception(f"User {userid} does not exist")


if __name__ == '__main__':
    client = DB_Client()
    #585767830247571476
    sync_tasks_c2l("585767830247571476",client)
    pass
