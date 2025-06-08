import asyncio
from typing import Tuple, Callable, Dict, Any
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

def arr_bounds_checker(bound1 : int,bound2 : int) -> Callable[[discord.Message],bool]:
    """Return bounds checker function"""

    checker : Callable[[discord.Message],bool] = lambda message : bound2 >= int(message.content) >= bound1 if message.content.isdigit() else False
    return checker

async def create_group_menu(ctx : discord.ext.commands.Context) -> Dict[str,str] | None:
    """Returns group dict if user successfully creates a group"""
    try:
        await ctx.send("Enter group name (Does not need to  be unique) (Has to be between 2 and 30 characters)  : ",delete_after=20)
        grp_name = await bot.wait_for('message', check=len_checker(2,30),timeout=20)
        grp_invite_unique = False
        for i in range(2):
            await ctx.send("Enter group invite name ( Has to be unique ) ( Between 6 and 15 characters)  : ",
                           delete_after=20)
            grp_invite_id = await bot.wait_for('message', check=len_checker(6, 15),timeout=20)
            grps = list(grp_db.find({"group_invite": grp_invite_id.content.lower()}))
            if len(grps) == 0:
                grp_invite_unique = True
                break
            else:
                await ctx.send("Group invite name already exists please enter a different name : ",delete_after=20)
        if not grp_invite_unique:
            await ctx.send("Maximum retries exceeded please try again later",delete_after=20)
            return None
        grp_id = str(uuid4()).replace('-', '')
        usr_role = 'Owner'
        grp = {"group_id" : grp_id,
               "group_invite" : grp_invite_id.content.lower(),
               "group_name" : grp_name.content,
               "role" : usr_role,
               }
        return grp


    except asyncio.TimeoutError:
        return None

@bot.command()
async def create_task_group(ctx : discord.ext.commands.Context):
    if ctx.channel.type == discord.ChannelType.private:
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
                    await ctx.send(f"Group {group['group_name']} created successfully")
                    await ctx.send("Further steps : Link Group to channel and Invite members using `#link_group` and `#grp_invite` commands respectively",ephemeral=True)
                else:
                    await ctx.send("Group creation failed")
            else:
                await ctx.send("Operation timed out please try again later",delete_after=20)
                return
        else:
            await ctx.channel.send("Initialise by typing initialise first and register yourself in bot DMs")

@bot.command()
async def list_groups(ctx : discord.ext.commands.Context):
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id, CLIENT)
        if us.user_exists():
            ns_db = load_mongo_db(user_id,CLIENT,nosync=True)
            groups = ns_db['user']['groups']
            headers = ['Group Name','Group Invite','Role']
            data = []
            if len(groups) == 0:
                await ctx.send("You are not in any groups \n Either create a group using `#create_task_group` or join a group using `#join_group`",delete_after=20)
                return
            for group in groups:
                data.append([group['group_name'],group['group_invite'],group['role']])
            resp = table2ascii(header=headers,body=data)
            resp = '```\n' + resp + '\n```'
            chunks = [resp[i:i + 2000] for i in
                          range(0, len(resp), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.channel.send("Initialise by typing initialise first and register yourself in bot DMs")


async def select_group(ctx : discord.ext.commands.Context) -> Dict[str,Any] | None:
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    if us.user_exists():
        try:
            ns_db = load_mongo_db(user_id,CLIENT,nosync=True)
            groups = ns_db['user']['groups']
            headers = ['No','Group Name','Group Invite','Role']
            data = []
            index = 0
            if len(groups) == 0 :
                await ctx.channel.send("No groups exist\nFirst create a group using `#create_task_group`")
                return None
            for group in groups:
                data.append([str(index),group['group_name'],group['group_invite'],group['role']])
                index += 1
            resp = table2ascii(header=headers,body=data)
            resp = '```\n' + resp + '\n```'
            chunks = [resp[i:i + 2000] for i in
                          range(0, len(resp), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.send(chunk,delete_after=20)
            await ctx.send("Enter group number to select : ",delete_after=20)
            grp_no = await bot.wait_for('message', check = arr_bounds_checker(0,len(groups)-1),timeout=20)
            sel_id = groups[int(grp_no.content)]['group_id']
            sel_mdb = grp_db.find_one({"group_id": sel_id})
            if sel_mdb is None:
                await ctx.channel.send("Group not found")
            else:
                return sel_mdb
        except asyncio.TimeoutError:
            await ctx.send("Group selection timed out",delete_after=20)
    return None
@bot.command()
async def invite_member_to_group(ctx : discord.ext.commands.Context):
    """Invite a member to a group with default role [Member]"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id, CLIENT)
        if us.user_exists():
            try:
                grp_sel = await select_group(ctx)
                usr = None
                if grp_sel:
                    print(grp_sel)
                    for member in grp_sel['members']:
                        if member['user_id'] == user_id:
                            usr = member
                    if usr:
                        if usr['role'] in ['Moderator','Owner']:
                            await ctx.send("Enter member discord username",delete_after=20)
                            usr_name = await bot.wait_for('message',check = len_checker(2,32),timeout=20)
                            usr_name = usr_name.content
                            sel_grp = grp_db.find_one({"group_id":grp_sel['group_id']})
                            if usr_name not in sel_grp['invited_users']:
                                sel_grp['invited_users'].append(usr_name)
                            else:
                                await ctx.send("Member has already been invited",delete_after=20)
                                return
                            op = grp_db.update_one(
                                {"group_id":grp_sel['group_id']},  # Filter: groups with group id
                                {"$set": sel_grp},
                                )
                            if op.acknowledged:
                                await ctx.send("Member invited successfully",delete_after=20)
                            else:
                                await ctx.send("Member invite failed please try again later",delete_after=20)
                                return

                        else:
                            await ctx.send("Insufficient permissions to invite new member\nYou need to be Admin or Moderator to invite a member",delete_after=20)
                            return
                    else:
                        await ctx.send("Error fetching / You have been removed from the group ",delete_after=20)
                        return
                else:
                    await ctx.send("Error fetching selected group")
            except asyncio.TimeoutError:
                await ctx.send("Group invite operation timed out please try again later",delete_after=20)

async def member_selector(ctx : discord.ext.commands.Context,grp : Dict[str,Any]) -> Dict[str,Any] | None:
    """Allows user to select a member and returns member dict"""
    user_id = str(ctx.author.id)
    try:
        await ctx.send("Please select a member no from the list below : ", delete_after=20)
        member_sel = None
        if len(grp['members']) == 1:
            await ctx.send("Only you are there is the group",delete_after=20)
            return None
        member_disp = []
        headers = ['No','Member Name','Role']
        index = 0
        for member in grp['members']:
            member_disp.append([str(index),member['user_name'],member['role']])
            index += 1
        resp = "```\n" + table2ascii(header=headers,body=member_disp) + "\n```"
        chunks = [resp[i:i + 2000] for i in
                  range(0, len(resp), 2000)]  # Split into 2000 sized chunks
        for chunk in chunks:
            await ctx.send(chunk)
        member_sel = await bot.wait_for('message', check = arr_bounds_checker(0,len(grp['members'])-1),timeout=20)
        selected = grp['members'][int(member_sel.content)]
        if TskUser(selected['user_id'],CLIENT).user_exists():
            pass
        else:
            await ctx.send("Selected member has not initialised / Deleted his account",delete_after=20)
            return None
        return selected
    except asyncio.TimeoutError:
        await ctx.send("Member selection timed out",delete_after=20)
        return None


def role_validator(message : discord.Message) -> bool:
    """Validates role input"""
    ct = message.content.lower()
    ct = ct[0].upper() + ct[1:]
    if ct in ['Owner','Moderator','Member']:
        return True
    return False
@bot.command()
async def assign_role(ctx: discord.ext.commands.Context):
    """Assigns role to user"""
    if ctx.channel.type == discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id, CLIENT)
        if us.user_exists():
            try:
                grp_sel = await select_group(ctx)
                usr = None
                if grp_sel:
                    for member in grp_sel['members']:
                        if member['user_id'] == user_id:
                            usr = member

                    if usr:
                        if usr['role'] == 'Owner':
                            member_sel = await member_selector(ctx,grp_sel)
                            await ctx.send("Enter a role from (Owner,Moderator,Member)",delete_after=20)
                            role_sel = await bot.wait_for('message', check = role_validator,timeout=20)
                            for mem in grp_sel['members']:
                                if mem['user_id'] == member_sel['user_id']:
                                    mem['role'] = role_sel
                            op = grp_db.update_one(
                                {"group_id": grp_sel['group_id']},  # Filter: groups with group id
                                {"$set": grp_sel},
                            )
                            if op.acknowledged:
                                st_usr = bot.get_user(member_sel['user_id'])
                                embed = discord.Embed(
                                    title="Role Assignment",
                                    description=f"You have been assigned role {grp_sel['role']} by {ctx.author.name} in group {grp_sel['group_name']}",
                                    color=discord.Color.green(),
                                )
                                await ctx.send("!!!Alert!!!",embed=embed)
                                await ctx.send(f"Role {role_sel} successfully assigned to {member_sel['user_name']}",delete_after=20)
                                return
                            else:
                                await ctx.send("Error assigning role please try again later",delete_after=20)




                        else:
                            await ctx.send(
                                "Insufficient permissions to assign role to member\nYou need to be Admin or Moderator to invite a member",
                                delete_after=20)
                            return
                    else:
                        await ctx.send("Error fetching / You have been removed from the group ", delete_after=20)
                        return
                else:
                    await ctx.send("Error fetching selected group")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Assign role operation timed out please try again later", delete_after=20)
                return
@bot.command()
async def join_group(ctx: discord.ext.commands.Context):
    if ctx.channel.type == discord.ChannelType.private:
        try:
            user_id = str(ctx.author.id)
            us = TskUser(user_id, CLIENT)
            if us.user_exists():
                await ctx.send("Enter a valid group invite",delete_after=20)
                invite_name = await bot.wait_for('message', check = len_checker(6,15),timeout=20)
                invite_name = invite_name.content.lower()
                grp_sel = grp_db.find_one({"group_invite": invite_name})
                if grp_sel:
                    user_invited = False
                    for invitee in grp_sel['invited_users']:
                        if invitee == ctx.author.name:
                            user_invited = True
                    if user_invited:
                        for members in grp_sel['members']:
                            if members['user_name'] == ctx.author.name:
                                await ctx.send("You have already joined this group",delete_after=20)
                                return
                        grp_sel['invited_users'].remove(ctx.author.name)
                        grp_sel['members'].append({'user_name': ctx.author.name,'user_id': user_id,'role' : 'Member'})
                        op = grp_db.update_one(
                            {"group_id": grp_sel['group_id']},  # Filter: groups with group id
                            {"$set": grp_sel},
                        )
                        db_ns = load_mongo_db(user_id, CLIENT,nosync=True)
                        db_ns['user']['groups'].append({"group_id": grp_sel['group_id'],"group_name": grp_sel['group_name'],"role":"Member","group_invite":grp_sel["group_invite"]})
                        op1 = save_to_db(user_id, db_ns,CLIENT,nosync=True)
                        if op.acknowledged and op1:
                            await ctx.send(f"Successfully joined the group {grp_sel['group_name']}")
                        else:
                            await ctx.send("Error joining group please try again later",delete_after=20)
                    else:
                        #print(grp_sel['invited_users'])
                        #print(ctx.author.name)
                        await ctx.send("Sorry you were not invited to the group", delete_after=20)
                else:
                    await ctx.send("Group invite invalid",delete_after=20)

            else:
                await ctx.channel.send("Initialise by typing initialise first and register yourself in bot DMs")
        except asyncio.TimeoutError:
            await ctx.send("Operation timed out",delete_after=20)
        except Exception as e:
            await ctx.send("Something went wrong",delete_after=20)
            print(str(e))

# TODO: List group tasks , create group task , delete group task, toggle group task status
@bot.command()
async def assign_group_channel(ctx: discord.ext.commands.Context):
    if ctx.channel.type != discord.ChannelType.private:
        user_id = str(ctx.author.id)
        us = TskUser(user_id, CLIENT)
        if us.user_exists():
            try:
                grp_sel = await select_group(ctx)
                if grp_sel:
                    pass
                else:
                    await ctx.send("Operation cancelled",delete_after=20)
                    return
                usr = None
                for member in grp_sel['members']:
                    if member['user_id'] == user_id:
                        usr = member
                if usr:
                    if usr['role'] == 'Owner':
                        await ctx.send("Do you want to set this channel as group channel ? (yes/no)",delete_after=20)
                        response = await bot.wait_for('message', check = lambda message: True if message.content.lower() in ["yes","no"] else False,timeout=20)
                        if response.content.lower() == "yes":
                            channel_id = ctx.channel.id
                            grp_sel["group_channel_id"] = str(channel_id)
                            op = grp_db.update_one({"group_id": grp_sel['group_id']}, {"$set": grp_sel})
                            if op.acknowledged:
                                await ctx.send(f"Successfully set channel as group channel for group {grp_sel['group_name']}")
                                return
                            else:
                                await ctx.send("Error setting group channel please try again later", delete_after=20)
                                return
                        else:
                            await ctx.send("Operation cancelled", delete_after=20)
                            return
                    else:
                        await ctx.send("Sorry you do not have sufficient permissions to set group channel", delete_after=20)
            except asyncio.TimeoutError:
                await ctx.send("Operation timed out ",delete_after=20)



bot.run(TOKEN_DISCORD)