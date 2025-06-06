import heapq
import discord
from discord.ext import commands,tasks
from discord.ext.commands import Context, errors
from discord.ext.commands._types import BotT

from Mongo_Access import DB_Client
from User import User as TskUser
from dotenv import dotenv_values
from datetime import datetime,date,time,timedelta
from pytz import timezone as tz
from Tasks import GoogleTasksClient
import asyncio
config = dotenv_values(".env")
local_tz = config["LOCAL_TZ"]
intents = discord.Intents.default()
CLIENT = DB_Client()
intents.message_content = True

class ReminderBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="#",intents = intents)
        self.reminder_queue = []
        self.queue_lock = asyncio.Lock()
        self.clt = CLIENT
        self.gclt = GoogleTasksClient
        self.db = CLIENT.clt['TBot_DB']['reminders']

    async def on_ready(self):
        print(f'We have logged in as {self.user} on Reminder bot')
        self.load_upcoming_reminders.start()
        self.send_loop.start()

    @tasks.loop(hours=1)
    async def load_upcoming_reminders(self):
        """Load upcoming reminders into queue"""
        start_time = datetime.now()
        start_time = tz(local_tz).localize(start_time)
        start_time = start_time.astimezone(tz('UTC')) # Get current time in UTC
        end_time = start_time + timedelta(hours=2)

        reminders = self.get_reminders_between(start_time, end_time)

        async with self.queue_lock:
            self.reminder_queue.clear()  # Prevent duplicates
            for reminder in reminders:
                del reminder['_id']
                timestamp = tz('UTC').localize(reminder['due']).timestamp()
                heapq.heappush(self.reminder_queue,(timestamp,reminder))

    def get_reminders_between(self,start_time, end_time):
        """Get reminders between start time and end time from Mongo db"""
        print("Start and end times")
        print(start_time)
        print(end_time)
        reminders_bw = self.db.find({
            "due" : {"$gte" : start_time,
                     "$lt" : end_time,},
            })
        reminders_bw = list(reminders_bw)
        print("Reminders loaded : ")
        print(str(reminders_bw))
        return reminders_bw

    @tasks.loop(seconds=30)
    async def send_loop(self):
        """Constantly keep sending reminders to users"""
        now = datetime.now()
        now = tz(local_tz).localize(now)
        now = now.astimezone(tz('UTC'))
        print("In send loop ")
        print("Topmost element in loop : " + str(self.reminder_queue))
        async with self.queue_lock:

            while self.reminder_queue and self.reminder_queue[0][0] <= now.timestamp():
                reminder = heapq.heappop(self.reminder_queue)[1]
                asyncio.create_task(self.send_reminder(reminder))

    async def send_reminder(self,reminder):
        print("Sending reminder : " + str(reminder))
        user_id = reminder['user_id']
        rem_id = reminder['reminder_id']
        usr = await self.fetch_user(user_id)
        task_usr = TskUser(user_id,self.clt)
        gclt = self.gclt(user_id,self.clt)
        task = gclt.get_task(task_list_id=reminder['tasklist_id'],task_id=reminder['task_id'])
        if task_usr.user_exists():
            if task["status"] == "needsAction":
                embed = discord.Embed(
                    title="!!! Reminder !!!",
                    description=f"Reminder for completing {reminder['task_name']}",
                    color=discord.Color.green()
                )
                await usr.send("Alert",embed=embed)
                self.db.delete_one({"reminder_id":reminder['reminder_id']})
                return
    async def on_command_error(self, context: Context[BotT], exception: errors.CommandError) -> None:
        if isinstance(exception, commands.CommandNotFound):
            pass
        else:
            print(str(exception))


rem_bot = ReminderBot()
rem_bot.run(config["DISCORD_BOT_TOKEN"])



