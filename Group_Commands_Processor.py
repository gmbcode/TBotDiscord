import asyncio
from tabnanny import check
from typing import Tuple,Callable,Dict
import discord
from dotenv import dotenv_values
from discord.ext import commands
from User import User as TskUser
from datetime import datetime, date, timedelta
from table2ascii import table2ascii
from User_Tasks import sync_tasks_g2m, load_mongo_db, save_to_db
from Misc_Methods import str_to_task, status_converter, iso_localizer
from Mongo_Access import DB_Client
from copy import deepcopy
from pytz import common_timezones
from pytz import timezone as tz
from uuid import uuid4
intents = discord.Intents.default()
intents.message_content = True
config = dotenv_values(".env")
TOKEN_DISCORD = config["DISCORD_BOT_TOKEN"]
local_tz = config["LOCAL_TZ"]
CLIENT = DB_Client()
grp_db = CLIENT.clt['TBot_DB']['groups']

bot = commands.Bot(command_prefix="#", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} on Group Commands Processor')
def len_checker(bound1 : int,bound2 : int) -> Callable[[discord.Message],bool]:
    """Return len checker function"""
    checker : Callable[[discord.Message],bool] = lambda message : bound2 >= len(message.content) >= bound1
    return checker

async def create_group_menu(ctx : discord.ext.commands.Context) -> Dict[str,str] | None:
    """Returns group dict if user successfully creates a group"""
    try:
        await ctx.send("Enter group name (Does not need to  be unique) (Has to be between 2 and 30 characters)  : ",ephemeral=True,delete_after=20)
        grp_name = await bot.wait_for('message', check=len_checker(2,30),timeout=20)
        grp_invite_unique = False
        for i in range(2):
            await ctx.send("Enter group invite name ( Has to be unique ) ( Between 6 and 15 characters)  : ",
                           ephemeral=True,delete_after=20)
            grp_invite_id = await bot.wait_for('message', check=len_checker(6, 15),timeout=20)
            grps = list(grp_db.find({"group_invite": grp_invite_id.content}))
            if len(grps) == 0:
                grp_invite_unique = True
                break
            else:
                await ctx.send("Group invite name already exists please enter a different name : ",ephemeral=True,delete_after=20)
        if not grp_invite_unique:
            await ctx.send("Maximum retries exceeded please try again later",ephemeral=True,delete_after=20)
            return None
        grp_id = str(uuid4()).replace('-', '')
        usr_role = 'Owner'
        grp = {"group_id" : grp_id,
               "group_invite" : grp_invite_id,
               "group_name" : grp_name,
               "role" : usr_role,
               }
        return grp


    except asyncio.TimeoutError:
        return None

@bot.command()
async def create_task_group(ctx : discord.ext.commands.Context):
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    if us.user_exists():
        group = await create_group_menu(ctx)

        if group:
            ns_db = load_mongo_db(user_id,CLIENT,nosync=True)
            ns_db['user']['groups'].append(group)
            save_to_db(user_id,ns_db,CLIENT,nosync=True)
            group_entry = {
                "group_id" : group['group_id'],
                "group_name" : group['group_name'],
                "group_invite" : group['group_invite'],
                "members" : [{"user_id" : user_id, "role" : group['role'],"user_name":ctx.author.name}],
                "group_tasks" : [],
                "invited_users" : [],
                "group_channel_id" : "not_set"
            }
            op = grp_db.insert_one(group_entry)
            if op.acknowledged:
                await ctx.send(f"Group {group['group_name']} created successfully",ephemeral=True)
                await ctx.send("Further steps : Link Group to channel and Invite members using `#link_group` and `#grp_invite` commands respectively",ephemeral=True)
            else:
                await ctx.send("Group creation failed",ephemeral=True)
        else:
            await ctx.send("Operation timed out please try again later",ephemeral=True,delete_after=20)
            return
    else:
        await ctx.channel.send("Initialise by typing initialise first and register yourself in bot DMs")

# TODO: List groups , List group tasks , invite member to group , create group task , delete group task , assign role , toggle group task status

bot.run(TOKEN_DISCORD)