from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
import PythonModules.SQLiteHelper as SH
import discord
from discord.ext import commands, tasks
import os
import asyncio
from dotenv import load_dotenv
import logging

# Configure logging to suppress GET request errors
logging.basicConfig(level=logging.WARNING)

"""
This python script will require port 8000 to be open on your firewall.

Welcome to Nanoh's Ascended Equipment Companion Bot! 

This bot was created after multiple requests from server owners to allow for a way to have their own top ten in their 
discord servers. 

To get started, open the UserConfig.ini file under the config folder. You will want to fill out the following fields:

DISCORD_TOKEN= (This will be the token generated after creating the discord app)
DISCORD_GUILD= (This is your discord's ID)
DISCORD_CHANNEL= (This is the channel you would want the top ten being sent in)
DO_DAILY_TOP_TEN= (This is whether or not you want the daily top ten task to run)
SERVER_NAME= (Server name)

You can find a guide for creating a bot application for discord here:
https://discordjs.guide/preparations/setting-up-a-bot-application.html#creating-your-bot

You can find a guide for inviting the bot to your discord server here:
https://discordjs.guide/preparations/adding-your-bot-to-servers.html

After the bot is setup and invited to your server, populating the UserConfig.INI file with the token, guild, channel, daily top ten, and server name fields,
run the python script.
"""

load_dotenv("Config/UserConfig.ini")
TOKEN = str(os.getenv('DISCORD_TOKEN'))
DB_FILE = 'Config/tableconfig.ini'
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL'))
DO_DAILY_TOP_TEN = bool(os.getenv('DO_DAILY_TOP_TEN'))
SERVER_NAME = str(os.getenv('SERVER_NAME'))
LEADER_UPDATE = int(os.getenv('UPDATE_TIME'))

intents = discord.Intents.default()
intents.messages = True
intents.guild_messages = True
intents.message_content = True
intents.webhooks = True
intents.guilds = True
intents.typing = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)
app = FastAPI()

db = SH.SQLiteHelper(DB_FILE, 'NAE')


class ItemDropEvent(BaseModel):
    server_name: str
    user_id: str
    character_name: str
    item_dropped: str
    chance: str
    dropped_by_dino: str
    server_max_level: str
    had_4_leaf_clover: str
    server_drop_chance: str
    suid: str


class CheckSuccess(BaseModel):
    success: str


@app.middleware("http")
async def ignore_get_requests(request: Request, call_next):
    if request.method == "GET":
        client_ip = request.client.host
        if 'X-Forwarded-For' in request.headers:
            client_ip = request.headers['X-Forwarded-For'].split(",")[0].strip()
        logging.warning(f"Ignored GET request from IP: {client_ip}")
    return await call_next(request)


@app.post("/checksuccess/")
async def check_success(event: CheckSuccess):
    print('Success!!')


@app.post("/item-drop-events/")
async def create_item_drop_event(event: ItemDropEvent):
    """On POST request from Nanoh's ascended equipment mod, gather drop info, insert into db"""

    event_dict = event.dict()

    def insert_item_drop(info_dict):
        db.insert_data(query_columns=['server_name', 'user_id', 'character_name', 'item_dropped',
                                      'chance', 'dropped_by_dino', 'server_max_level',
                                      'had_4_leaf_clover', 'server_drop_chance', 'suid'],
                       query_values=[info_dict['server_name'], info_dict['user_id'], info_dict['character_name'],
                                     info_dict['item_dropped'], info_dict['chance'], info_dict['dropped_by_dino'],
                                     info_dict['server_max_level'], info_dict['had_4_leaf_clover'], info_dict['server_drop_chance'],
                                     info_dict['suid']])

    if all(x for x in event_dict.values()):
        insert_item_drop(event_dict)
    else:
        print(f'Failed to insert: {event_dict}')


async def send_discord_message(message):
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f'{message}')
    else:
        print("Channel not found")


@bot.event
async def on_ready():
    """On Async.io starting the discord bot."""
    print(f'{bot.user.name} has connected to Discord!')
    if not send_daily_message.is_running():
        send_daily_message.start()


@app.on_event("startup")
def startup_event():
    """On Async.io start, start discord bot"""
    asyncio.create_task(bot.start(TOKEN))


@bot.command(name='getitemdrops', help='Get your total number of item drops!')
async def get_item_drops(ctx, user_id: str):
    """Get item drops for user. Takes a user's character id, which can be retrieved from the item in game."""

    user_data = db.select_data('*', f'user_id = {user_id}')
    if user_data:
        response = (
            f'{user_data[0]["character_name"]} has obtained {len(user_data)} drops on {user_data[0]["server_name"]}')
        await ctx.send(response)
    else:
        response = "No data found for the user."
        response += "\n"
        await ctx.send(response)


@bot.command(name='getservertopten', help='Get your servers total number of item drops!')
async def get_server_top_ten(ctx):
    """Manual bot command for getting server top ten"""

    user_data = db.select_data("user_id, character_name, COUNT(*) as drop_count",
                               f"server_name LIKE '%{SERVER_NAME}%' GROUP BY user_id, character_name;")
    try:
        response = ""
        response += f"Top 10 Leaderboard for {SERVER_NAME}:\n"
        response += f'Rank | Player Name | Number of Drops\n\n'
        top_10_drops = sorted(user_data, key=lambda x: x['drop_count'], reverse=True)[:10]
        for line in enumerate(top_10_drops, 0):
            response += f'**#{line[0] + 1}** - {line[1]["character_name"]}: {line[1]["drop_count"]} drops\n'
        await ctx.send(response)
    except Exception as e:
        response = f"Unable to find data for: {SERVER_NAME}"
        await ctx.send(response)


@tasks.loop(hours=LEADER_UPDATE)
async def send_daily_message():
    """Send daily server top ten message. Requires CHANNEL_ID field in UserConfig to be filled out."""

    if DO_DAILY_TOP_TEN:
        channel = bot.get_channel(CHANNEL_ID)
        user_data = db.select_data("user_id, character_name, COUNT(*) as drop_count",
                                   f"server_name LIKE '%{SERVER_NAME}%' GROUP BY user_id, character_name;")
        try:
            response = ""
            response += f"Top 10 Leaderboard for {SERVER_NAME}:\n"
            response += f'Rank | Player Name | Number of Drops\n\n'
            top_10_drops = sorted(user_data, key=lambda x: x['drop_count'], reverse=True)[:10]
            for line in enumerate(top_10_drops, 0):
                response += f'**#{line[0] + 1}** - {line[1]["character_name"]}: {line[1]["drop_count"]} drops\n'
            await channel.purge(limit=10)
            await channel.send(response)
        except Exception as e:
            response = f"Unable to find data for: {SERVER_NAME}"
            await channel.send(response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
