# TBot

A comprehensive Discord bot that integrates with Google Tasks to provide task management capabilities directly from Discord. The bot offers full synchronization with Google Tasks, reminder systems, and advanced task organization features.

## Features

### Core Task Management
- **Full Google Tasks Integration**: Complete synchronization with your Google Tasks account
- **Task CRUD Operations**: Create, read, update, and delete tasks seamlessly with google tasks sync
- **Task Status Toggle**: Mark tasks as complete/incomplete with a single command
- **Task Reminders**: Create custom task reminders
- **Due Date Management**: Set and modify task due dates with validation
- **Task Lists Management**: Create and manage multiple task lists.
### Advanced Organization
- **Custom Categories**: Create and assign custom categories to tasks for better organization
- **Priority System**: Assign priority levels (Low, Medium, High) to tasks
- **Task View**: View tasks by various criteria including category and priority
- **Gen AI based queries** : Type `query ` followed by your query in natural language 
- Note : Currently only task creation and a few more queries are supported in natural language
### Reminder System
- **One-time Reminders**: Set individual reminders for specific tasks
- **Recurring Reminders**: Create repeating reminders with customizable intervals (1-30 days)
- **Synced Recurring Tasks**: Create recurring reminders that sync with Google tasks and track task completion
- **Timezone Support**: Full timezone awareness for accurate reminder scheduling 

### Group Management
- **Task Groups**: Create and manage task groups for collaborative work
- **Group Commands**: Dedicated command processor for group-specific operations

## Prerequisites

Before setting up the bot, you'll need:

1. Python 3.8 or higher
2. A Google Cloud Platform account
3. A Discord Developer account
4. MongoDB database (local or cloud)

## Installation & Setup

### 1. Google API Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Tasks API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Tasks API" and enable it
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Choose "Web application" as the application type
   - Add authorized redirect URIs (your auth server URL) which is http://localhost:8080 
   - Note : If unable to add localhost as redirect URI first add another random valid domain before adding localhost.
   - Set the necessary environment variables in .env ( Use .env.example as a reference )
   - Note you need the following scopes enabled in OAuth 
   - `openid` , `email` , `profile` and `https://www.googleapis.com/auth/tasks`
### 2. Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Navigate to the "Bot" section
4. Click "Add Bot"
5. Copy the bot token (you'll need this for the `.env` file)
6. Enable necessary intents:
   - Message Content Intent
   - Server Members Intent (if using group features)

### 3. Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# Discord Bot Token
DISCORD_BOT_TOKEN = <your_discord_bot_token>

# Google OAuth Credentials
GOOGLE_CLIENT_ID = <your_google_client_id>
GOOGLE_CLIENT_SECRET = <your_google_client_secret>

# MongoDB Configuration
MONGO_DB_CLUSTER_URL = <your_mongo_db_cluster_url>
MONGO_DB_ADMIN_USERNAME = "<your_mongo_db_admin_username>" 
MONGO_DB_ADMIN_PASSWORD = "<your_mongo_db_admin_password>"

# Generative AI Config
GEMINI_API_KEY = "<your_gemini_api_key>"

# Timezone Configuration ( Local timezone of server )
LOCAL_TZ = "<your_local_timezone>"
```

### 4. Dependencies Installation

Install the required Python packages ( preferably in a fresh virtual environment ) :

```bash
pip install discord.py
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
pip install pymongo
pip install python-dotenv
pip install table2ascii
pip install pytz
pip install asyncio
```
### 5. Mongo DB Structure 
Create a database called as `TBot_DB` with the following collections : 
- `auth` for storing user refresh tokens and OAuth credentials
- `tasks` for storing a synced version of users google tasks
- `tasks_ns` for storing category and priority information
- `reminders` for storing user reminders
- `groups` for storing user groups
- `group_tasks` for storing user group tasks
### 6. Project Structure

Ensure your project has the following structure:
```
discord-task-bot/
├── main.py
├── Reminder_Bot.py
├── Auth_Server.py
├── Group_Commands_Processor.py
├── Group_Bot.py
├── User.py
├── Tasks.py
├── User_Tasks.py
├── Misc_Methods.py
├── Mongo_Access.py
├── .env
└── README.md
```

## Running the Bot

The bot requires multiple components to run simultaneously. Start each in a separate terminal:

### 1. Authentication Server
```bash
python Auth_Server.py
```

### 2. Main Discord Bot
```bash
python main.py
```

### 3. Reminder System
```bash
python Reminder_Bot.py
```

### 4. Group Commands Processor
```bash
python Group_Commands_Processor.py
```

### 5. Group Task Alerts System
```bash
python Group_Bot.py
```
## Usage

### Initial Setup

1. Send a DM to the bot with the message `initialise`
2. Click the provided Google OAuth link to authorize the bot
3. Complete the authorization within 60 seconds

### Basic Commands

All commands are prefixed with `#` and must be sent as direct messages to the bot:

#### Task Management
- `#list_tasks` - Display all your tasks
- `#create_task` - Create a new task
- `#modify_task` - Edit an existing task
- `#delete_task` - Remove a task
- `#toggle_task` - Mark task as complete/incomplete

#### Task Lists
- `#list_tasklists` - Show all your task lists
- `#create_tasklist` - Create a new task list

#### Organization
- `#list_category` - View all categories
- `#create_category` - Create a new category
- `#assign_category` - Assign a category to a task
- `#assign_priority` - Set task priority (low/medium/high)

#### Reminders
- `#create_reminder` - Set up task reminders
- `#list_reminders` - View all active reminders
#### Group System
- `#create_task_group` - Create a task group enabling group task support
- `#join_group` - Join task group
- `#assign_group_channel` Assign channel to a group
- `#create_group_task` - Create group task
- `#list_group_task` - Lists all group tasks
- `#toggle_group_task` - Toggle group task completion status
- `#delete_group_task` - Delete group task
- `#list_groups` - List all user groups
- `#invite_member_to_group` - Invite member to group
- `#assign_role` - Assign role to group member
- `#leave_group` - Leave the group

Note : Only users with role Moderator and Above can create tasks as well as assign tasks to other users.
#### Settings
- `#set_timezone` - Configure your timezone for accurate reminders

### Task Creation Format

When creating or modifying tasks, use this format:
```
Task Name Due Date(YYYY-MM-DD) Notes(if any)
Example: Complete project report 2025-06-15 Final version with all sections
```

### Reminder Features

- **One-time Reminders**: Get notified once at a specific date and time
- **Recurring Reminders**: Repeat every 1-30 days
- **Synced Reminders**: Automatically update task due dates and reset completion status

## Advanced Features

### Recurring Task Automation
- Create reminders that sync with task due dates  ( essentially regenerating tasks )
- Automatically reset task completion status on each recurrence
- Perfect for daily, weekly, or monthly recurring tasks

### Timezone Management
- Set your local timezone for accurate reminder scheduling
- All reminders are displayed in your configured timezone
- Supports all standard timezone formats (e.g., `Asia/Kolkata`, `America/New_York`) listed in `pytz -> common_timezones`

### Task Categories and Priorities
- Organize tasks with custom categories
- Set priorities to focus on important tasks

## Troubleshooting

### Common Issues

1. **Bot not responding**: Ensure all four components are running
2. **Google Tasks sync issues**: Check your OAuth credentials and API enablement
3. **Reminder not working**: Verify timezone settings and ensure Reminder_Bot.py is running
4. **Database errors**: Confirm MongoDB is running and accessible

### Error Messages

- `"Initialise by typing initialise first"`: You need to complete the Google OAuth setup
- `"Error fetching user tasks"`: Check Google API credentials and network connection
- `"Time elapsed please try again later"`: Command timeout - retry the operation

## Support

For additional support or to report issues:
1. Check that all prerequisites are properly installed
2. Verify all environment variables are correctly set
3. Ensure all four Python scripts are running simultaneously
4. Check MongoDB connectivity and Google API credentials

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- Regularly change your Discord bot token and Google OAuth credentials
- Use secure MongoDB configurations in production environments
- Consider using application-specific passwords for enhanced security

---

**Note**: This bot requires continuous internet connectivity for Google Tasks synchronization and Discord API communication. Reminders should be created at least 30 minutes before the due time to ensure proper delivery.

## Optimizations and Key Decisions / Improvements needed
- The reminder bot utilises a priority queue for efficient and scalable reminder alerts
- I did try testing the bot with async MongoDB clients but it did not yield noticeable performance improvements
- The codebase relied on json files earlier prior to the migration to MongoDB which made it very inefficient as all users files needed to be loaded for each query
- Appropriate MongoDB indexes were set up for unique fields commonly accessed to speed up query times
- The overall user experience relies a bit heavily on typing as opposed to discord interactions due to time constraints and realising it a lot later down the project