import heapq
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context, errors
from discord.ext.commands._types import BotT
from Mongo_Access import DB_Client
from dotenv import dotenv_values
from datetime import datetime, date, time, timedelta
from pytz import timezone as tz
from Tasks import GoogleTasksClient
import asyncio

config = dotenv_values(".env")
local_tz = config["LOCAL_TZ"]
intents = discord.Intents.default()
CLIENT = DB_Client()
intents.message_content = True


class GroupBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="#", intents=intents)
        self.tasks_queue = []
        self.queue_lock = asyncio.Lock()
        self.clt = CLIENT
        self.gclt = GoogleTasksClient
        self.db = CLIENT.clt['TBot_DB']['group_tasks']
        self.auth_db = CLIENT.clt['TBot_DB']['auth']

    async def on_ready(self):
        print(f'We have logged in as {self.user} on Group Tasks bot')
        self.load_upcoming_tasks_due.start()
        self.send_loop.start()

    @tasks.loop(minutes=30)
    async def load_upcoming_tasks_due(self):
        """Load upcoming tasks due into queue"""
        start_time = datetime.now()
        start_time = tz(local_tz).localize(start_time)
        start_time = start_time.astimezone(tz('UTC'))  # Get current time in UTC
        end_time = start_time + timedelta(hours=2)

        due_tasks = self.get_tasks_due_between(start_time, end_time)

        async with self.queue_lock:
            self.tasks_queue.clear()  # Prevent duplicates
            for reminder in due_tasks:
                del reminder['_id']
                timestamp = tz('UTC').localize(reminder['due']).timestamp()
                heapq.heappush(self.tasks_queue, (timestamp, reminder))

    def get_tasks_due_between(self, start_time, end_time):
        """Get tasks due between start time and end time from Mongo DB"""
        print("Start and end times")
        print(start_time)
        print(end_time)
        reminders_bw = self.db.find({
            "due": {"$gte": start_time,
                    "$lt": end_time, },
        })
        reminders_bw = list(reminders_bw)
        print("Reminders loaded : ")
        print(str(reminders_bw))
        return reminders_bw

    @tasks.loop(seconds=20)
    async def send_loop(self):
        """Constantly keep sending alerts to users"""
        now = datetime.now()
        now = tz(local_tz).localize(now)
        now = now.astimezone(tz('UTC'))
        print("In send loop ")
        print("Topmost element in loop : " + str(self.tasks_queue))
        async with self.queue_lock:
            while self.tasks_queue and self.tasks_queue[0][0] <= now.timestamp():
                reminder = heapq.heappop(self.tasks_queue)[1]
                asyncio.create_task(self.send_group_task_update(reminder))

    async def send_group_task_update(self, grp_task):
        """Send group task updates"""
        print("Sending group task reminder : " + str(grp_task))
        group_id = grp_task['group_id']
        rem_id = grp_task['group_task_id']
        if grp_task['group_channel_id'] == 'not_set': # We will not process tasks without a proper channel set
            return
        grp = await self.fetch_channel(int(grp_task['group_channel_id']))

        if grp_task["status"] == "needsAction":
            embed_not_completed = discord.Embed(
                title="!!! Reminder !!!",
                description=f"You were not able to complete task {grp_task['task_title']} by the due time",
                color=discord.Color.red()
            )
            await grp.send("Alert", embed=embed_not_completed)
            for usr in grp_task['assigned_to']:
                us = await self.fetch_user(int(usr))
                await us.send(embed=embed_not_completed)
            return
        else:
            embed_completed = discord.Embed(
                title="!!! Reminder !!!",
                description=f"Nice work you were able to complete recurring task {grp_task['task_title']} by the due date",
                color=discord.Color.green()
            )
            await grp.send("Alert", embed=embed_completed)
            for usr in grp_task['assigned_to']:
                us = await self.fetch_user(int(usr))
                await us.send(embed=embed_completed)
            return


    async def on_command_error(self, context: Context[BotT], exception: errors.CommandError) -> None:
        """Handle random command errors"""
        if isinstance(exception, commands.CommandNotFound):
            pass
        else:
            print(str(exception))


grp_bot = GroupBot()
grp_bot.run(config["DISCORD_BOT_TOKEN"])
