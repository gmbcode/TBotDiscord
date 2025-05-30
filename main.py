import asyncio
import discord
from discord.ext import commands
from dotenv import dotenv_values
from Auth_Server import generate_auth_url
from User import User as TskUser
from datetime import datetime, date, timedelta
from Tasks import GoogleTasksClient
from table2ascii import table2ascii
from User_Tasks import sync_tasks_c2l, load_local_db, save_local_db
from Misc_Methods import str_to_task

config = dotenv_values(".env")
TOKEN_DISCORD = config["DISCORD_BOT_TOKEN"]
format_str = "Task Name Due Date(YYYY-MM-DD) Notes(if any)\nExample : my task 2025-05-30 Some details about my task"
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="#", intents=intents)


def status_converter(status: str) -> str:
    """Miniature task status converter"""
    if status == "completed":
        return "✓"
    else:
        return "X"


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.channel.type == discord.ChannelType.private:
        if message.content.startswith('initialise'):
            us = TskUser(str(message.author.id))
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


@bot.command()
async def list_tasks(ctx):
    """Function to list all the users tasks , the tasklist and their due time"""
    if ctx.channel.type == discord.ChannelType.private:
        us = TskUser(str(ctx.author.id))
        if us.user_exists():
            await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                   delete_after=10)
            try:
                clt = GoogleTasksClient(user_id=str(ctx.author.id))
                tl = clt.get_task_lists()
            except Exception as e:
                await ctx.channel.send("Error fetching user tasks")
                return
            headings = ['Category','Task Name', 'Due Date', 'Tasklist', 'Status','Priority']
            resp = []
            sync_tasks_c2l(str(ctx.author.id))
            ns_db = load_local_db(nosync = True)
            ns_db = ns_db[str(ctx.author.id)]['tasks']
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
            final_response = table2ascii(header=headings, body=resp)
            final_response = '```\n' + final_response + '\n```'
            chunks = [final_response[i:i + 2000] for i in
                      range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.channel.send(chunk)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")


@bot.command()
async def list_tasklists(ctx):
    """Function to list all the users tasklists"""
    if ctx.channel.type == discord.ChannelType.private:
        us = TskUser(str(ctx.author.id))
        if us.user_exists():
            await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)",
                                   delete_after=10)
            try:
                clt = GoogleTasksClient(user_id=str(ctx.author.id))
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
            sync_tasks_c2l(str(ctx.author.id))
            chunks = [final_response[i:i + 2000] for i in
                      range(0, len(final_response), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.channel.send(chunk)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")


@bot.command()
async def create_tasklist(ctx):
    """Function to create a new tasklist"""
    if ctx.channel.type == discord.ChannelType.private:
        us = TskUser(str(ctx.author.id))
        if us.user_exists():
            await ctx.channel.send(f"Enter tasklist name to create below", delete_after=20)

            def validator(message: discord.Message) -> bool:
                if len(message.content) == 0 or len(message.content) > 100:
                    return False
                return True

            try:
                message = await bot.wait_for('message', timeout=20.0, check=validator)
                clt = GoogleTasksClient(user_id=str(ctx.author.id))
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
                sync_tasks_c2l(str(ctx.author.id))
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
async def create_task(ctx):
    """Function to create a new task"""
    if ctx.channel.type == discord.ChannelType.private:
        us = TskUser(str(ctx.author.id))
        if us.user_exists():
            try:
                await ctx.channel.send(f"Enter tasklist number to add the task to : ", delete_after=10)
                clt = GoogleTasksClient(user_id=str(ctx.author.id))
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
                sync_tasks_c2l(str(ctx.author.id))
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
                print(task)
                new_task = clt.create_task(task_list_id=id_list[tl_no], title=task[0], notes=task[1], due=task[2])
                sync_tasks_c2l(str(ctx.author.id))
                ns_db = load_local_db(nosync=True)
                ns_db[str(ctx.author.id)]["tasks"].append(
                    {"id": new_task["id"], "title": new_task["title"], "status": new_task["status"],
                     "priority": "not_set", "category": "not_set"})
                save_local_db(ns_db, nosync=True)
                await ctx.channel.send(f"Task {task[0]} created successfully in tasklist {resp[tl_no][1]}")

            except asyncio.TimeoutError:
                await ctx.channel.send("Time elapsed please try again later")
            except Exception as e:
                print(str(e))
                await ctx.channel.send("Error fetching user / Task Creation Error ")
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")


bot.run(TOKEN_DISCORD)
