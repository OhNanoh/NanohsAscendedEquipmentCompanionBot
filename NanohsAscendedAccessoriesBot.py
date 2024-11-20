from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
import PythonModules.SQLiteHelper as SH
import discord
from discord.ext import commands, tasks
import os
import asyncio
from dotenv import load_dotenv
import logging
from mcrcon import MCRcon
from enum import Enum


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

Command usage:
/rconcommand saveworld - Performs a worldsave
/broadcastcolor {g}Test{/} {r}text{/} - Broadcasts a message that says "Test text" with Test being in green, and text being in red.
/setupnametoeosandplayer Nanoh *EOSID* *PLAYERID* - sets up player with eos id and player id in db
/giveitemtoplayer Nanoh '*itemblueprintpath*' *Quantity* *Quality* *is_bp* - Itemblueprint is the item blueprint path, Quantity is the amount, quality is the quality, is_bp is a 0 for no, 1 for yes
"""

load_dotenv("Config/UserConfig.ini")
TOKEN = str(os.getenv('DISCORD_TOKEN'))
DB_FILE = 'Config/tableconfig.ini'
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL'))
DO_DAILY_TOP_TEN = bool(os.getenv('DO_DAILY_TOP_TEN'))
SERVER_NAME = str(os.getenv('SERVER_NAME'))
LEADER_UPDATE = int(os.getenv('UPDATE_TIME'))
HOST = os.getenv('RCON_IP')
RCON_PORT = int(os.getenv('RCON_PORT'))
RCON_PASS = os.getenv('RCON_PASS')

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
namedb = SH.SQLiteHelper(DB_FILE, 'NameToEOS')


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


def get_eos_from_name(name_in):
    eos = namedb.select_data('eos', selection_where=f"NAME = '{name_in}'")
    return eos[0]['eos']

def get_playerid_from_name(name_in):
    eos = namedb.select_data('playerid', selection_where=f"NAME = '{name_in}'")
    return eos[0]['playerid']

def format_rich_text(input_text):
    color_map = {
        "{g}": '<RichColor Color="0, 1, 0, 1">',
        "{r}": '<RichColor Color="1, 0, 0, 1">',
        "{b}": '<RichColor Color="0, 0, 1, 1">',
        "{y}": '<RichColor Color="1, 1, 0, 1">',
        "{c}": '<RichColor Color="0, 1, 1, 1">',
        "{p}": '<RichColor Color="0.6, 0, 0.8, 1">',
        "{o}": '<RichColor Color="1, 0.5, 0, 1">',
        "{/}": '</>',
    }

    for placeholder, tag in color_map.items():
        input_text = input_text.replace(placeholder, tag)
    return input_text


def execute_rcon(command):
    """Execute an RCON command against your server. Requires RCON_IP, RCON_PORT, and RCON_PASS setup in the UserConfig.ini file"""
    try:
        with MCRcon(HOST, RCON_PASS, port=RCON_PORT) as mcr:
            response = mcr.command(command)
            return f"Server Response to '{command}': \n\n{response}"
    except Exception as e:
        return f"Failed to connect or run command: {e}"

def execute_color_broadcast(command):
    formatted_text = format_rich_text(command)
    with MCRcon(HOST, RCON_PASS, port=RCON_PORT) as mcr:
        response = mcr.command(formatted_text)

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


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.command(name='rconcommand', help='Executes an rcon command')
async def bot_rcon(ctx, *rcon_command):
    try:
        await ctx.send(f"Executing rcon command...")
        result = execute_rcon(' '.join(rcon_command))
        await ctx.send(result)

    except Exception as e:
        await ctx.send(f'Failed to execute rcon command: {e}')


@bot.command(name='broadcastcolor', help='Broadcasts a message with color formatting.')
async def broadcast_color(ctx, *, rcon_command):
    try:
        await ctx.send("Executing colored broadcast...")
        formatted_text = format_rich_text(rcon_command)
        result = execute_rcon(f'broadcast {formatted_text}')
        await ctx.send(f"RCON Response: {result}")
    except Exception as e:
        await ctx.send(f"Failed to execute colored broadcast: {e}")


@bot.command(name='setupnametoeosandplayer', help='Broadcasts a message with color formatting.')
async def setup_eos_name(ctx, name, eos, playerid):
    try:
        await ctx.send(f'Setting up {name} with EOS ID as {eos} and player id as {playerid}')
        result = namedb.insert_data(['name', 'eos', 'playerid'], [name, eos, playerid])
        await ctx.send(f'Finished: {result}')

    except Exception as e:
        await ctx.send(f'Failed to associate {name} with {eos}: {e}')


@bot.command(name='geteos', help='Broadcasts a message with color formatting.')
async def setup_eos_name(ctx, name):
    try:
        await ctx.send(f'Getting eos for {name}')
        eos = get_eos_from_name(name)
        await ctx.send(f'Eos for {name} is {eos}')
    except Exception as e:
        await ctx.send(f'Failed to get eos for {name}: {e}')

@bot.command(name='givetoplayer', help='Broadcasts a message with color formatting.')
async def gfi_give(ctx, playername, item, amount=1, quality=1, is_bp=0):
    try:
        await ctx.send(f'Attempting to give {playername} {amount} {item}.')
        playerid = get_playerid_from_name(playername)
        result = execute_rcon(f'GiveItemToPlayer {playerid} "Blueprint{item}" {amount} {quality} {is_bp}')
        await ctx.send(f"{result}")

    except Exception as e:
        await ctx.send(f'Failed to give {item} to {playername}. Error: {e}')


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
