from fastapi import FastAPI
from pydantic import BaseModel
import PythonModules.SQLiteHelper as SH
import discord
from discord.ext import commands, tasks
import os
import asyncio
from dotenv import load_dotenv

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


def has_role(role_names):
    """Checking if user has the role specified in the decorator call this function is assigned to"""

    def predicate(ctx):
        for ind_role in role_names:
            role = discord.utils.get(ctx.guild.roles, name=ind_role)
            if role is None:
                raise commands.CheckFailure(f"The role '{role}' does not exist on this server.")
            if role not in ctx.author.roles:
                pass
            return True
    return commands.check(predicate)


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


@app.on_event("startup")
def startup_event():
    """On Async.io start, start discord bot"""
    asyncio.create_task(bot.start(TOKEN))


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
        await send_discord_message(f'Failed Insert: {event_dict}')
        print(f'Failed to insert: {event_dict}')


#@has_role(['YourRoleHere', 'SecondRole']) - Use if you want to restrict this command to only users with a specific role, can take one role, or an array of roles
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


#@has_role(['YourRoleHere', 'SecondRole']) - Use if you want to restrict this command to only users with a specific role, can take one role, or an array of roles
@bot.command(name='getservertopten', help='Get your servers total number of item drops!')
async def get_server_top_ten(ctx):
    """Manual bot command for getting server top ten"""

    user_data = db.select_data('user_id, character name, COUNT(*) as drop_count',
                               f'server_name = {SERVER_NAME} GROUP BY user_id, character_name;')
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


@tasks.loop(hours=24)
async def send_daily_message():
    """Send daily server top ten message. Requires CHANNEL_ID field in UserConfig to be filled out."""

    if DO_DAILY_TOP_TEN:
        channel = bot.get_channel(CHANNEL_ID)
        user_data = db.select_data('user_id, character name, COUNT(*) as drop_count',
                                   f'server_name = {SERVER_NAME} GROUP BY user_id, character_name;')
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