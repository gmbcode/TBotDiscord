import asyncio
from typing import Tuple, Callable, Dict, Any
import discord
from dotenv import dotenv_values
from discord.ext import commands
from User import User as TskUser
from datetime import datetime, date, timedelta
from table2ascii import table2ascii
from discord.ext.commands import Context, errors
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
auth_db = CLIENT.clt['TBot_DB']['auth']
grp_tasks_db = CLIENT.clt['TBot_DB']['group_tasks']
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
                del sel_mdb['_id']
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
            await ctx.send(chunk,delete_after=20)
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
                        if not member_sel:
                            pass
                        await ctx.send("Enter a role from (Owner,Moderator,Member)",delete_after=20)
                        role_sel = await bot.wait_for('message', check = role_validator,timeout=20)
                        for mem in grp_sel['members']:
                            if mem['user_id'] == member_sel['user_id']:
                                mem['role'] = role_sel.content
                        op = grp_db.update_one(
                            {"group_id": grp_sel['group_id']},  # Filter: groups with group id
                            {"$set": grp_sel},
                        )
                        ns_db = load_mongo_db(member_sel['user_id'],CLIENT,nosync=True)
                        for g in ns_db['user']['groups']:
                            if g['group_id'] == grp_sel['group_id']:
                                g['role'] = role_sel.content
                        print(ns_db)
                        op2 = save_to_db(member_sel['user_id'],ns_db,CLIENT,nosync=True)
                        if op.acknowledged and op2:
                            st_usr = bot.get_user(member_sel['user_id'])
                            usr = await bot.fetch_user(member_sel['user_id'])
                            embed = discord.Embed(
                                title="Role Assignment",
                                description=f"You have been assigned role {role_sel.content} by {ctx.author.name} in group {grp_sel['group_name']}",
                                color=discord.Color.green(),
                            )
                            await usr.send("!!!Alert!!!",embed=embed)
                            await ctx.send(f"Role {role_sel.content} successfully assigned to {member_sel['user_name']}",delete_after=20)
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
                            if grp_sel['group_channel_id'] != 'not_set':
                                g_channel = await bot.fetch_channel(int(grp_sel['group_channel_id']))
                                await g_channel.send(
                                    f"User {ctx.author.name} has joined the group {grp_sel['group_name']}")
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

# TODO: delete group task,
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

def get_user_role(user_id : str,group_id : str) -> str | None:
    grp_sel = grp_db.find_one({"group_id": group_id})
    if grp_sel:
        members_list = grp_sel['members']
        for member in members_list:
            if member['user_id'] == user_id:
                return member['role']
        return None
    else:
        return None

def check_if_other_owner(user_id : str,group_id : str) -> bool:
    grp_sel = grp_db.find_one({"group_id": group_id})
    other_owners_available = False
    members_list = grp_sel['members']
    for member in members_list:
        if member['user_id'] != user_id and member['role'] == 'Owner':
            other_owners_available = True
    return other_owners_available

@bot.command()
async def leave_group(ctx: discord.ext.commands.Context):
    user_id = str(ctx.author.id)
    grp_sel = await select_group(ctx)
    usr_role = get_user_role(user_id,grp_sel['group_id'])
    if usr_role == "Owner":
        other_owners_available = check_if_other_owner(user_id,grp_sel['group_id'])
        if other_owners_available:
            db_ns = load_mongo_db(user_id,CLIENT,nosync=True)
            db_ns['groups'] = [group for group in db_ns['groups'] if group['group_id'] != grp_sel['group_id']]
            members_list = grp_sel['members']
            members_list = [member for member in members_list if member['user_id'] != user_id]
            grp_sel['members'] = members_list
            op = grp_db.update_one({"group_id": grp_sel['group_id']}, {"$set": grp_sel})
            if op.acknowledged:
                if grp_sel['group_channel_id'] != 'not_set':
                    g_channel = await bot.fetch_channel(int(grp_sel['group_channel_id']))
                    await g_channel.send(f"User {ctx.author.name} has left the group {grp_sel['group_name']}")
                await ctx.send(f"Successfully left the group {grp_sel['group_name']}")
            else:
                await ctx.send("Error leaving the group", delete_after=20)
        else:
            await ctx.send("You cannot leave the group until it has more than one admin", delete_after=20)
    else:
        db_ns = load_mongo_db(user_id, CLIENT, nosync=True)
        db_ns['user']['groups'] = [group for group in db_ns['user']['groups'] if group['group_id'] != grp_sel['group_id']]
        members_list = grp_sel['members']
        save_to_db(user_id,db_ns,CLIENT)
        members_list = [member for member in members_list if member['user_id'] != user_id]
        grp_sel['members'] = members_list
        op = grp_db.update_one({"group_id": grp_sel['group_id']}, {"$set": grp_sel})
        if op.acknowledged:
            if grp_sel['group_channel_id'] != 'not_set':
                g_channel = await bot.fetch_channel(int(grp_sel['group_channel_id']))
                await g_channel.send(f"User {ctx.author.name} has left the group {grp_sel['group_name']}")
            await ctx.send(f"Successfully left the group {grp_sel['group_name']}")
        else:
            await ctx.send("Error leaving the group", delete_after=20)
@bot.command()
async def create_group_task(ctx: discord.ext.commands.Context):
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    try:
        if us.user_exists():
            grp_sel = await select_group(ctx)
            if not grp_sel:
                await ctx.send("Group task creation failed / timed out", delete_after=20)
                return
            if grp_sel['group_channel_id'] == 'not_set':
                await ctx.send("Please set group channel first using `#assign_group_channel` and try again later", delete_after=20)
                return
            usr_role = get_user_role(user_id,grp_sel['group_id'])
            if usr_role in ['Owner','Moderator']:
                pass
            else:
                await ctx.send("You need to be Owner / Moderator in a group to create tasks", delete_after=20)
                return
            await ctx.send("Enter task title (between 2 and 32 characters ) : ", delete_after=20)
            title = await bot.wait_for('message', check = len_checker(2,32), timeout=20)
            title = title.content
            await ctx.send("Enter task notes (between 2 and 32 characters ) : ", delete_after=20)
            notes = await bot.wait_for('message', check=len_checker(2, 32), timeout=20)
            notes = notes.content
            auth = CLIENT.clt['TBot_DB']['auth']
            usr = auth.find_one({"user.user_id": user_id})
            if usr is not None:
                del usr['_id']
            usr_timezone = usr['user']['timezone']
            if usr_timezone == 'not_set':
                await ctx.channel.send(f"You need to set a timezone first using `#set_timezone` command",
                                       delete_after=15)
                return
            await ctx.channel.send("Enter valid due date in YYYY-MM-DD format : ", delete_after=40)

            def date_validator(message: discord.Message) -> bool:
                dt = message.content
                try:
                    now = datetime.now()
                    now = tz(usr_timezone).localize(now)
                    cd = now.date()  # Get current date in user's timezone
                    dt = date.fromisoformat(dt)
                    if dt >= cd:
                        return True
                    return False
                except ValueError:
                    return False

            date_sel = await bot.wait_for('message', timeout=40.0, check=date_validator)
            date_sel = date_sel.content
            await ctx.channel.send("Enter valid due time in HH-MM (24 hour format) \n Example : `16:30`", delete_after=40)

            def time_validator(message: discord.Message) -> bool:
                time_sel = message.content
                tm = date_sel + " " + time_sel + ":00"
                try:
                    tm = iso_localizer(tm, usr_timezone)
                    now = datetime.now()
                    now = tz(local_tz).localize(now)
                    now = now.astimezone(tz('UTC'))
                    if tm >= now:
                        return True
                    return False
                except ValueError:
                    return False

            time_sel = await bot.wait_for('message', timeout=25.0, check=time_validator)
            mem_list = grp_sel['members']
            mem_id_lst = []
            r_list = []
            hdrs = ['No','Member Name']
            index = 0
            for member in mem_list:
                r_list.append([str(index),member['user_name']])
                mem_id_lst.append(member['user_id'])
                index += 1
            resp = "```\n" + table2ascii(header=hdrs,body=r_list) + "\n```"
            chunks = [resp[i:i + 2000] for i in
                      range(0, len(resp), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.send(chunk,delete_after=35)
            await ctx.send("Enter space seperated member numbers to assign the task to : ",delete_after=35)
            mem_nos = await bot.wait_for('message', check = len_checker(1,32), timeout=20)
            mem_nos = mem_nos.content
            m_indices = mem_nos.split()
            for entry in m_indices:
                try:
                    index = int(entry)
                    if 0 <= index < len(mem_id_lst):
                        pass
                    else:
                        await ctx.channel.send(f"Invalid input please try again", delete_after=20)
                        return
                except ValueError:
                    await ctx.channel.send(f"Invalid input please try again", delete_after=20)
                    return
            time_sel = time_sel.content
            date_time = date_sel + " " + time_sel + ":00"
            obj = iso_localizer(date_time, usr_timezone)
            task_id = "".join(str(uuid4()).split('-'))
            assigned_ids = []
            for member in m_indices:
                assigned_ids.append(mem_id_lst[int(member)])
            group_task = {
                "group_id" : grp_sel['group_id'],
                "group_task_id": task_id,
                "task_title": title,
                "notes" : notes,
                "assigned_to" : assigned_ids,
                "due" : obj,
                "status" : "needsAction",
                "priority" : "not_set",
                "group_channel_id" : grp_sel['group_channel_id'],
            }
            op = grp_tasks_db.insert_one(group_task)
            if op.acknowledged:
                await ctx.channel.send(f"Group task {title} successfully created", delete_after=20)
            else:
                await ctx.channel.send(f"Group task {title} creation failed please try again later", delete_after=20)
                return
        else:
            await ctx.send("First initialise by typing initialise in bot DMs", delete_after=20)
    except asyncio.TimeoutError:
        await ctx.send("Operation timed out",delete_after=20)
    except Exception as e:
        await ctx.send("Something went wrong",delete_after=20)
        print(str(e))

@bot.command()
async def list_group_tasks(ctx : discord.ext.commands.Context):
    """List a user's group tasks"""
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    try:
        if us.user_exists():
            grp_sel = await select_group(ctx)
            if not grp_sel:
                await ctx.send("Group task creation failed / timed out", delete_after=20)
                return
            usr_timezone = auth_db.find_one({"user.user_id" : user_id})["user"]["timezone"]
            if usr_timezone == "not_set":
                await ctx.channel.send(f"You need to set a timezone first using `#set_timezone` command",
                                       delete_after=15)
                return

            g_tasks = list(grp_tasks_db.find({"group_id": grp_sel['group_id']}))
            if not g_tasks:
                await ctx.send("No group tasks exist\nFirst create a task using `#create_group_task`",
                               delete_after=20)
                return
            print(g_tasks)
            g_tasks = [g_task for g_task in g_tasks if user_id in g_task["assigned_to"]]
            if len(g_tasks) == 0:
                await ctx.send("No group tasks exist assigned to you \nFirst create a task using `#create_group_task`", delete_after=20)
                return
            hdrs = ['Group Task Name','Due Date','Due Time','Priority','Status']
            index = 0
            task_list = []

            for g_task in g_tasks:
                tm = g_task['due']
                tm = tz('utc').localize(tm)
                tm = tm.astimezone(tz(usr_timezone))
                rem_date = tm.date().strftime("%B %d, %Y")
                rem_time = str(tm.time())
                task_list.append([g_task['task_title'],rem_date,rem_time,g_task['priority'],status_converter(g_task['status'])])
            resp = '```\n' + table2ascii(header=hdrs,body=task_list) + "\n```"
            chunks = [resp[i:i + 2000] for i in
                      range(0, len(resp), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.send(chunk)

        else:
            await ctx.send("First initialise by typing initialise in bot DMs", delete_after=20)
            return
    except asyncio.TimeoutError:
        await ctx.send("Operation timed out",delete_after=20)
        return


async def select_group_task(ctx : discord.ext.commands.Context,group_id : str) -> Dict[str, Any]:
    """Group Task Selection helper function"""
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    try:
        if us.user_exists():
            grp_sel = grp_db.find_one({"group_id": group_id})
            if not grp_sel:
                await ctx.send("Group task selection failed / timed out", delete_after=20)
                return
            usr_timezone = auth_db.find_one({"user.user_id" : user_id})["user"]["timezone"]
            if usr_timezone == "not_set":
                await ctx.channel.send(f"You need to set a timezone first using `#set_timezone` command",
                                       delete_after=15)
                return

            g_tasks = list(grp_tasks_db.find({"group_id": grp_sel['group_id']}))
            if not g_tasks:
                await ctx.send("No group tasks exist\nFirst create a task using `#create_group_task`",
                               delete_after=20)
                return

            hdrs = ['No','Group Task Name','Due Date','Due Time','Priority','Status']
            index = 0
            task_list = []
            col = []
            index = 0
            for g_task in g_tasks:
                tm = g_task['due']
                tm = tz('utc').localize(tm)
                tm = tm.astimezone(tz(usr_timezone))
                rem_date = tm.date().strftime("%B %d, %Y")
                rem_time = str(tm.time())
                col.append(g_task)
                task_list.append([index,g_task['task_title'],rem_date,rem_time,g_task['priority'],status_converter(g_task['status'])])
                index += 1
            resp = '```\n' + table2ascii(header=hdrs,body=task_list) + "\n```"
            chunks = [resp[i:i + 2000] for i in
                      range(0, len(resp), 2000)]  # Split into 2000 sized chunks
            for chunk in chunks:
                await ctx.send(chunk,delete_after=25)
            selection = await bot.wait_for('message',check = arr_bounds_checker(0,len(task_list)-1))
            gt = col[int(selection.content)]
            del gt['_id']
            return gt

        else:
            await ctx.send("First initialise by typing initialise in bot DMs", delete_after=20)
            return
    except asyncio.TimeoutError:
        await ctx.send("Operation timed out",delete_after=20)
        return

@bot.command()
async def toggle_group_task(ctx : discord.ext.commands.Context):
    """Allow user to toggle group task status"""
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    try:
        if us.user_exists():
            grp_sel = await select_group(ctx)
            if grp_sel:
                pass
            else:
                await ctx.send("Group selection failed / timed out", delete_after=20)
                return
            grp_channel = await bot.fetch_channel(int(grp_sel['group_channel_id']))
            grp_task_sel = await select_group_task(ctx,grp_sel['group_id'])
            if not grp_task_sel:
                await ctx.send("Group task selection failed / timed out", delete_after=20)
            if grp_task_sel['status'] == 'needsAction':
                grp_task_sel['status'] = 'completed'
            else:
                grp_task_sel['status'] = 'needsAction'
            op = grp_tasks_db.update_one(
                {"group_id": grp_sel['group_id'],"group_task_id": grp_task_sel['group_task_id']},
                {"$set": grp_task_sel}
            )
            if op.acknowledged:
                await ctx.send("Group task status successfully toggled", delete_after=20)
                embed = discord.Embed(title="Group Task Status Toggled",
                                      description=f"{ctx.author.name} has toggled group task {grp_task_sel['task_title']} to {status_converter(grp_task_sel['status'])}",
                                      color=discord.Color.green()
                                      )
                await grp_channel.send(embed=embed)
            else:
                await ctx.send(" Error operation failed", delete_after=20)
                return

    except asyncio.TimeoutError:
        await ctx.send("Operation timed out",delete_after=20)
    except Exception as e:
        print(str(e))
        await ctx.send("Something went wrong", delete_after=20)

@bot.command()
async def delete_group_task(ctx : discord.ext.commands.Context):
    """Allow user to toggle group task status"""
    user_id = str(ctx.author.id)
    us = TskUser(user_id, CLIENT)
    try:
        if us.user_exists():
            grp_sel = await select_group(ctx)
            if grp_sel:
                pass
            else:
                await ctx.send("Group selection failed / timed out", delete_after=20)
                return
            usr_role = get_user_role(user_id,grp_sel['group_id'])
            if usr_role not in ['Moderator','Owner']:
                await ctx.send("User must be Moderator or Owner to delete tasks", delete_after=20)
                return

            grp_channel = await bot.fetch_channel(int(grp_sel['group_channel_id']))
            grp_task_sel = await select_group_task(ctx,grp_sel['group_id'])
            if not grp_task_sel:
                await ctx.send("Group task selection failed / timed out", delete_after=20)
            op = grp_tasks_db.delete_one(
                {"group_id": grp_sel['group_id'],"group_task_id": grp_task_sel['group_task_id']})
            if op.acknowledged:
                await ctx.send("Group task successfully deleted", delete_after=20)
                embed = discord.Embed(title="Group Task deleted",
                                      description=f"{ctx.author.name} has deleted group task {grp_task_sel['task_title']}",
                                      color=discord.Color.green()
                                      )
                await grp_channel.send(embed=embed)
            else:
                await ctx.send(" Error operation failed", delete_after=20)
                return

    except asyncio.TimeoutError:
        await ctx.send("Operation timed out",delete_after=20)
    except Exception as e:
        print(str(e))
        await ctx.send("Something went wrong", delete_after=20)

async def on_command_error(self, ctx : discord.ext.commands.Context,exception: errors.CommandError) -> None:
    if isinstance(exception, commands.CommandNotFound):
        pass
    else:
        print(str(exception))
bot.run(TOKEN_DISCORD)