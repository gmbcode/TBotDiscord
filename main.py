import asyncio
from typing import Tuple
import discord
import re
from discord.ext import commands
from dotenv import dotenv_values
from Auth_Server import generate_auth_url
from Test1 import response
from User import User as TskUser
from datetime import datetime, date, timedelta
from Tasks import GoogleTasksClient
from table2ascii import table2ascii
from User_Tasks import sync_tasks_g2m, load_mongo_db, save_to_db
from Misc_Methods import str_to_task, status_converter, iso_localizer,priority_map,PROMPT_1,PROMPT_2,PROMPT_3
from Mongo_Access import DB_Client
from google import genai
from copy import deepcopy
from pytz import common_timezones
from pytz import timezone as tz
from uuid import uuid4
config = dotenv_values(".env")
TOKEN_DISCORD = config["DISCORD_BOT_TOKEN"]
GEMINI_API_KEY = config["GEMINI_API_KEY"]
local_tz = config["LOCAL_TZ"]
format_str = "Task Name Due Date(YYYY-MM-DD) Notes(if any)\nExample : my task 2025-05-30 Some details about my task"
intents = discord.Intents.default()
intents.message_content = True
CLIENT = DB_Client()
bot = commands.Bot(command_prefix="#", intents=intents)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

async def selector(ctx : discord.ext.commands.Context , get_task_name : bool = False) -> Tuple[str,str] | Tuple[str,str,str] | None :
    """Selector function to return selected task id and parent tasklist id or None"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try:
                await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                       delete_after=10)
                try:
                    clt = GoogleTasksClient(user_id,CLIENT)
                    tl = clt.get_task_lists()
                except Exception as e:
                    await ctx.channel.send("Error fetching user tasks")
                    return None
                headings = ['No','Category','Task Name', 'Due Date', 'Tasklist', 'Status','Priority']
                resp = []
                resp_int = []
                sync_tasks_g2m(user_id, CLIENT)
                ns_db = load_mongo_db(user_id, CLIENT, nosync = True)

                u_db = ns_db["user"]
                index = 0
                id_list = []
                for task_list in tl:
                    tr = clt.get_tasks(task_list['id'])['items']

                    for task in tr:
                        if 'due' in task:
                            f_date = datetime.fromisoformat(task['due']).astimezone()
                            f_date = f_date.strftime("%B %d, %Y")
                        else:
                            f_date = 'Not Set / Passed'
                        current_task = list(filter(lambda t: t['id'] == task['id'], u_db['tasks']))[0]
                        id_list.append(current_task['id'])
                        resp.append([index,current_task['category'],task['title'], f_date, task_list['title'], status_converter(task['status']), current_task['priority']])
                        resp_int.append([task['id'],task_list['id'],task['title']])
                        index += 1
                if len(resp) == 0:
                    await ctx.channel.send("No tasks found")
                    return None
                final_response = table2ascii(header=headings, body=resp)
                final_response = '```\n' + final_response + '\n```'
                chunks = [final_response[i:i + 2000] for i in
                          range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk)

                await ctx.channel.send('Enter a task number from the above list to select :')

                def validator(message: discord.Message) -> bool:
                    """Validate if the user has selected a task from within the list"""
                    try:
                        ct = int(message.content)
                        if ct < 0 or (ct > (len(resp) - 1)):
                            return False
                        return True
                    except ValueError:
                        return False

                t_no = await bot.wait_for('message', timeout=20.0, check=validator)
                t_no = int(t_no.content)
                t_id = id_list[t_no]
                tsk_lst = u_db['tasks']
                task_index = [t_id == i['id'] for i in tsk_lst].index(True)
                await ctx.channel.send(f"Successfully selected task {resp[task_index][2]}")
                if not get_task_name:
                    return resp_int[task_index][0], resp_int[task_index][1]
                else:
                    return resp_int[task_index][0], resp_int[task_index][1], resp_int[task_index][2]
            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
                return None
            except Exception as e:
                await ctx.channel.send("Error fetching user tasks")
    return None

@bot.event
async def on_message(message : discord.Message):
    """Process each user DM message"""
    await bot.process_commands(message)
    if message.channel.type == discord.ChannelType.private:
        if message.content.startswith('initialise'):
            user_id = str(message.author.id)
            us = TskUser(user_id, CLIENT)
            if us.user_exists():
                await message.channel.send(f"You are already initialised")
                return
            else:
                await message.channel.send(f'Initialising\nYour member id is {message.author.id}')
                await message.channel.send('Click on the link and authorize within 60 seconds to continue')
                await message.channel.send(generate_auth_url(message.author.id), delete_after=60.0)
                for i in range(6):
                    if us.user_exists():
                        await message.channel.send(f"You are successfully initialised")
                        return
                    else:
                        print("User still not registered")
                        pass
                    await asyncio.sleep(10)
                await  message.channel.send("Authorisation cancelled")
        elif message.content.startswith('query '):
            user_id = str(message.author.id)
            us = TskUser(user_id, CLIENT)
            gclt = GoogleTasksClient(user_id, CLIENT)
            query = message.content[6:]
            if len(query) > 100:
                query = query[:100]
            query = re.sub('[^A-Za-z0-9 ]+','',query) # Sanitize user query
            if us.user_exists():
                response =  await ai_client.aio.models.generate_content(
                            model="gemini-2.0-flash", contents=PROMPT_1+query
                            )
                t_out = response.text
                t_out = t_out[0]
                print(t_out)
                if t_out == 'i':
                    response1 = await ai_client.aio.models.generate_content(
                        model="gemini-2.0-flash", contents=PROMPT_2+query
                    )
                    t_out = response1.text
                    t_out = t_out[0]
                    ctx = await bot.get_context(message)
                    try :
                        t_out = int(t_out)
                        if 1 <= t_out <= 4:
                            if t_out == 1:
                                await ctx.invoke(bot.get_command("get_overdue_tasks"))
                            elif t_out == 2:
                                await ctx.invoke(bot.get_command("list_tasks"))
                                return
                            elif t_out == 3:
                                await ctx.invoke(bot.get_command("list_tasklists"))
                            else:
                                await ctx.invoke(bot.get_command("list_reminders"))
                        else:
                            await message.channel.send("Failed processing query")
                            return
                    except ValueError:
                        await message.channel.send("Failed processing query")
                        return

                elif t_out == 'a': # Currently only task creation is supported
                    response1 = await ai_client.aio.models.generate_content(
                        model="gemini-2.0-flash", contents=PROMPT_3 + query
                    )
                    t_out = response1.text

                    def task_validator(message: str) -> bool:
                        tokenized = message.split()
                        index = 0
                        d_index = 0
                        d_toks = 0
                        for token in tokenized:
                            try:
                                datetime.strptime(token, "%Y-%m-%d")
                                d_toks += 1
                                d_index = index
                            except ValueError:
                                pass
                            index += 1
                        if d_toks == 1:  # Check if only one date is present in input
                            pass
                        else:
                            return False
                        if d_index != 0:
                            task_name = tokenized[0:d_index]
                            task_name = "".join(task_name)
                        else:
                            return False
                        task_due = datetime.strptime(tokenized[d_index], "%Y-%m-%d").date()
                        today = date.today()
                        if task_due < today:  # Date is in the past
                            return False
                        year = timedelta(days=365)
                        max_spread = today + year
                        if task_due > max_spread:  # Task is more than one year after
                            return False
                        return True
                    if t_out == "invalid":
                        await message.channel.send("Failed processing query")
                        return
                    try :
                        if task_validator(t_out):
                            tsk = str_to_task(t_out)
                            tl = gclt.get_task_lists()[0]['id']
                            gclt.create_task(task_list_id=tl,title=tsk[0],notes=tsk[1],due=tsk[2])
                            await message.channel.send(f"Task {tsk[0]} created successfully")

                        else:
                            await message.channel.send("Failed processing query")
                            return
                    except ValueError:
                        await message.channel.send("Failed processing query")
                        return
                    ctx = await bot.get_context(message)
                    pass
                else:
                    await message.channel.send("Failed processing query")
                    return
            else:
                await message.channel.send(f"Initialise by typing initialise first and register yourself")
                return




@bot.command()
async def list_tasks(ctx : discord.ext.commands.Context):
    """Function to list all the users tasks , the tasklist and their due time"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                   delete_after=10)
            try:
                clt = GoogleTasksClient(user_id,CLIENT)
                tl = clt.get_task_lists()
            except Exception as e:
                await ctx.channel.send("Error fetching user tasks")
                return
            headings = ['Category','Task Name', 'Due Date', 'Tasklist', 'Status','Priority']
            resp = []
            sync_tasks_g2m(user_id, CLIENT)
            ns_db = load_mongo_db(user_id, CLIENT, nosync = True)
            ns_db = ns_db['user']['tasks']
            for task_list in tl:
                tr = clt.get_tasks(task_list['id'])['items']

                for task in tr:
                    if 'due' in task:
                        f_date = datetime.fromisoformat(task['due']).astimezone()
                        f_date = f_date.strftime("%B %d, %Y")
                    else:
                        f_date = 'Not Set / Passed'
                    current_task = list(filter(lambda t: t['id'] == task['id'], ns_db))[0]
                    resp.append([current_task['category'],task['title'], f_date, task_list['title'], status_converter(task['status']), current_task['priority']])
            if len(resp) == 0:
                await ctx.channel.send("No tasks found")
                return
            resp.sort(key=lambda t: priority_map[t[5]], reverse=True)
            final_response = table2ascii(header=headings, body=resp)
            final_response = '```\n' + final_response + '\n```'
            chunks = [final_response[i:i + 2000] for i in
                      range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.channel.send(chunk)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")


@bot.command()
async def list_tasklists(ctx : discord.ext.commands.Context):
    """Function to list all the users tasklists"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                   delete_after=10)
            try:
                clt = GoogleTasksClient(user_id,CLIENT)
                tl = clt.get_task_lists()
            except Exception as e:
                await ctx.channel.send("Error fetching user tasklists")
                return
            headings = ['Tasklist Name', 'Last Updated']
            resp = []
            for task_list in tl:
                resp.append([task_list['title'],
                             datetime.fromisoformat(task_list['updated']).astimezone().strftime("%B %d, %Y")])
            final_response = table2ascii(header=headings, body=resp)
            final_response = '```\n' + final_response + '\n```'
            sync_tasks_g2m(user_id, CLIENT)
            chunks = [final_response[i:i + 2000] for i in
                      range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.channel.send(chunk)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")


@bot.command()
async def create_tasklist(ctx : discord.ext.commands.Context):
    """Function to create a new tasklist"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            await ctx.channel.send(f"Enter tasklist name to create below", delete_after=20)

            def validator(message: discord.Message) -> bool:
                if len(message.content) == 0 or len(message.content) > 100:
                    return False
                return True

            try:
                message = await bot.wait_for('message', timeout=20.0, check=validator)
                clt = GoogleTasksClient(user_id,CLIENT)
                clt.create_task_list(message.content)
                await ctx.channel.send(f"Tasklist {message.content} created successfully")
                await ctx.channel.send(f"Current Tasklists ", delete_after=21)
                tl = clt.get_task_lists()
                headings = ['Tasklist Name', 'Last Updated']
                resp = []
                for task_list in tl:
                    resp.append([task_list['title'],
                                 datetime.fromisoformat(task_list['updated']).astimezone().strftime("%B %d, %Y")])
                final_response = table2ascii(header=headings, body=resp)
                final_response = '```\n' + final_response + '\n```'
                sync_tasks_g2m(user_id, CLIENT)
                chunks = [final_response[i:i + 2000] for i in
                          range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk, delete_after=20)
            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
            except Exception as e:
                await ctx.channel.send("Error fetching user ")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")


@bot.command()
async def create_task(ctx : discord.ext.commands.Context):
    """Function to create a new task"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try:
                await ctx.channel.send(f"Enter tasklist number to add the task to : ", delete_after=10)
                clt = GoogleTasksClient(user_id,CLIENT)
                tl = clt.get_task_lists()
                headings = ['No', 'Tasklist Name', 'Last Updated']
                resp = []
                id_list = []
                index = 0
                for task_list in tl:
                    id_list.append(task_list['id'])
                    resp.append([str(index), task_list['title'],
                                 datetime.fromisoformat(task_list['updated']).astimezone().strftime("%B %d, %Y")])
                    index += 1
                final_response = table2ascii(header=headings, body=resp)
                final_response = '```\n' + final_response + '\n```'
                sync_tasks_g2m(user_id, CLIENT)
                chunks = [final_response[i:i + 2000] for i in
                          range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk, delete_after=20)

                def validator(message: discord.Message) -> bool:
                    try:
                        ct = int(message.content)
                        if ct < 0 or (ct > (len(resp) - 1)):
                            return False
                        return True
                    except ValueError:
                        return False

                def task_validator(message: discord.Message) -> bool:
                    tokenized = message.content.split()
                    index = 0
                    d_index = 0
                    d_toks = 0
                    for token in tokenized:
                        try:
                            datetime.strptime(token, "%Y-%m-%d")
                            d_toks += 1
                            d_index = index
                        except ValueError:
                            pass
                        index += 1
                    if d_toks == 1:  # Check if only one date is present in input
                        pass
                    else:
                        return False
                    if d_index != 0:
                        task_name = tokenized[0:d_index]
                        task_name = "".join(task_name)
                    else:
                        return False
                    task_due = datetime.strptime(tokenized[d_index], "%Y-%m-%d").date()
                    today = date.today()
                    if task_due < today:  # Date is in the past
                        return False
                    year = timedelta(days=365)
                    max_spread = today + year
                    if task_due > max_spread:  # Task is more than one year after
                        return False
                    return True

                message = await bot.wait_for('message', timeout=10.0, check=validator)
                tl_no = int(message.content)
                await ctx.channel.send(f'You have selected tasklist {resp[tl_no][1]}', delete_after=20)
                await ctx.channel.send(f"Enter Details in the following format : \n{format_str}", delete_after=21)
                task_msg = await bot.wait_for('message', timeout=30.0, check=task_validator)
                task = str_to_task(task_msg.content)
                new_task = clt.create_task(task_list_id=id_list[tl_no], title=task[0], notes=task[1], due=task[2])
                sync_tasks_g2m(user_id, CLIENT)
                ns_db = load_mongo_db(user_id, CLIENT, nosync=True)
                ns_db["user"]["tasks"].append(
                    {"id": new_task["id"], "title": new_task["title"], "status": new_task["status"],
                     "priority": "not_set", "category": "not_set"})
                save_to_db(user_id, ns_db, CLIENT, nosync=True)
                await ctx.channel.send(f"Task {task[0]} created successfully in tasklist {resp[tl_no][1]}")

            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user / Task Creation Error ")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

@bot.command()
async def list_category(ctx : discord.ext.commands.Context):
    """Function to list a user's categories"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try:
                db_ns = load_mongo_db(user_id, CLIENT, nosync=True)
                db_ns = db_ns["user"]
                categories = db_ns["categories"]
                cat_body = []
                for c in categories:
                    cat_body.append([c])
                if len(categories) == 0:
                    await ctx.channel.send("No categories created. First create a category by using `#create_category`")
                    return
                resp = table2ascii(header = ['Categories'], body=cat_body)
                resp = '```\n' + resp + '\n```'
                chunks = [resp[i:i + 2000] for i in
                          range(0, len(resp), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk, delete_after=20)

            except KeyError:
                await ctx.channel.send("Error finding user")

            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error finding user")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

@bot.command()
async def create_category(ctx : discord.ext.commands.Context):
    """Function to allow the user to create a new category"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try:
                db_ns = load_mongo_db(user_id, CLIENT, nosync=True)
                categories = db_ns["user"]["categories"]
                await ctx.channel.send(f"Enter a category name to create (length =< 32) : ")
                def validator(message: discord.Message) -> bool:
                    m_len = len(message.content)
                    if m_len <= 32:
                        return True
                    else:
                        return False
                cat = await bot.wait_for('message', timeout=20.0, check=validator)
                cat = cat.content
                if cat in categories:
                    await ctx.channel.send(f"Category {cat} already exists please try again using another category name")
                    return
                db_ns["user"]["categories"].append(cat)
                save_to_db(user_id, db_ns, CLIENT, nosync=True)
                await ctx.channel.send(f"Category {cat} successfully created")

            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
            except KeyError:
                await ctx.channel.send("Error finding user")
            except Exception as e:
                await ctx.channel.send("Error finding user")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

@bot.command()
async def assign_category(ctx : discord.ext.commands.Context):
    """Function to allow the user to assign a category to a task"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try:
                await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                       delete_after=10)
                try:
                    clt = GoogleTasksClient(user_id,CLIENT)
                    tl = clt.get_task_lists()
                except Exception as e:
                    await ctx.channel.send("Error fetching user tasks")
                    return
                headings = ['No','Category','Task Name', 'Due Date', 'Tasklist', 'Status','Priority']
                resp = []
                sync_tasks_g2m(user_id, CLIENT)
                ns_db = load_mongo_db(user_id, CLIENT, nosync = True)

                u_db = ns_db["user"]
                index = 0
                id_list = []
                for task_list in tl:
                    tr = clt.get_tasks(task_list['id'])['items']

                    for task in tr:
                        if 'due' in task:
                            f_date = datetime.fromisoformat(task['due']).astimezone()
                            f_date = f_date.strftime("%B %d, %Y")
                        else:
                            f_date = 'Not Set / Passed'
                        current_task = list(filter(lambda t: t['id'] == task['id'], u_db['tasks']))[0]
                        id_list.append(current_task['id'])
                        resp.append([index,current_task['category'],task['title'], f_date, task_list['title'], status_converter(task['status']), current_task['priority']])
                        index += 1
                if len(resp) == 0:
                    await ctx.channel.send("No tasks found")
                    return
                final_response = table2ascii(header=headings, body=resp)
                final_response = '```\n' + final_response + '\n```'
                chunks = [final_response[i:i + 2000] for i in
                          range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk)

                await ctx.channel.send('Enter a task number from the above list to assign a category to :')

                def validator(message: discord.Message) -> bool:
                    """Validate if the user has selected a task from within the list"""
                    try:
                        ct = int(message.content)
                        if ct < 0 or (ct > (len(resp) - 1)):
                            return False
                        return True
                    except ValueError:
                        return False

                t_no = await bot.wait_for('message', timeout=20.0, check=validator)
                t_no = int(t_no.content)
                t_id = id_list[t_no]
                tsk_lst = u_db['tasks']
                task_index = [t_id == i['id'] for i in tsk_lst].index(True)
                await ctx.channel.send(f"Successfully selected task {resp[task_index][2]}")

                categories = deepcopy(u_db["categories"])
                if "not_set" not in categories:
                    categories.append("not_set")
                cat_body = [ [i,categories[i]] for i in range(len(categories)) ]
                if len(u_db["categories"]) == 0:
                    await ctx.channel.send("No categories created. First create a category by using `#create_category`")
                    return
                cat_resp = table2ascii(header=['No','Categories'], body=cat_body)
                cat_resp = '```\n' + cat_resp + '\n```'
                cat_chunks = [cat_resp[i:i + 2000] for i in
                          range(0, len(cat_resp), 2000)]  # Split into 2000 sized chunks
                for chunk in cat_chunks:
                    await ctx.channel.send(chunk, delete_after=20)
                await ctx.channel.send("Enter a category number from the above list to assign to the task : ")
                def cat_validator(message: discord.Message) -> bool:
                    """Validate if the user has selected a category from within the list"""
                    try:
                        ct = int(message.content)
                        if ct < 0 or (ct > (len(cat_resp) - 1)):
                            return False
                        return True
                    except ValueError:
                        return False
                cat_index = await bot.wait_for('message', timeout=20.0, check=cat_validator)
                cat_index = int(cat_index.content)

                ns_db['user']['tasks'][task_index]['category'] = categories[cat_index]
                save_to_db(user_id, ns_db, CLIENT, nosync=True)
                await ctx.channel.send(f"Successfully assigned category {categories[cat_index]} to task {resp[task_index][2]}")

            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user ")


        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")
@bot.command()
async def assign_priority(ctx : discord.ext.commands.Context):
    """Function to allow the user to assign a priority to a task"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try:
                await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                       delete_after=10)
                try:
                    clt = GoogleTasksClient(user_id,CLIENT)
                    tl = clt.get_task_lists()
                except Exception as e:
                    await ctx.channel.send("Error fetching user tasks")
                    return
                headings = ['No','Category','Task Name', 'Due Date', 'Tasklist', 'Status','Priority']
                resp = []
                sync_tasks_g2m(user_id, CLIENT)
                ns_db = load_mongo_db(user_id, CLIENT, nosync = True)

                u_db = ns_db["user"]
                index = 0
                id_list = []
                for task_list in tl:
                    tr = clt.get_tasks(task_list['id'])['items']

                    for task in tr:
                        if 'due' in task:
                            f_date = datetime.fromisoformat(task['due']).astimezone()
                            f_date = f_date.strftime("%B %d, %Y")
                        else:
                            f_date = 'Not Set / Passed'
                        current_task = list(filter(lambda t: t['id'] == task['id'], u_db['tasks']))[0]
                        id_list.append(current_task['id'])
                        resp.append([index,current_task['category'],task['title'], f_date, task_list['title'], status_converter(task['status']), current_task['priority']])
                        index += 1
                if len(resp) == 0:
                    await ctx.channel.send("No tasks found")
                    return
                final_response = table2ascii(header=headings, body=resp)
                final_response = '```\n' + final_response + '\n```'
                chunks = [final_response[i:i + 2000] for i in
                          range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk)

                await ctx.channel.send('Enter a task number from the above list to assign a priority to :')

                def validator(message: discord.Message) -> bool:
                    try:
                        ct = int(message.content)
                        if ct < 0 or (ct > (len(resp) - 1)):
                            return False
                        return True
                    except ValueError:
                        return False

                t_no = await bot.wait_for('message', timeout=20.0, check=validator)
                t_no = int(t_no.content)
                t_id = id_list[t_no]
                tsk_lst = u_db['tasks']
                task_index = [t_id == i['id'] for i in tsk_lst].index(True)
                await ctx.channel.send(f"Successfully selected task {resp[task_index][2]}")


                await ctx.channel.send("Enter a priority (low,medium,high) to assign to the task  : ")
                def priority_validator(message: discord.Message) -> bool:
                    priority_sel = message.content.upper()
                    if priority_sel in ['LOW', 'MEDIUM', 'HIGH','not_set']:
                        return True
                    else:
                        return False
                priority = await bot.wait_for('message', timeout=20.0, check=priority_validator)
                if priority != 'not_set':
                    priority = priority.content.upper()

                ns_db['user']['tasks'][task_index]['priority'] = priority
                save_to_db(user_id, ns_db, CLIENT, nosync=True)
                await ctx.channel.send(f"Successfully assigned priority {priority} to task {resp[task_index][2]}")

            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user ")


        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")
@bot.command()
async def toggle_task(ctx : discord.ext.commands.Context):
    """Function to allow the user to toggle a task's completion status"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try :
                clt = GoogleTasksClient(user_id,CLIENT)
                task_selected = await selector(ctx)
                if task_selected:
                    task = clt.get_task(task_id=task_selected[0],task_list_id=task_selected[1])
                    if task:
                        status = task['status']
                        if status == 'completed':
                            clt.uncomplete_task(task_id=task_selected[0],task_list_id=task_selected[1])
                        else:
                            clt.complete_task(task_id=task_selected[0],task_list_id=task_selected[1])
                        sync_tasks_g2m(user_id, CLIENT)
                        await ctx.channel.send(f"Task {task['title']}'s status has been toggled successfully")
                        return
                    await ctx.channel.send("Error finding task", delete_after=20)
                    return
                else:
                    await ctx.channel.send("Toggle task operation cancelled",delete_after=20)
                    return
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user ")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

@bot.command()
async def set_timezone(ctx : discord.ext.commands.Context):
    """Function to set user timezone"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try :
                await ctx.channel.send(f"Enter a valid timezone to set : \nExample : `Asia/Kolkata`\nNote : Timezones are case-sensitive")
                def tz_validator(message: discord.Message) -> bool:
                    tz_info = message.content
                    if tz_info in common_timezones:
                        return True
                    return False
                tz_sel = await bot.wait_for('message', timeout=20.0, check=tz_validator)
                tz_sel = tz_sel.content
                auth = CLIENT.clt['TBot_DB']['auth']
                usr = auth.find_one({"user.user_id": user_id})
                if usr is not None:
                    del usr['_id']
                usr['user']['timezone'] = tz_sel
                keys = list(usr.keys())
                uid = str(keys[0])
                result = auth.update_one(
                    {"user.user_id": user_id},  # Filter: documents that have uid field
                    {"$set": usr},
                )
                if result.acknowledged:
                    await ctx.channel.send(f"Successfully updated timezone")
                else:
                    await ctx.channel.send(f"Error updating timezone")
            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later choosing a valid timezone")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

@bot.command()
async def delete_task(ctx : discord.ext.commands.Context):
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try :
                clt = GoogleTasksClient(user_id,CLIENT)
                task_selected = await selector(ctx)
                if task_selected:
                    clt.delete_task(task_id=task_selected[0],task_list_id=task_selected[1])
                    sync_tasks_g2m(user_id, CLIENT)
                    await ctx.channel.send(f"Successfully deleted task")
                    await ctx.channel.send(f"New task list")
                    cmd = bot.get_command("list_tasks")
                    # noinspection PyTypeChecker
                    await ctx.invoke(cmd)
                else:
                    await ctx.channel.send("Error finding task", delete_after=20)
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user ",delete_after=20)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself",delete_after=30)

@bot.command()
async def modify_task(ctx : discord.ext.commands.Context):
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            try :
                clt = GoogleTasksClient(user_id,CLIENT)
                task_selected = await selector(ctx)
                if task_selected:
                    def task_validator(message: discord.Message) -> bool:
                        tokenized = message.content.split()
                        index = 0
                        d_index = 0
                        d_toks = 0
                        for token in tokenized:
                            try:
                                datetime.strptime(token, "%Y-%m-%d")
                                d_toks += 1
                                d_index = index
                            except ValueError:
                                pass
                            index += 1
                        if d_toks == 1:  # Check if only one date is present in input
                            pass
                        else:
                            return False
                        if d_index != 0:
                            task_name = tokenized[0:d_index]
                            task_name = "".join(task_name)
                        else:
                            return False
                        task_due = datetime.strptime(tokenized[d_index], "%Y-%m-%d").date()
                        today = date.today()
                        if task_due < today:  # Date is in the past
                            return False
                        year = timedelta(days=365)
                        max_spread = today + year
                        if task_due > max_spread:  # Task is more than one year after
                            return False
                        return True
                    await ctx.channel.send(f"Enter Details in the following format : \n{format_str}", delete_after=40)
                    task_msg = await bot.wait_for('message', timeout=40.0, check=task_validator)
                    task = str_to_task(task_msg.content)
                    patched_task = clt.update_task(task_list_id=task_selected[1],task_id=task_selected[0],title=task[0], notes=task[1], due=task[2])
                    ns_db = load_mongo_db(user_id, CLIENT, nosync=True)
                    ns_db["user"]["tasks"].append(
                        {"id": patched_task["id"], "title": patched_task["title"], "status": patched_task["status"],
                         "priority": "not_set", "category": "not_set"})
                    save_to_db(user_id, ns_db, CLIENT, nosync=True)
                    await ctx.channel.send(f"Task {task[0]} modified successfully")
                    sync_tasks_g2m(user_id, CLIENT)

                else:
                    await ctx.channel.send("Error finding task", delete_after=20)
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user ",delete_after=20)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself",delete_after=30)

async def rt_sync_available(task_id : str) -> bool:
    rem_db = CLIENT.clt['TBot_DB']['reminders']
    synced_task = list(rem_db.find({"task_id": task_id,"task_sync":"yes","recurring":"yes"}))
    if len(synced_task) == 0:
        return True
    return False

@bot.command()
async def create_reminder(ctx : discord.ext.commands.Context):
    """Command to allow the user to create reminders"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            await ctx.channel.send("Select a task to set reminder for : ",delete_after=10)
            task_selected = await selector(ctx,get_task_name=True)
            if task_selected:
                try :
                    auth = CLIENT.clt['TBot_DB']['auth']
                    usr = auth.find_one({"user.user_id": user_id})
                    if usr is not None:
                        del usr['_id']
                    usr_timezone = usr['user']['timezone']
                    rem_db = CLIENT.clt['TBot_DB']['reminders']
                    if usr_timezone == 'not_set':
                        await ctx.channel.send(f"You need to set a timezone first using `#set_timezone` command",delete_after=15)
                        return
                    await ctx.channel.send("Enter valid date in YYYY-MM-DD format : ",delete_after=40)
                    def date_validator(message: discord.Message) -> bool:
                        dt = message.content
                        try :
                            now = datetime.now()
                            now = tz(usr_timezone).localize(now)
                            cd = now.date() # Get current date in user's timezone
                            dt = date.fromisoformat(dt)
                            if dt >= cd:
                                return True
                            return False
                        except ValueError:
                            return False
                    date_sel = await bot.wait_for('message', timeout=40.0, check=date_validator)
                    date_sel = date_sel.content
                    await ctx.channel.send("Enter valid time in HH-MM (24 hour format) \n Example : `16:30`", delete_after=40)
                    def time_validator(message: discord.Message) -> bool:
                        time_sel = message.content
                        tm = date_sel + " " + time_sel + ":00"
                        try :
                            tm = iso_localizer(tm,usr_timezone)
                            now = datetime.now()
                            now = tz(local_tz).localize(now)
                            now = now.astimezone(tz('UTC'))
                            if tm >= now:
                                return True
                            return False
                        except ValueError:
                            return False
                    time_sel = await bot.wait_for('message', timeout=25.0, check=time_validator)
                    def rec_val(message: discord.Message) -> bool:
                        if message.content.lower() in ['yes','no']:
                            return True
                        return False

                    await ctx.channel.send("Do you want reminder to be recurring : Yes/No",delete_after=20)
                    choice = await bot.wait_for('message', timeout=20.0, check=rec_val)
                    choice = choice.content.lower()
                    recurrence_interval = 0
                    rem_sync = 'no'
                    if choice == 'yes':
                        await ctx.channel.send("Enter recurrence interval in days from (1,30): ", delete_after=20)
                        def rec_int_val(message: discord.Message) -> bool:
                            try:
                                days = int(message.content)
                                if days > 0 and days <= 30 :
                                    return True
                                return False
                            except ValueError:
                                return False
                        rec_int = await bot.wait_for('message', timeout=20.0, check=rec_int_val)
                        recurrence_interval = int(rec_int.content)
                        sync_available = await rt_sync_available(task_selected[0])
                        if sync_available:
                            await ctx.channel.send("Do you want the reminder to sync with task due date ? (Yes/No) \nThis will immediately set the task due date to current reminder date and change due date and reset task completion status every time reminder is repeated.\nNote : Only one reminder per task can be synced", delete_after=20)
                            sync_resp = await bot.wait_for('message', timeout=20.0, check=rec_val)
                            sync_resp = sync_resp.content.lower()
                            rem_sync = sync_resp



                    time_sel = time_sel.content
                    date_time = date_sel + " " + time_sel + ":00"
                    obj = iso_localizer(date_time,usr_timezone)
                    unique_id = "".join(str(uuid4()).split('-'))

                    reminder = {
                        "reminder_id": unique_id, # Unique id for reminder
                        "user_id": user_id,       # User id
                        "task_id": task_selected[0], # Reminder task id
                        "tasklist_id": task_selected[1], # Reminder tasklist id
                        "task_name": task_selected[2], # Reminder task name
                        "due" : obj, # Reminder due time converted to utc
                        "due_date" : str(obj.date()), # Reminder due date (UTC)
                        "recurring" : choice ,
                        "recurrence_interval" : recurrence_interval,
                        "task_sync" : rem_sync,
                        "times_reminded" : 0,
                        "times_completed" : 0,  # Only works with synced tasks
                    }
                    operation = rem_db.insert_one(reminder)
                    if operation.acknowledged:
                        await ctx.channel.send(f"Successfully created reminder for task {task_selected[2]} at {date_time}", delete_after=20)
                    else:
                        await ctx.channel.send("Error creating reminder", delete_after=20)
                except asyncio.TimeoutError:
                    await ctx.channel.send("Time elapsed / Invalid date entered", delete_after=25)

        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself",delete_after=30)

@bot.command()
async def list_reminders(ctx : discord.ext.commands.Context):
    """Function to list all the user's reminders"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            auth = CLIENT.clt['TBot_DB']['auth']
            usr = auth.find_one({"user.user_id": user_id})
            if usr is not None:
                del usr['_id']
            usr_timezone = usr['user']['timezone']
            rem_db = CLIENT.clt['TBot_DB']['reminders']
            reminders = list(rem_db.find({"user_id": user_id}))
            if len(reminders) > 0:
                rem_resp = []
                hdrs = ['Task Name','Due Date','Due Time','Recurring','Sync']
                for rem in reminders:
                    tm = rem['due']
                    tm = tz('utc').localize(tm)
                    tm = tm.astimezone(tz(usr_timezone))
                    rem_date = tm.date().strftime("%B %d, %Y")
                    rem_time = str(tm.time())
                    rem_resp.append([rem['task_name'],rem_date,rem_time,rem['recurring'].upper(),rem['task_sync'].upper()])
                await ctx.channel.send(f"Showing results in user timezone `{usr_timezone}`")

                final_resp = "```\n"+table2ascii(header=hdrs,body=rem_resp)+"\n```"
                chunks = [final_resp[i:i + 2000] for i in
                          range(0, len(final_resp), 2000)]  # Split into 2000 sized chunks
                for chunk in chunks:
                    await ctx.channel.send(chunk)

            else:
                await ctx.channel.send("No reminders exist first create a reminder using `#create_reminder` command",delete_after=15)
                await ctx.channel.send("Note : In order to receive reminder alerts your reminders should be created at least 30 minutes before the due time \n This is a limitation of the bot necessary to reduce server load.", delete_after=15)
                return

        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself", delete_after=30)

@bot.command()
async def get_overdue_tasks(ctx : discord.ext.commands.Context):
    """Function to list all the users tasks , the tasklist and their due time"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id,CLIENT)
        if us.user_exists():
            await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                   delete_after=10)
            try:
                clt = GoogleTasksClient(user_id,CLIENT)
                tl = clt.get_task_lists()
            except Exception as e:
                await ctx.channel.send("Error fetching user tasks")
                return
            headings = ['Category','Task Name', 'Due Date', 'Tasklist', 'Status','Priority']
            resp = []
            sync_tasks_g2m(user_id, CLIENT)
            ns_db = load_mongo_db(user_id, CLIENT, nosync = True)
            ns_db = ns_db['user']['tasks']
            for task_list in tl:
                tr = clt.get_tasks(task_list['id'])['items']

                for task in tr:
                    if 'due' in task:
                        f_date = datetime.fromisoformat(task['due']).astimezone()
                        if f_date > tz('UTC').localize(datetime.now()):
                            continue
                        f_date = f_date.strftime("%B %d, %Y")
                    else:
                        continue
                    current_task = list(filter(lambda t: t['id'] == task['id'], ns_db))[0]
                    resp.append([current_task['category'],task['title'], f_date, task_list['title'], status_converter(task['status']), current_task['priority']])
            if len(resp) == 0:
                await ctx.channel.send("No such tasks found")
                return
            resp.sort(key=lambda t: priority_map[t[5]], reverse=True)
            final_response = table2ascii(header=headings, body=resp)
            final_response = '```\n' + final_response + '\n```'
            chunks = [final_response[i:i + 2000] for i in
                      range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.channel.send(chunk)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

bot.run(TOKEN_DISCORD)
