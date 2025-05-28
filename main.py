import asyncio
import discord
from discord.ext import commands
from dotenv import dotenv_values
from Auth_Server import generate_auth_url
from User import User as TskUser
from datetime import datetime
from Tasks import GoogleTasksClient
from table2ascii import table2ascii
config = dotenv_values(".env")
TOKEN_DISCORD = config["DISCORD_BOT_TOKEN"]
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="#", intents=intents)
def status_converter(status : str) -> str:
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
                await message.channel.send(generate_auth_url(message.author.id),delete_after=60.0)
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
async def list_tasks(ctx,arg):
    """Function to list all the users tasks , the tasklist and their due time"""
    if ctx.channel.type == discord.ChannelType.private:
        us = TskUser(str(ctx.author.id))
        if us.user_exists():
            await ctx.channel.send(f"Loading task list for user {ctx.author.name} (Synced from Google Tasks)")
            clt = GoogleTasksClient(user_id=str(ctx.author.id))
            tl = clt.get_task_lists()
            headings = ['Task Name','Due time','Tasklist','Status']
            resp = []
            for task_list in tl:
                tr = clt.get_tasks(task_list['id'])['items']
                for task in tr:
                    f_date = datetime.fromisoformat(task['due']).astimezone()
                    f_date = f_date.strftime("%B %d, %Y %I:%M:%S %p")
                    resp.append([task['title'], f_date,task_list['title'],status_converter(task['status'])])
            final_response = table2ascii(header=headings,body=resp)
            final_response = '```\n'+ final_response + '\n```'
            chunks = [final_response[i:i + 2000] for i in range(0, len(final_response), 2000)] # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.channel.send(chunk)
        else:
            await ctx.channel.send(f"Initialise by typing initialise first and register yourself")

bot.run(TOKEN_DISCORD)
