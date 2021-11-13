![Deployment State](https://img.shields.io/github/deployments/2kai2kai2/eu4img/eu4imgbot?label=deployment&logo=heroku)
![Code Size](https://img.shields.io/github/languages/code-size/2kai2kai2/eu4img)
![Total Size](https://img.shields.io/github/repo-size/2kai2kai2/eu4img)
![License GPL-3.0](https://img.shields.io/github/license/2kai2kai2/eu4img)
![Vulnerabilities](https://img.shields.io/snyk/vulnerabilities/github/2kai2kai2/eu4img)
# The Cartographer

This bot is a must-have for Discord servers that play the video game [Europa Universalis IV](https://eu4.paradoxwikis.com/Europa_Universalis_4_Wiki) (EU4) by Paradox Interactive.

While primarily intended for multiplayer campaigns, The Cartographer fully supports all applicable features for singleplayer.

## Features:

### 1) Beautiful Post-Game AAR Stats

Similar to the popular tool [Skanderbeg](https://skanderbeg.pm), The Cartographer provides statistics and a map showing information about an uploaded game save file. However, The Cartographer is unique in that it posts an aesthetically fitting image containing this information directly into the Discord channel.

To get started, simply type `/stats` in the channel where you want the display to be posted. There is an optional `skanderbeg` option which, if enabled, will automatically upload to Skanderbeg and post the link alongside the in-channel stats display.

The Cartographer will send you a direct message with instructions on how to upload the file and optionally modify the list of players to be displayed.

![Stats Example](https://media.discordapp.net/attachments/655980109676675072/812136817125490748/finalimg.png?width=2016&height=1134)

_Map shows player borders including subject states. And yes, I am the one playing the unnecessarily wealthy Russia that has seized London, Tehran, and Beijing. For the record, colonialism and imperalism are bad IRL._


### 2) Managing Multiplayer Campaign Reservations

Easy commands to set up a channel for reservations. Simply set up a fresh channel for reservations and type `/reservations`

- Avoid duplicates picks and conflicts: It's first-come, first serve (with admin overrides, of course)!
- Automatically inform users when they've selected a banned nation.
- Automatically delete messages to the channel that could push the reservation list up.
- An image showing the picked nations, making it easier to find one you want to play that's open.
- Most importantly, keep everything organized!

![Reservations](https://cdn.discordapp.com/attachments/655980109676675072/908943926814195713/unknown.png)

----

## How can I add this to my Discord server?
While we do not currently have a link to add the bot publically available, but you can request a link on
[**The Cartographer** Official Discord Server](https://img.shields.io/discord/846487859661504532?label=Discord&logo=discord&logoColor=white)

[![Discord Button](https://img.shields.io/discord/846487859661504532?label=Discord&logo=discord&logoColor=white)
](https://img.shields.io/discord/846487859661504532?label=Discord&logo=discord&logoColor=white)

## Running Your Own Bot Instance

If you would prefer to run your own instance of the bot, you can. (If you're not sure, feel free to join the Discord server with the above link and ask!) 

Depending on your system or hosting service, you may have different ways of running the program. However, there are a few things that are important:

### 1. Environment Variables

Either in your environment variables or in the `.env` file, provide the following:

| Environment Variable | Description |
| -------------------- | ----------- |
| `DISCORD_TOKEN`      | A Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications). |
| `SKANDERBEG_TOKEN` | (optional) A [Skanderbeg](https://skanderbeg.pm/) API token for automatic Skanderbeg uploads. |
| `MONGODB_USERNAME` | Username to access a MongoDB cluster where the bot will store its data. |
| `MONGODB_PASSWORD` | Password to access a MongoDB cluster where the bot will store its data. |
| `MONGODB_CLUSTERURL` | Cluster URL to access a MongoDB cluster where the bot will store its data. |

A template can be found in the file `template.env`; simply rename to `.env` and modify.

### 2. Install Dependencies

The recommended method for running the bot is in a Docker Container. A `Dockerfile` is provided which will load the necessary dependencies.

If you decide not to use Docker, you can still install dependencies manually:
```
pip install -r requirements.txt
```

### 3. Run

If you choose to run the bot in a Docker Container, the command to start is already setup in `Dockerfile`.

If you decide not to use Docker, the following are example commands for starting up the bot:

Linux:
```
python3 EU4Bot.py
```
Windows:
```
python EU4Bot.py
```
However, many hosting services or different platforms may have different methods for running Python 3.x programs.

----

## Updates

Updated game data will be needed when a new EU4 version is released. I will do my best to this as soon as possible after new game updates are released, but private bot instances will need to update from the GitHub repo.