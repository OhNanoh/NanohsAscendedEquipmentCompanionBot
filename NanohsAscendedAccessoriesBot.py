from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
import PythonModules.SQLiteHelper as SH
import discord
from discord import Embed, Color
from discord.ext import commands, tasks
import os
import asyncio
from dotenv import load_dotenv
import logging
from mcrcon import MCRcon
from datetime import datetime
import json

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
SERVER_NAME= (Server common name, for example, if all your servers have "ArkServer" in them, put that here. This is used for getting info from multiple servers in the DB)
UPDATE_TIME= (How often the leaderboard post updates)
PLAYER_COUNT_UPDATE_TIME= (How often the server status embed updates)
ARK_SERVERS= (json for server info): EXAMPLE - {"server_info": [{"server_name": "YOUR SERVER NAME HERE", "server_rcon_ip": "1.1.1.1", "server_rcon_port": 7777, "server_rcon_pass": "password", "override_embed_thumbnail": "URL TO PICTURE, THIS IS ALSO OPTIONAL"}, {"server_name": "second server", "server_rcon_ip": "2.2.2.2", "server_rcon_port": 7778, "server_rcon_pass": "password"}]}

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

Additional feature: Updates a Discord widget with the current number of players online on your ARK server.
"""

"""Try to load config"""
try:
    load_dotenv("Config/UserConfig.ini")
    TOKEN = str(os.getenv('DISCORD_TOKEN'))
    DB_FILE = 'Config/tableconfig.ini'
    CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL'))
    DO_DAILY_TOP_TEN = bool(os.getenv('DO_DAILY_TOP_TEN'))
    SERVER_NAME = str(os.getenv('SERVER_NAME'))
    LEADER_UPDATE = int(os.getenv('UPDATE_TIME'))

except Exception as e:
    input(f'Failed to load config: {e}')

CURRENT_TIME = None

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


class DateTime(BaseModel):
    datetime: str


class ServerEmbed(BaseModel):
    server_name: str
    server_rcon_ip: str
    server_rcon_port: int
    server_rcon_pass: str
    override_thumbnail: str


def parse_server_env(env_string_in):
    data = json.loads(env_string_in)
    return data


def create_server_embed(server_json):
    created_embed = ServerEmbed(server_name=server_json["server_name"], server_rcon_ip=server_json["server_rcon_ip"],
                                server_rcon_port=server_json["server_rcon_port"], server_rcon_pass=server_json["server_rcon_pass"],
                                override_thumbnail=server_json["override_thumbnail"])
    return created_embed


def execute_rcon(command, host, rcon_pass, rcon_port):
    """Execute an RCON command against your server. Requires RCON_IP, RCON_PORT, and RCON_PASS setup in the UserConfig.ini file"""
    try:
        with MCRcon(host, rcon_pass, port=rcon_port) as mcr:
            response = mcr.command(command)
            return f"Server Response to '{command}': \n\n{response}"
    except Exception as e:
        return f"Failed to connect or run command: {e}"


def execute_color_broadcast(command, host, rcon_pass, rcon_port):
    formatted_text = format_rich_text(command)
    with MCRcon(host, rcon_pass, port=rcon_port) as mcr:
        response = mcr.command(formatted_text)
        return f"Server Response to '{command}': \n\n{response}"


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


def get_player_count(host, rcon_pass, rcon_port):
    """Fetch the current player count using RCON."""
    try:
        with MCRcon(host, rcon_pass, port=rcon_port) as mcr:
            response = mcr.command("listplayers")
            player_count = response.count('\n') - 1
            lines = response.split("\n")
            names = []
            for line in lines:
                if ". " in line and ", " in line:
                    try:
                        name = line.split(". ")[1].split(", ")[0]
                        names.append(name)
                    except IndexError:
                        continue
            return player_count, names

    except Exception as e:
        return f"Failed to fetch player count: {e}"


async def get_server_uptime():
    """Fetch the server's start time via RCON and update CURRENT_TIME."""
    global CURRENT_TIME
    try:
        response = execute_rcon('cheat ScriptCommand GetDateTime')
        print(response)
        time_format = "%m-%d-%Y %H:%M:%S"
        CURRENT_TIME = datetime.strptime(response.strip(), time_format)
        return "Server start time updated"
    except Exception as e:
        return f"Error retrieving uptime: {e}"


def calculate_uptime():
    """Calculate the server uptime based on CURRENT_TIME."""
    global CURRENT_TIME
    if CURRENT_TIME is None:
        return "Start time not available"

    now = datetime.now()
    elapsed_time = now - CURRENT_TIME
    days = elapsed_time.days
    hours, remainder = divmod(elapsed_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


@tasks.loop(minutes=int(os.getenv('PLAYER_COUNT_UPDATE_TIME'), 5))
async def update_player_count():
    """Check the player count and update an embed widget in Discord."""
    embed_info = parse_server_env(os.getenv("ARK_SERVERS"))
    channel = bot.get_channel(CHANNEL_ID)
    pinned_messages = await channel.pins()
    if embed_info:
        for index, server in enumerate(embed_info["server_info"]):
            try:
                player_count, names = get_player_count(
                    host=server["server_rcon_ip"],
                    rcon_port=server["server_rcon_port"],
                    rcon_pass=server["server_rcon_pass"]
                )

                url = server.get(
                    "override_embed_thumbnail",
                    "https://raw.githubusercontent.com/OhNanoh/NanohsAscendedEquipmentCompanionBot/main/Nanoh's%20Ascended%20Equipment.png"
                )

                if isinstance(player_count, int):
                    embed = Embed(
                        title=f"🎮 {server['server_name']} Status 🎮",
                        description=f"**Current Players Online:** {player_count}",
                        color=Color.green() if player_count > 0 else Color.red()
                    )
                    embed.set_author(
                        name="NAE Companion Bot",
                        icon_url="https://raw.githubusercontent.com/OhNanoh/NanohsAscendedEquipmentCompanionBot/main/Nanoh's%20Ascended%20Equipment.png"
                    )
                    embed.set_thumbnail(url=url)
                    embed.add_field(name="Server Name", value=server["server_name"], inline=False)
                    if player_count > 0:
                        embed.add_field(name="Connected Players", value="\n".join(names))
                    embed.set_footer(text="Status updated automatically")
                    embed.timestamp = discord.utils.utcnow()

                    if index < len(pinned_messages):
                        await pinned_messages[index].edit(embed=embed)
                    else:
                        sent_message = await channel.send(embed=embed)
                        await sent_message.pin()

                else:
                    logging.warning(f"Failed to update player count for {server['server_name']}: {player_count}")

            except Exception as e:
                logging.error(f"Error updating player count for {server['server_name']}: {e}")


@tasks.loop(hours=int(os.getenv("UPDATE_TIME"), 24))
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


@bot.command(name='rconcommand', help='Executes an rcon command')
async def bot_rcon(ctx, *rcon_command):
    try:
        await ctx.send(f"Executing rcon command...")
        result = execute_rcon(' '.join(rcon_command))
        await ctx.send(result)

    except Exception as e:
        await ctx.send(f'Failed to execute rcon command: {e}')


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    if not update_player_count.is_running():
        update_player_count.start()
    if not send_daily_message.is_running() and os.getenv('DO_DAILY_TOP_TEN'):
        send_daily_message.start()


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


@app.post("/SendDateTime/")
async def get_date_time(event: DateTime):
    global CURRENT_TIME
    try:
        time_format = "%m-%d-%Y %H:%M:%S"
        CURRENT_TIME = datetime.strptime(event.datetime, time_format)
        return {"status": "Start time updated", "start_time": event.datetime}
    except ValueError as e:
        return {"status": "Error", "message": str(e)}


@app.post("/item-drop-events/")
async def create_item_drop_event(event: ItemDropEvent):
    event_dict = event.dict()

    def insert_item_drop(info_dict):
        db.insert_data(query_columns=['server_name', 'user_id', 'character_name', 'item_dropped',
                                      'chance', 'dropped_by_dino', 'server_max_level',
                                      'had_4_leaf_clover', 'server_drop_chance', 'suid'],
                       query_values=[info_dict['server_name'], info_dict['user_id'], info_dict['character_name'],
                                     info_dict['item_dropped'], info_dict['chance'], info_dict['dropped_by_dino'],
                                     info_dict['server_max_level'], info_dict['had_4_leaf_clover'],
                                     info_dict['server_drop_chance'],
                                     info_dict['suid']])

    if all(x for x in event_dict.values()):
        insert_item_drop(event_dict)
    else:
        print(f'Failed to insert: {event_dict}')


@app.on_event("startup")
def startup_event():
    asyncio.create_task(bot.start(TOKEN))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
