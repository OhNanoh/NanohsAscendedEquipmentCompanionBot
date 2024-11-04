# NanohsAscendedEquipementCompanionBot
This bot was created after multiple requests from server owners to allow for a way to have their own top ten in their  discord servers. 


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

This python script will require port 8000 to be open on the firewall for the hosting server.


HOW TO SETUP MOD SIDE:

Have an ark server admin execute the following:


cheat ScriptCommand SetupBot "Your arkserver domain or ip here"


DO NOT INCLUDE HTTPS://

Only the domain or ip

Examples:

cheat ScriptCommand SetupBot test.arkservers.com

cheat ScriptCommand SetupBot 192.129.129.129


