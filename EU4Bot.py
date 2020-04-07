import os
from abc import ABC, abstractmethod
from io import BytesIO, StringIO
from random import shuffle
from typing import List, Optional, Union, Tuple
import asyncio

import discord
import psycopg2
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

import EU4Lib
import EU4Reserve
import GuildManager

load_dotenv()
token: str = os.getenv('DISCORD_TOKEN')
client = discord.Client()
# Get database if it exists; if not None and methods will open a json file.
try:
    DATABASEURL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASEURL, sslmode='require')
    conn.autocommit = True
except:
    conn = None

DiscUser = Union[discord.User, discord.Member]
DiscTextChannels = Union[discord.TextChannel,
                         discord.DMChannel, discord.GroupChannel]


def imageToFile(img: Image) -> discord.File:
    """Comverts PIL Images into discord File objects."""
    file = BytesIO()
    img.save(file, "PNG")
    file.seek(0)
    return discord.File(file, "img.png")


async def sendUserMessage(user: Union[str, int, DiscUser], message: str) -> discord.Message:
    """Sends a user a specified DM via discord. Returns the discord Message object sent."""
    u = None
    if isinstance(user, str) or isinstance(user, int):  # id
        u = client.get_user(int(user))
    elif isinstance(user, discord.User) or isinstance(user, discord.Member):
        u = user
    else:
        print("ERROR: Could not find discord user to send message.")
        print(user)
        return  # pass uh something went wrong
    if u.dm_channel is None:
        await u.create_dm()
    msg = await u.dm_channel.send(message)
    return msg


def getRoleFromStr(server: Union[str, int, discord.Guild], roleName: str) -> Optional[discord.Role]:
    """Converts a string into the role on a specified discord server.
    Use an '@role' string as the roleName argument. (@ is optional)
    Returns None if the role cannot be found."""
    if roleName is None:
        return None
    # Get server object
    s = None
    if isinstance(server, str) or isinstance(server, int):
        s = client.get_guild(int(server))
    elif isinstance(server, discord.Guild):
        s = server
    else:
        print("ERROR: Could not find discord server get role.")
    for role in s.roles:
        if role.name.strip("\n\t @").lower() == roleName.strip("\n\t @").lower():
            return role
    return None


def checkResAdmin(server: Union[str, int, discord.Guild], user: [str, int, DiscUser]) -> bool:
    """Returns whether or not a user has bot admin control roles as set in .env on a server."""
    # Get server object
    s: discord.Guild = None
    if isinstance(server, str) or isinstance(server, int):
        s = client.get_guild(int(server))
    elif isinstance(server, discord.Guild):
        s = server
    else:
        print("ERROR: Could not find discord server to check for admin.")
        return False
    # Get member object
    u: discord.Member = None
    if isinstance(user, str) or isinstance(user, int):  # id
        u = s.get_member(int(user))
    elif isinstance(user, discord.User):
        u = s.get_member(user.id)
    elif isinstance(user, discord.Member):
        u = user
    else:
        print("ERROR: Could not find discord user to check for admin.")
        print(user)
        return False  # pass uh something went wrong.. false i guess?
    # OK now check
    role = getRoleFromStr(s, GuildManager.getGuildSave(s, conn=conn).admin)
    return (role is not None and role <= u.top_role) or u.top_role.id == s.roles[-1].id or u._user.id == 249680375280959489


class AbstractChannel(ABC):
    @abstractmethod
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels):
        self.user = user
        self.interactChannel = initChannel
        self.displayChannel = initChannel

    @abstractmethod
    async def responsive(self, message: discord.Message) -> bool:
        pass

    @abstractmethod
    async def process(self, message: discord.Message):
        pass

    @abstractmethod
    async def msgdel(self, msgID: Union[str, int]):
        pass

    @abstractmethod
    async def userdel(self, user: DiscUser):
        pass


class ReserveChannel(AbstractChannel):
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels, Load=False, textID: Optional[int] = None, imgID: Optional[int] = None):
        self.user = None
        self.interactChannel = initChannel
        self.displayChannel = initChannel
        self.textID: Optional[int] = textID
        self.imgID: Optional[int] = imgID
        if not Load:  # If this is new, then make a new Reserve.
            res = EU4Reserve.Reserve(str(self.interactChannel.id))
            # Set the ban list to the server default
            res.bans = GuildManager.getGuildSave(
                self.interactChannel.guild, conn=conn).defaultBan
            EU4Reserve.addReserve(res, conn=conn)

    def prefix(self) -> str:
        return GuildManager.getGuildSave(self.interactChannel.guild, conn=conn).prefix

    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel

    async def process(self, message: discord.Message):
        text: str = message.content.strip("\n\t ")
        if text.upper() == self.prefix() + "HELP":  # HELP
            stringHelp = "__**Command help for " + message.channel.mention + ":**__"
            stringHelp += "\n**" + self.prefix() + "HELP**\nGets you this information!"
            stringHelp += "\n**" + self.prefix() + \
                "RESERVE [nation]**\nReserves a nation or overwrites your previous reservation. Don't include the brackets."
            stringHelp += "\n**" + self.prefix() + "DELRESERVE**\nCancels your reservation."
            # Here we send info about commands only for admins
            if checkResAdmin(message.guild, message.author):
                stringHelp += "\n**" + self.prefix() + \
                    "END**\nStops allowing reservations and stops the bot's channel management.\nThis should be done by the time the game starts."
                stringHelp += "\n**" + self.prefix() + \
                    "ADMRES [nation] [@user]**\nReserves a nation on behalf of a player on the server.\nMake sure to actually @ the player. This ignores the ban list."
                stringHelp += "\n**" + self.prefix() + \
                    "ADMDELRES [@user]**\nDeletes a player's reservation.\nMake sure to actually @ the player."
                stringHelp += "\n**" + self.prefix() + \
                    "UPDATE**\nUpdates the reservations list. Should usually not be necessary unless in debug or something went wrong."
                stringHelp += "\n**" + self.prefix() + \
                    "ADDBAN [nation], [nation], ... **\nAdds countries to the ban list. Add commas between each entry if there are more than one."
                stringHelp += "\n**" + self.prefix() + \
                    "DELBAN [nation], [nation], ... **\nRemoves countries from the ban list. Add commas between each entry if there are more than one."
            await message.delete()
            await sendUserMessage(message.author, stringHelp)
        elif text.upper() == self.prefix() + "UPDATE" and checkResAdmin(message.guild, message.author):  # UPDATE
            await message.delete()
            await self.updateText()
            await self.updateImg()
        elif text.upper() == self.prefix() + "END" and checkResAdmin(message.guild, message.author):  # END
            await message.delete()
            await self.displayChannel.send("*Reservations are now ended. Good Luck.*")
            EU4Reserve.deleteReserve(str(self.displayChannel.id), conn=conn)
            interactions.remove(self)
            del(self)
        # RESERVE [nation]
        elif text.upper().startswith(self.prefix() + "RESERVE "):
            res = text.split(" ", 1)[1].strip("\n\t ")
            tag = EU4Lib.country(res)
            if tag is not None:
                if EU4Reserve.isBanned(str(self.displayChannel.id), tag, conn=conn):
                    await sendUserMessage(message.author, "You may not reserve " + EU4Lib.tagToName(tag) + " in " + self.displayChannel.mention + " because it is banned. If you still want to play it, please have an admin override.")
                else:
                    await self.add(EU4Reserve.reservePick(message.author.mention, tag.upper()))
            else:
                await sendUserMessage(message.author, "Your country reservation in " + self.displayChannel.mention + " was not recorded, as \"" + res + "\" was not recognized.")
            await message.delete()
        # ADMRES [nation] @[player]
        elif text.upper().startswith(self.prefix() + "ADMRES") and checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                res = text.split(maxsplit=1)[1].strip("\n\t <@!1234567890>")
                tag = EU4Lib.country(res)
                if tag is not None:
                    await self.add(EU4Reserve.reservePick(message.mentions[0].mention, tag.upper()))
                else:
                    await sendUserMessage(message.author, "Your reservation for " + message.mentions[0].mention + " in " + self.displayChannel.mention + " was not recorded, as \"" + res + "\" was not recognized.")
            else:
                await sendUserMessage(message.author, "Your reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        elif text.upper() == self.prefix() + "DELRESERVE" or text.upper() == self.prefix() + "DELETERESERVE":  # DELRESERVE
            await self.removePlayer(message.author.mention)
            await message.delete()
        # ADMDELRES @[player]
        elif text.upper().startswith(self.prefix() + "ADMDELRES") and checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                await self.removePlayer(message.mentions[0].mention)
            else:
                await sendUserMessage(message.author, "Your deletion of a reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        # ADDBAN [nation], [nation], ...
        elif text.upper().startswith(self.prefix() + "ADDBAN") and checkResAdmin(message.guild, message.author):
            bannations = text.partition(" ")[2].strip("\n\t ,").split(",")
            bantags = []
            fails = []
            for bannat in bannations:
                tag = EU4Lib.country(bannat.strip("\n\t ,"))
                if tag is not None:
                    bantags.append(tag)
                else:
                    fails.append(bannat)
            string = ""
            if len(bantags) > 0:
                EU4Reserve.addBan(str(self.displayChannel.id),
                                  bantags, conn=conn)
                string += "Added the following nations to the ban list in " + \
                    self.displayChannel.mention + ": "
                for tag in bantags:
                    string += EU4Lib.tagToName(tag)
                    if tag is not bantags[-1]:
                        string += ", "
            if len(fails) > 0:
                string += "\nDid not recognize the following nations: "
                for tag in fails:
                    string += EU4Lib.tagToName(tag)
                    if tag is not fails[-1]:
                        string += ", "
                string += "\n The unrecognized nations were not added to the ban list."
            if string != "":
                await sendUserMessage(message.author, string)
            await message.delete()
            await self.updateText()
        # DELBAN [nation], [nation], ...
        elif text.upper().startswith(self.prefix() + "DELBAN") and checkResAdmin(message.guild, message.author):
            bannations = text.partition(" ")[2].strip("\n\t ,").split(",")
            bantags = []
            fails = []
            for bannat in bannations:
                tag = EU4Lib.country(bannat.strip("\n\t ,"))
                if tag is not None:
                    bantags.append(tag)
                else:
                    fails.append(bannat)
            string = ""
            if len(bantags) > 0:
                EU4Reserve.deleteBan(
                    str(self.displayChannel.id), bantags, conn=conn)
                string += "Removed the following nations from the ban list in " + \
                    self.displayChannel.mention + ": "
                for tag in bantags:
                    string += EU4Lib.tagToName(tag)
                    if tag is not bantags[-1]:
                        string += ", "
            if len(fails) > 0:
                string += "\nDid not recognize the following nations: "
                for tag in fails:
                    string += EU4Lib.tagToName(tag)
                    if tag is not fails[-1]:
                        string += ", "
                string += "\n The unrecognized nations were not removed from the ban list."
            if string != "":
                await sendUserMessage(message.author, string)
            await message.delete()
            await self.updateText()
        else:
            await message.delete()

    async def updateText(self):
        reserve: EU4Reserve.Reserve = EU4Reserve.getReserve(
            str(self.interactChannel.id), conn=conn)
        string = "How to reserve: " + self.prefix() + \
            "reserve [nation]\nTo unreserve: " + self.prefix() + "delreserve\n"
        string += "Banned nations: "
        if len(reserve.bans) == 0:
            string += "*none or unspecified*"
        for tag in reserve.bans:
            name = EU4Lib.tagToName(tag)
            if name is None:
                string += tag
            else:
                string += name
            if tag is not reserve.bans[-1]:
                string += ", "
        string += "\n**Current players list:**"
        if reserve is None or len(reserve.players) == 0:
            string = string + "\n*It's so empty here...*"
        else:
            reserve.players.sort(key=lambda x: x.time)
            for x in reserve.players:
                string = string + "\n" + x.player + \
                    ": " + EU4Lib.tagToName(x.tag) + " | " + x.timeStr()
        if self.textID is None:
            self.textID = (await self.displayChannel.send(content=string)).id
            EU4Reserve.updateMessageIDs(
                str(self.displayChannel.id), textmsg=self.textID, conn=conn)
        else:
            await (await (self.displayChannel).fetch_message(self.textID)).edit(content=string)

    async def updateImg(self):
        reserve: EU4Reserve.Reserve = EU4Reserve.getReserve(
            str(self.interactChannel.id), conn=conn)
        if reserve is None:
            reserve = EU4Reserve.Reserve(str(self.interactChannel.id))
        if self.imgID is None:
            self.imgID = (await self.displayChannel.send(file=imageToFile(EU4Reserve.createMap(reserve)))).id
            EU4Reserve.updateMessageIDs(
                str(self.displayChannel.id), imgmsg=self.imgID, conn=conn)
        else:
            await (await self.interactChannel.fetch_message(self.imgID)).delete()

    async def add(self, nation: EU4Reserve.reservePick) -> int:
        addInt = EU4Reserve.addPick(
            str(self.interactChannel.id), nation, conn=conn)
        if addInt == 1 or addInt == 2:  # Success!
            await self.updateText()
            await self.updateImg()
        elif addInt == 0:  # This is not a reserve channel. How did this happen?
            await sendUserMessage(client.get_user(int(nation.player.strip("\n\t <@>"))), "You can't reserve nations in " + self.displayChannel.mention + ".")
        elif addInt == 3:  # This nation is already taken
            await sendUserMessage(client.get_user(int(nation.player.strip("\n\t <@>"))), "The nation " + EU4Lib.tagToName(nation.tag) + " is already reserved in " + self.displayChannel.mention + ".")
        return addInt

    async def remove(self, tag: str):
        pass

    async def removePlayer(self, name: str):
        # If it did anything
        if EU4Reserve.deletePick(str(self.interactChannel.id), name, conn=conn):
            await self.updateText()
            await self.updateImg()

    async def msgdel(self, msgID: Union[str, int]):
        if msgID == self.textID:
            self.textID = None
            await self.updateText()
            # This will call msgdel again to update the image
            await (await self.interactChannel.fetch_message(self.imgID)).delete()
        elif msgID == self.imgID:
            self.imgID = None
            reserve = EU4Reserve.getReserve(
                str(self.interactChannel.id), conn=conn)
            if reserve is None:
                reserve = EU4Reserve.Reserve(str(self.interactChannel.id))
            self.imgID = (await self.displayChannel.send(file=imageToFile(EU4Reserve.createMap(reserve)))).id
            EU4Reserve.updateMessageIDs(
                str(self.displayChannel.id), imgmsg=self.imgID, conn=conn)

    async def userdel(self, user: DiscUser):
        if (hasattr(self.displayChannel, 'guild') and self.displayChannel.guild == user.guild) or (hasattr(self.interactChannel, 'guild') and self.interactChannel.guild == user.guild):
            await self.removePlayer(user)


class Nation:
    def __init__(self, player: str):
        self.player = player
        self.tag: Optional[str] = None
        self.development: int = 0
        self.prestige: int = None
        self.stability: int = None
        #self.manpower = None
        #self.maxManpower = None
        self.army: float = 0.0
        self.navy: int = 0
        self.debt: int = 0
        self.treasury: float = 0.0
        self.totalIncome: float = 0.0
        self.totalExpense: float = 0.0
        self.scorePlace = None
        self.capitalID: int = 0


class xNation:
    def __init__(self, tag: str):
        self.tag: str = tag.upper()
        self.development: int = 0
        self.prestige: int = None
        self.stability: int = None
        #self.manpower = None
        #self.maxManpower = None
        self.army: float = 0.0
        self.navy: int = 0
        self.debt: int = 0
        self.treasury: float = 0.0
        self.totalIncome: float = 0.0
        self.totalExpense: float = 0.0
        self.scorePlace = None
        self.capitalID: int = 0
        self.overlord: Optional[str] = None
        self.allies: List[str] = []
        self.subjects: List[str] = []
        #self.revColors: color = None
        self.mapColor: Tuple[int, int, int] = None
        self.natColor: Tuple[int, int, int] = None

    def fullDataStr(self) -> str:
        string = "Tag: " + self.tag + "\n"
        string += "Dev: " + str(self.development) + " Prestige: " + \
            str(self.prestige) + " Stability: " + str(self.stability) + "\n"
        string += "Army: " + str(self.army) + " Navy: " + str(self.navy) + "\n"
        string += "Treasury: " + \
            str(self.treasury) + " Debt: " + str(self.debt) + "\n"
        string += "Income: " + str(self.totalIncome) + \
            " Expenses: " + str(self.totalExpense) + "\n"
        string += "Capital: " + str(self.capitalID)
        return string


class war():
    def __init__(self, name: str):
        self.name = name
        self.attackers: List[str] = []
        self.defenders: List[str] = []
        self.attackerLosses: int = 0
        self.defenderLosses: int = 0
        self.startDate: str = None
        self.endDate: str = None
        self.result: int = 0  # 1 = WP; 2 = Attacker wins; 3 = Defender wins

    def isPlayerWar(self, playertags: List[str]):
        attacker = False
        defender = False
        for tag in self.attackers:
            if tag in playertags:
                attacker = True
                break
        for tag in self.defenders:
            if tag in playertags:
                defender = True
                break
        return attacker and defender

    def playerAttackers(self, playertags: List[str]):
        return list(filter(lambda x: x in self.attackers, playertags))

    def playerDefenders(self, playertags: List[str]):
        return list(filter(lambda x: x in self.defenders, playertags))

    def warScale(self, playertags: List[str] = []):
        """Calculates a score for how important the war is for deciding which to display. May be somewhat arbitrary or subjective."""
        if playertags is None or playertags == {}:  # Ignore player involvement
            # Base off casualties
            return self.attackerLosses + self.defenderLosses
        else:  # Include player involvement
            # Scale by number of players
            return (self.attackerLosses + self.defenderLosses) * max(min(len(self.playerAttackers(playertags)) * 0.7, len(self.playerDefenders(playertags)) * 0.7), 1)


class saveGame():
    def __init__(self):
        self.allNations: dict = {}
        self.playertags: dict = {}
        self.dlc: List[str] = []
        self.GP: List[str] = []
        self.date: Optional[str] = None
        self.mp: bool = True
        self.age: Optional[str] = None
        self.HRE: str = None
        self.china: str = None
        self.crusade: str = None
        self.playerWars: List[war] = []


class statsChannel(AbstractChannel):
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels):
        self.user = user
        self.interactChannel = None
        self.displayChannel = initChannel
        self.hasReadFile = False
        self.politicalImage: Image = None
        #self.playersImage: Image = Image.open("src/BlankPlayerMap.png")
        self.playersImage = None
        self.game = saveGame()
        self.modMsg = None
        self.doneMod = False

    async def asyncInit(self):
        """Does of the init stuff that needs to happen async. Returns self."""
        if self.user.dm_channel is None:
            await self.user.create_dm()
        self.interactChannel = self.user.dm_channel
        await self.interactChannel.send("**Send EITHER an uncompressed .eu4 save file\nor a direct link to an uncompressed .eu4 save file:**\nYou can do this by uploading to https://www.file.io/\nthen clicking **Copy Link** and entering it here:")
        return self

    def modPromptStr(self) -> str:
        """Makes and returns a string giving information for player list modification."""
        prompt = "**Current players list:**```"
        for x in self.game.playertags:
            if EU4Lib.tagToName(x) is None:
                prompt += "\n" + x + ": " + self.game.playertags[x]
            else:
                prompt += "\n" + \
                    EU4Lib.tagToName(x) + ": " + self.game.playertags[x]
        prompt += "```\n**Do you want to make any changes?\nType `'done'` to finish. Commands:\n`remove [nation]`\n`add [player], [nation]`**"
        return prompt

    async def readFile(self, file):
        """Gets all data from file and saves it to the self.game"""
        lines: List[str] = file.readlines()
        brackets: List[str] = []
        currentReadWar: war = None
        currentReadWarParticTag: str = None
        currentWarLastLeave: str = None
        lastPlayerInList: str = None

        # Reading save file...
        linenum = 0
        for line in lines:
            linenum += 1
            if "{" in line:
                if line.count("{") == line.count("}"):
                    continue
                elif line.count("}") == 0 and line.count("{") == 1:
                    brackets.append(line.rstrip("\n "))
                elif line.count("}") == 0 and line.count("{") > 1:
                    for x in range(line.count("{")):
                        brackets.append("{")  # TODO: fix this so it has more
                else:  # Unexpected Brackets
                    pass
            elif "}" in line:
                try:
                    brackets.pop()
                except IndexError:  # No brackets to close
                    pass
            # Get rid of long, useless sections
            # elif len(brackets) < 0 and ("trade={" == brackets[1] or "provinces={" == brackets[0] or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
            #    continue
            # Get player names and country tags

            # This is where we do stuff
            elif len(brackets) == 0:
                # Get current gamedate
                if line.startswith("date="):
                    self.game.date = line.strip('date=\n')
                # Get save DLC (not sure if we use this...)
                elif brackets == ["dlc_enabled={"]:
                    self.game.dlc.append(line.strip('\t"\n'))
                # Check if game is mp
                elif "multi_player=" in line:
                    if "yes" in line:
                        self.game.mp = True
                    else:
                        self.game.mp = False
                # Get current age
                elif "current_age=" in line and brackets == []:
                    self.game.age = line[12:].strip('"\n')
            elif brackets == ["players_countries={"]:
                # In the file, the format is like this:
                # players_countries={
                #   "playername"
                #   "SWE"
                #
                # Where "   " is a tab \t
                # Prepare to assign the player by recording it for the next line
                if lastPlayerInList is None:
                    lastPlayerInList = line.strip('\t"\n')
                # Add to playertags based on what was saved in the previous line as the player name
                else:
                    self.game.playertags[line.strip(
                        '\t"\n ')] = lastPlayerInList
                    lastPlayerInList = None
            # Get top 8
            elif "country=" in line and brackets == ["great_powers={", "\toriginal={"]:
                if len(self.game.GP) < 8:  # Make sure to not include leaving GPs
                    self.game.GP.append(line.strip('\tcountry="\n'))
            # Get HRE emperor tag
            elif "\temperor=" in line and brackets == ["empire={"]:
                self.game.HRE = line.strip('\temperor="\n')
            # Get Celestial emperor tag
            elif "emperor=" in line and brackets == ["celestial_empire={"]:
                self.game.china = line.strip('\temperor="\n')
            # Get target of crusade ('---' if none)
            elif "crusade_target=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
                self.game.crusade = line.strip('\tcrusade_target="\n')
            # Get papal controller
            elif "previous_controller=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
                continue
            # Country-specific data (for players)
            elif len(brackets) > 1 and brackets[0] == "countries={":
                if len(brackets) == 2:
                    if "government_rank=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")] = xNation(
                            brackets[1].strip("\n\t ={"))
                    elif "raw_development=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].development = round(
                            float(line.strip("\traw_devlopmnt=\n")))
                    elif "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].capitalID = int(
                            line.strip("\tcapitl=\n"))
                    elif "score_place=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].scorePlace = round(
                            float(line.strip("\tscore_place=\n")))
                    elif "prestige=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].prestige = round(
                            float(line.strip("\tprestige=\n")))
                    elif "stability=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].stability = round(
                            float(line.strip("\tstability=\n")))
                    elif "treasury=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].treasury = round(
                            float(line.strip("\ttreasury=\n")))
                    # elif "\tmanpower=" in line:
                        #x.manpower = round(float(line.strip("\tmanpower=\n")))
                    # elif "max_manpower=" in line:
                        #x.maxManpower = round(float(line.strip("\tmax_manpower=\n")))
                    elif "overlord=\"" in line:
                        self.game.allNations[brackets[1].strip(
                            "\n\t ={")].overlord = line.split("\"")[1]
                elif len(brackets) == 3:
                    # Get each loan and add its amount to debt
                    if brackets[2] == "\t\tloan={" and "amount=" in line:
                        self.game.allNations[brackets[1].strip(
                            "\n\t ={")].debt += round(float(line.strip("\tamount=\n")))
                    # Get Income from the previous month
                    elif brackets[2] == "\t\tledger={" and "\tlastmonthincome=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].totalIncome = round(
                            float(line.strip("\tlastmonthincome=\n")), 2)
                    # Get Expense from the previous month
                    elif brackets[2] == "\t\tledger={" and "\tlastmonthexpense=" in line:
                        self.game.allNations[brackets[1].strip("\n\t ={")].totalExpense = round(
                            float(line.strip("\tlastmonthexpense=\n")), 2)
                    elif brackets[2] == "\t\tsubjects={":
                        for subject in line.strip().split():
                            self.game.allNations[brackets[1].strip(
                                "\n\t ={")].subjects.append(subject)
                    elif brackets[2] == "\t\tallies={":
                        for ally in line.strip().split():
                            self.game.allNations[brackets[1].strip(
                                "\n\t ={")].allies.append(ally)
                elif len(brackets) == 4:
                    # Add 1 to army size for each regiment
                    if brackets[2] == "\t\tarmy={" and "regiment={" in brackets[3] and "morale=" in line:
                        self.game.allNations[brackets[1].strip(
                            "\n\t ={")].army += 1000
                    # Subtract damage done to units from army size
                    # This needs to be separate from ^ because for full regiments there is no "strength=" tag
                    elif brackets[2] == "\t\tarmy={" and "regiment={" in brackets[3] and "strength=" in line:
                        try:
                            self.game.allNations[brackets[1].strip("\n\t ={")].army = round(
                                self.game.allNations[brackets[1].strip("\n\t ={")].army - 1000 + 1000 * float(line.strip("\tstrength=\n")))
                        except ValueError:
                            continue
                    # Add 1 for each ship
                    elif brackets[2] == "\t\tnavy={" and brackets[3] == "\t\t\tship={" and "\thome=" in line:
                        self.game.allNations[brackets[1].strip(
                            "\n\t ={")].navy += 1
                    elif brackets[2] == "\t\tcolors={" and brackets[3] == "\t\t\tmap_color={":
                        self.game.allNations[brackets[1].strip("\n\t ={")].mapColor = tuple(map(lambda x: int(x), line.strip().split()))
                    elif brackets[2] == "\t\tcolors={" and brackets[3] == "\t\t\tcountry_color={":
                        self.game.allNations[brackets[1].strip("\n\t ={")].natColor = tuple(map(lambda x: int(x), line.strip().split()))
                # End new save stuff
            elif len(brackets) > 0 and brackets[0] == "previous_war={":
                if len(brackets) == 1 and "\tname=\"" in line:
                    if currentReadWar is not None and currentReadWar.isPlayerWar(self.game.playertags):
                        currentReadWar.endDate = currentWarLastLeave
                        self.game.playerWars.append(currentReadWar)
                    currentReadWar = war(line.split("=")[1].strip("\n\t \""))
                elif len(brackets) == 3 and brackets[1] == "\thistory={":
                    if "add_attacker=\"" in line:
                        currentReadWar.attackers.append(line.split("\"")[1])
                        if currentReadWar.startDate is None:
                            currentReadWar.startDate = brackets[2].strip(
                                "\t={\n ")
                    elif "add_defender=\"" in line:
                        currentReadWar.defenders.append(line.split("\"")[1])
                    elif "rem_attacker=\"" in line or "rem_defender=\"" in line:
                        currentWarLastLeave = brackets[2].strip("\t={\n ")
                elif len(brackets) >= 2 and brackets[1] == "\tparticipants={":
                    if len(brackets) == 2 and "\t\ttag=\"" in line:
                        currentReadWarParticTag = line.split("\"")[1]
                    elif len(brackets) == 4 and brackets[2] == "\t\tlosses={" and brackets[3] == "\t\t\tmembers={":
                        if currentReadWarParticTag in currentReadWar.attackers:
                            for x in line.strip("\n\t ").split():
                                currentReadWar.attackerLosses += int(x)
                        elif currentReadWarParticTag in currentReadWar.defenders:
                            for x in line.strip("\n\t ").split():
                                currentReadWar.defenderLosses += int(x)
                        else:
                            print(
                                "Something went wrong with the attacker/defender list.")
                elif len(brackets) == 1 and "\toutcome=" in line:
                    currentReadWar.result = int(line.strip("\toutcme=\n "))
                    if currentReadWar.isPlayerWar(self.game.playertags):
                        currentReadWar.endDate = currentWarLastLeave
                        self.game.playerWars.append(currentReadWar)
                        currentReadWar = None
        # Finalize data
        # These signify that it's probably not a valid save file.
        if self.game.GP == [] or self.game.date == None or self.game.age == None:
            raise Exception(
                "This probably isn't a valid .eu4 uncompressed save file from " + self.user.mention)
        for x in self.game.allNations.copy().keys():
            if self.game.allNations[x].development == 0:
                try:
                    del(self.game.allNations[x])
                except:
                    pass
                try:
                    del(self.game.playertags[x])
                except:
                    pass
            # else:
                # print(self.game.allNations[x].fullDataStr())
        # Sort Data:
        self.game.playerWars.sort(key=lambda x: x.warScale(
            self.game.playertags), reverse=True)

    async def generateImage(self) -> Image:
        """Returns a stats Image based off the self.game data."""
        imgFinal: Image = Image.open("src/finalTemplate.png")
        mapFinal: Image = self.politicalImage.copy()
        # Make the army display text

        def armyDisplay(army: int):
            armydisplay = str(round(army/1000, 1))
            if armydisplay.endswith(".0") or ("." in armydisplay and len(armydisplay) > 4):
                armydisplay = armydisplay.partition(".")[0]
            return armydisplay + "k"
        # Player and player-owned country colors
        def invertColor(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
            return (255 - color[0], 255 - color[1], 255 - color[2])
        playerColors = {} # Formatting: (map color) = (player contrast color)
        for natTag in self.game.allNations:
            try:
                nat: xNation = self.game.allNations[natTag]
                playerNatTag: str = None # This is what nation actually is said to own the land
                # Check if this nation is a player
                if natTag in self.game.playertags:
                    playerNatTag = natTag
                # Check if any overlord(s) are players and if so, go with the highest one.
                while nat.overlord is not None:
                    if nat.overlord in self.game.playertags:
                        playerNatTag = nat.overlord
                    nat = self.game.allNations[nat.overlord]
                if playerNatTag is not None:
                    playerColors[self.game.allNations[natTag].mapColor] = invertColor(self.game.allNations[playerNatTag].mapColor)
            except:
                pass
        # Modify the image
        mapDraw = ImageDraw.Draw(mapFinal)
        drawColors = {} # Formatting: (draw color) = [(x, y), (x, y), ...]
        for x in range(mapFinal.size[0]):
            for y in range(mapFinal.size[1]):
                color = self.politicalImage.getpixel((x, y))
                if color in playerColors:
                    for neighbor in ((x - 1, y - 1), (x, y - 1), (x + 1, y - 1), (x - 1, y), (x + 1, y), (x - 1, y + 1), (x, y + 1), (x + 1, y + 1)):
                        try:
                            neighborColor = self.politicalImage.getpixel(neighbor)
                        except:
                            # This means that we're out of bounds. That's okay. We're on the edge of the map so draw a border here.
                            if playerColors[color] in drawColors:
                                drawColors[playerColors[color]].append((x, y))
                            else:
                                drawColors[playerColors[color]] = [(x, y)]
                            break
                        else:
                            if neighborColor not in playerColors or playerColors[neighborColor] != playerColors[color]:
                                if playerColors[color] in drawColors:
                                    drawColors[playerColors[color]].append((x, y))
                                else:
                                    drawColors[playerColors[color]] = [(x, y)]
                                break
        for drawColor in drawColors:
            mapDraw.point(drawColors[drawColor], drawColor)
        del(drawColors)
        del(playerColors)
        # Start Final Img Creation
        # Copy map into bottom of final image
        imgFinal.paste(mapFinal, (0, imgFinal.size[1]-mapFinal.size[1]))
        del(mapFinal)
        # The top has 5632x1119
        # Getting fonts
        fontmini = ImageFont.truetype("src/GARA.TTF", 36)
        fontsmall = ImageFont.truetype("src/GARA.TTF", 50)
        font = ImageFont.truetype("src/GARA.TTF", 100)
        imgDraw = ImageDraw.Draw(imgFinal)
        #================MULTIPLAYER================#
        if True:  # mp == True:
            # Players section from (20,30) to (4710, 1100) half way is x=2345
            # So start with yborder = 38, yheight = 128 for each player row. x just make it half or maybe thirds depending on how it goes

            # Get the list of player Nations
            # TODO: make this more integrated with the new savefile data system rather than doing this conversion
            playerNationList: List[xNation] = []
            for x in self.game.playertags:
                playerNationList.append(self.game.allNations[x])
            playerNationList.sort(key=lambda x: x.development, reverse=True)

            # Put stuff on the board
            for nat in playerNationList:
                natnum = playerNationList.index(nat)
                # We have 2335 pixels to work with maximum for each player column
                x = 38 + 2335*int(natnum/8)
                y = 38 + 128*(natnum % 8)
                if (natnum < 16):
                    # x: Country flag
                    imgFinal.paste(EU4Lib.flag(nat.tag), (x, y))
                    # x+128: Player
                    playerName = self.game.playertags[nat.tag]
                    while (imgDraw.textsize(playerName, font)[0] > 760 - 128):
                        # Make sure the name isn't too long
                        playerName = playerName[:-1]
                    imgDraw.text((x+128, y), playerName, (255, 255, 255), font)
                    # x+760: Army size
                    imgFinal.paste(Image.open("src/army.png"), (x+760, y))
                    imgDraw.text((x+760+128, y),
                                 armyDisplay(nat.army), (255, 255, 255), font)
                    # x+1100: Navy size
                    imgFinal.paste(Image.open("src/navy.png"), (x+1100, y))
                    imgDraw.text((x+1100+128, y), str(nat.navy),
                                 (255, 255, 255), font)
                    # x+1440: Development
                    imgFinal.paste(Image.open(
                        "src/development.png"), (x+1440, y))
                    imgDraw.text((x+1440+128, y),
                                 str(nat.development), (255, 255, 255), font)
                    # x+1780: Income/Expense
                    monthlyProfit = nat.totalIncome-nat.totalExpense
                    imgIncome = Image.open("src/income.png")
                    if monthlyProfit < 0:
                        imgIncome = imgIncome.crop((128, 0, 255, 127))
                        imgFinal.paste(imgIncome, (x+1780, y))
                        imgDraw.text(
                            (x+1780+128, y), str(round(nat.totalIncome - nat.totalExpense)), (247, 16, 16), font)
                    else:
                        imgIncome = imgIncome.crop((0, 0, 127, 127))
                        imgFinal.paste(imgIncome, (x+1780, y))
                        imgDraw.text(
                            (x+1780+128, y), str(round(nat.totalIncome - nat.totalExpense)), (49, 190, 66), font)
                    imgDraw.text(
                        (x+2130, y), "+" + str(round(nat.totalIncome, 2)), (49, 190, 66), fontsmall)
                    imgDraw.text(
                        (x+2130, y+64), "-" + str(round(nat.totalExpense, 2)), (247, 16, 16), fontsmall)
                    # Possible TODO:
                    # navy_strength
                    # manpower
                    # max_manpower
                    # max_sailors
                else:
                    pass
            for playerWar in self.game.playerWars:
                warnum = self.game.playerWars.index(playerWar)
                if warnum < 4:
                    x = 4742
                    y = 230 + 218 * warnum
                    # Draw Attacker Flags
                    for nat in playerWar.playerAttackers(self.game.playertags):
                        natnum = playerWar.playerAttackers(
                            self.game.playertags).index(nat)
                        if natnum < 8:
                            imgFinal.paste(EU4Lib.flag(nat).resize((64, 64)), (round(x + 3 * (12 + 64) - (
                                natnum % 4) * (64 + 12)), round(y + (natnum - natnum % 4) / 4 * (64 + 12) + 12)))
                    # Draw Attacker Casualties
                    attackerIcon = Image.open(
                        "src/bodycount_attacker_button.png")
                    imgFinal.paste(
                        attackerIcon, (x + 290 - 12 - 32, y + 156), attackerIcon)
                    imgDraw.text((x + 290 - 12 - 32 - imgDraw.textsize("Losses: " + str(armyDisplay(playerWar.attackerLosses)), fontmini)[
                                 0], y + 152), "Losses: " + str(armyDisplay(playerWar.attackerLosses)), (255, 255, 255), fontmini)
                    # Draw Defender Flags
                    for nat in playerWar.playerDefenders(self.game.playertags):
                        natnum = playerWar.playerDefenders(
                            self.game.playertags).index(nat)
                        if natnum < 8:
                            imgFinal.paste(EU4Lib.flag(nat).resize((64, 64)), (round(
                                x + (natnum % 4) * (64 + 12) + 585), round(y + (natnum - natnum % 4) / 4 * (64 + 12) + 12)))
                    # Draw Defender Casualties
                    defenderIcon = Image.open(
                        "src/bodycount_defender_button.png")
                    imgFinal.paste(
                        defenderIcon, (x + 12 + 585, y + 156), defenderIcon)
                    imgDraw.text((x + 12 + 32 + 585, y + 152), "Losses: " + str(
                        armyDisplay(playerWar.defenderLosses)), (255, 255, 255), fontmini)
                    # Draw war details
                    remainingWords = playerWar.name.split()
                    lineLimit = 290  # pix/ln
                    nameStr = ""
                    for word in remainingWords:
                        if nameStr == "" or nameStr.endswith("\n"):
                            if imgDraw.textsize(word, fontmini)[0] >= lineLimit:
                                nameStr += word + "\n"
                            else:
                                nameStr += word
                        else:
                            if imgDraw.textsize(word, fontmini)[0] >= lineLimit:
                                nameStr += "\n" + word + "\n"
                            elif imgDraw.textsize(nameStr.split("\n")[-1] + " " + word, fontmini)[0] >= lineLimit:
                                nameStr += "\n" + word
                            else:
                                nameStr += " " + word
                    imgDraw.text((round(x + 437.5 - imgDraw.textsize(nameStr, fontmini)
                                        [0]/2), y + 12), nameStr, (255, 255, 255), fontmini, align="center")
                    dateStr = playerWar.startDate.split(
                        ".")[0] + "-" + playerWar.endDate.split(".")[0]
                    imgDraw.text((round(x + 437.5 - imgDraw.textsize(dateStr, fontmini)
                                        [0]/2), y + 115), dateStr, (255, 255, 255), fontmini, align="center")
                    # Draw result
                    if playerWar.result == 1:  # WP
                        WPIcon = Image.open("src/icon_peace.png")
                        imgFinal.paste(WPIcon, (x + 437 - 32, y + 140), WPIcon)
                    elif playerWar.result == 2:  # Attacker
                        WinnerIcon = Image.open("src/star.png")
                        imgFinal.paste(
                            WinnerIcon, (x + 290, y + 148), WinnerIcon)
                    elif playerWar.result == 3:  # Defender
                        WinnerIcon = Image.open("src/star.png")
                        imgFinal.paste(
                            WinnerIcon, (x + 12 + 585 - 48, y + 148), WinnerIcon)
        #================SINGLEPLAYER================#
        else:
            pass
        #================END  SECTION================#
        # Date
        year, month, day = self.game.date.split(".")
        gameDateStr = None
        if month == "1":
            gameDateStr = day + " January " + year
        elif month == "2":
            gameDateStr = day + " Feburary " + year
        elif month == "3":
            gameDateStr = day + " March " + year
        elif month == "4":
            gameDateStr = day + " April " + year
        elif month == "5":
            gameDateStr = day + " May " + year
        elif month == "6":
            gameDateStr = day + " June " + year
        elif month == "7":
            gameDateStr = day + " July " + year
        elif month == "8":
            gameDateStr = day + " August " + year
        elif month == "9":
            gameDateStr = day + " September " + year
        elif month == "10":
            gameDateStr = day + " October " + year
        elif month == "11":
            gameDateStr = day + " November " + year
        elif month == "12":
            gameDateStr = day + " December " + year
        imgDraw.text((round(5177 - imgDraw.textsize(gameDateStr, font)
                            [0] / 2), 60), gameDateStr, (255, 255, 255), font)
        return imgFinal

    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel and not message.author.bot

    async def process(self, message: discord.Message):
        if message.content.upper() == GuildManager.getGuildSave(self.displayChannel.guild, conn=conn).prefix + "CANCEL":
            await self.interactChannel.send("**Cancelling the stats operation.**")
            interactions.remove(self)
            del(self)
        elif not self.hasReadFile:  # First step - get .eu4 file
            saveFile: Optional[StringIO] = None
            if len(message.attachments) > 0 and message.attachments[0].filename.endswith(".eu4"):
                try:
                    saveFile = StringIO((await message.attachments[0].read()).decode("cp1252"))
                except:
                    await self.interactChannel.send("**Something went wrong in decoding your .eu4 file.**\nThis may mean your file is not an eu4 save file, or has been changed from the cp1252 encoding.\n**Please try another file or change the file's encoding and try again.**")
                    return
            else:  # str
                saveURL = message.content.strip("\n\t ")
                response = requests.get(saveURL)
                if response.status_code == 200:  # 200 == requests.codes.ok
                    try:
                        saveFile = StringIO(response.content.decode("cp1252"))
                    except Exception as e:
                        await self.interactChannel.send("**Something went wrong in decoding your .eu4 file.**\nThis may mean your file is not an eu4 save file, or has been changed from the cp1252 encoding.\n**Please try another file or change the file's encoding and try again.**\n```"+repr(e)+"```")
                        return
                else:
                    await self.interactChannel.send("Something went wrong. Please try a different link.")
                    return
            await self.interactChannel.send("**Recieved save file. Processing...**")
            try:
                await self.readFile(saveFile)
            except Exception as e:
                await self.interactChannel.send("**Uh oh! something went wrong.**\nIt could be that your save file was incorrectly formatted. Make sure it is uncompressed.\n**Please try another file.**\n```" + repr(e) + "```")
                return
            else:
                await self.interactChannel.send("**Send the Political Mapmode screenshot in this channel (png):**")
                self.hasReadFile = True
                del(saveFile)
        # Second step - get .png file
        elif self.hasReadFile and (self.politicalImage is None):
            if len(message.attachments) == 0:  # Check there is a file
                await self.interactChannel.send("File not recieved. Please send a file as a message attachment.")
            # Needs to be a .png file
            elif not message.attachments[0].filename.endswith(".png"):
                await self.interactChannel.send("File ending needs to be .png. Please send a .png EU4 player mapmode screenshot.")
            else:  # This means that all the checks succeeded
                politicalFile = BytesIO()
                await message.attachments[0].save(politicalFile)
                self.politicalImage = Image.open(politicalFile)
                del(politicalFile)
                if self.politicalImage.size != (5632, 2048):
                    await self.interactChannel.send("**Your image was not the right size.** (5632, 2048)\nDid you submit a Political Mapmode screenshot? (f10)\n**Please try another image.**")
                    self.politicalImage = None
                else:
                    self.modMsg = await self.interactChannel.send(self.modPromptStr())

        # Third step - player list modification
        elif self.hasReadFile and (self.politicalImage is not None) and (not self.doneMod):
            if message.content.strip("\n\t ") == "done":
                self.doneMod == True
                img = None
                # Create the Image and convert to discord.File
                # try:
                await self.interactChannel.send("**Generating Image...**")
                img = imageToFile(await self.generateImage())
                # except:
                #    await self.interactChannel.send("**Image generation failed!**\nPerhaps something was wrong with one of the files?\n**Try " + GuildManager.getGuildSave(self.displayChannel.guild, conn = conn).prefix + "stats again after checking that the files are valid and unchanged from their creation.**")
                # else: # That was successful, now post!
                try:
                    await self.interactChannel.send("**Image generation complete...**")
                    await self.displayChannel.send(file=img)
                except discord.Forbidden:  # If we're not allowed to send on the server, just give it in dms. They can post it themselves; this will reduce the server load
                    await self.interactChannel.send("**Unable to send the image to " + self.displayChannel.mention + " due to lack of permissions. Posting image here:**\nYou can right-click and copy link then post that.", file=imageToFile(img))
                else:
                    await self.interactChannel.send("**Image posted to " + self.displayChannel.mention + "**")
                interactions.remove(self)
                del(self)
            # add [player], [nation]
            elif message.content.strip("\n\t ").startswith("add "):
                player = message.content.strip("\n\t ").partition(
                    " ")[2].partition(",")[0].strip("\t\n ")
                natName = message.content.strip("\n\t ").partition(",")[
                    2].strip("\t\n ")
                tag = EU4Lib.country(natName)
                if tag is None:
                    await sendUserMessage(self.user, "Nation " + natName + " not recognized.")
                elif tag in self.game.playertags:
                    await sendUserMessage(self.user, EU4Lib.tagToName(tag) + " is already played. If you wish to replace the player, please remove it first.")
                elif not tag in self.game.allNations:
                    await sendUserMessage(self.user, EU4Lib.tagToName(tag) + " does not exist in this game.")
                else:
                    self.game.playertags[tag] = player
                    await sendUserMessage(self.user, "Added " + EU4Lib.tagToName(tag) + " for " + player + ".")
            # remove [nation]
            elif message.content.strip("\n\t ").startswith("remove "):
                name = message.content.strip("\n\t ").partition(" ")[2].strip("\t\n ")
                tag = EU4Lib.country(name)
                if tag is None:
                    await self.interactChannel.send("Did not recognize \"" + name + "\" as a valid nation.")
                elif tag in self.game.playertags:
                    del(self.game.playertags[tag])
                    await sendUserMessage(self.user, "Removed " + EU4Lib.tagToName(tag) + ".")
                else:
                    await self.interactChannel.send("Did not recognize " + tag.upper() + " as a played nation.")

    async def msgdel(self, msgID: Union[str, int]):
        pass

    async def userdel(self, user: DiscUser):
        if user == self.user:
            try:  # If this fails, it probably means the account was deleted. We still should delete.
                await self.interactChannel.send("You left the " + self.displayChannel.guild.name + " discord server, so this stats interaction has been cancelled.")
            finally:
                interactions.remove(self)
                del(self)


class asiFaction:
    """Represents a faction for an ASI game."""

    def __init__(self, name: str, territory: List[str], maxPlayers: int = 256):
        self.name = name
        self.territory = territory
        self.maxPlayers = maxPlayers
        self.taken = 0

    def isInTerritory(self, provinceID: Union[str, int]) -> bool:
        """Returns whether or not the given province is within this faction's territory."""
        for land in self.territory:
            if EU4Lib.isIn(provinceID, land):
                return True
        return False


# This is custom for my discord group. Anybody else can ignore it or do what you will.
class asiresChannel(AbstractChannel):
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels, Load=False, textID: int = None):
        self.user = None
        self.interactChannel = initChannel
        self.displayChannel = initChannel
        self.textID: Optional[int] = textID
        self.factions: List[asiFaction] = []
        self.factions.append(asiFaction("West", ["france_region", "british_isles_region", "iberia_region", "corsica_sardinia_area",
                                                 "piedmont_area", "liguria_area", "tuscany_area", "naples_area", "calabria_area", "sicily_area"], 4))
        self.factions.append(asiFaction("East", ["low_countries_region", "north_german_region", "south_german_region", "scandinavia_region", "poland_region", "baltic_region",
                                                 "russia_region", "ruthenia_region", "carpathia_region", "venetia_area", "lombardy_area", "emilia_romagna_area", "apulia_area", "central_italy_area"]))
        self.factions.append(asiFaction("Mid", [
                             "balkan_region", "near_east_superregion", "persia_superregion", "egypt_region", "maghreb_region"]))
        self.factions.append(asiFaction(
            "India", ["india_superregion", "burma_region"]))
        self.factions.append(asiFaction("Asia", ["china_superregion", "tartary_superregion", "far_east_superregion",
                                                 "malaya_region", "moluccas_region", "indonesia_region", "indo_china_region", "oceania_superregion"], 3))
        if not Load:
            EU4Reserve.addReserve(EU4Reserve.ASIReserve(
                str(self.displayChannel.id)), conn=conn)

    def prefix(self) -> str:
        return GuildManager.getGuildSave(self.interactChannel.guild, conn=conn).prefix

    def getFaction(self, provinceID: Union[str, int]) -> Optional[asiFaction]:
        """Returns the faction that owns a given province.

        This should only be one faction, but if more than one have the province in their territory list,, only the first faction with the territory on its list will be returned.
        """
        for faction in self.factions:
            if faction.isInTerritory(provinceID):
                return faction
        return None

    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel

    async def process(self, message: discord.Message):
        text = message.content.strip("\n\t ")
        if text.upper() == self.prefix() + "HELP":
            stringHelp = "__**Command help for " + message.channel.mention + ":**__"
            stringHelp += "\n**" + self.prefix() + "HELP**\nGets you this information!"
            stringHelp += "\n**" + self.prefix() + \
                "RESERVE [nation1], [nation2], [nation3]**\nReserves your picks or overwrites your previous reservation.\nThese are in the order of first pick to third. Don't include the brackets."
            stringHelp += "\n**" + self.prefix() + "DELRESERVE**\nCancels your reservation."
            # Here we send info about commands only for admins
            if checkResAdmin(message.guild, message.author):
                stringHelp += "\n**" + self.prefix() + "END**\nStops allowing reservations and stops the bot's channel management.\nThen runs and displays the draft. Draft may need to be rearranged manually to ensure game balance."
                stringHelp += "\n**" + self.prefix() + \
                    "ADMRES [nation1], [nation2], [nation3] [@user]**\nReserves picks on behalf of a player on the server.\nMake sure to actually @ the player."
                stringHelp += "\n**" + self.prefix() + \
                    "EXECRES [nation] [optional @user]**\nReserves a pick on behalf of yourself or another player on the server.\nEnsures that this player gets the reservation first."
                stringHelp += "\n**" + self.prefix() + \
                    "ADMDELRES [@user]**\nDeletes a player's reservation.\nMake sure to actually @ the player."
                stringHelp += "\n**" + self.prefix() + \
                    "UPDATE**\nUpdates the reservations list. Should usually not be necessary unless in debug or something went wrong."
            await message.delete()
            await sendUserMessage(message.author, stringHelp)
        elif text.upper() == self.prefix() + "UPDATE" and checkResAdmin(message.guild, message.author):  # UPDATE
            await message.delete()
            await self.updateText()
        elif text.upper() == self.prefix() + "END" and checkResAdmin(message.guild, message.author):  # END
            await message.delete()
            reserves = EU4Reserve.getReserve(
                str(self.displayChannel.id), conn=conn).players
            finalReserves: List[EU4Reserve.reservePick] = []
            # This stores the capitals of all possible tags, so that their factions can be determined.
            tagCapitals = dict()
            # Add all possibly reserved nations to the tagCapitals dictionary with a capital of -1
            for res in reserves:
                for tag in res.picks:
                    if tagCapitals.get(tag.upper()) is None:
                        tagCapitals[tag.upper()] = -1
            # Get the actual capitals and add to tagCapitals.
            srcFile = open("src/save_1444.eu4", "r", encoding="cp1252")
            lines = srcFile.readlines()
            brackets = []
            linenum = 0
            for line in lines:
                linenum += 1
                if "{" in line:
                    if line.count("{") == line.count("}"):
                        continue
                    elif line.count("}") == 0 and line.count("{") == 1:
                        brackets.append(line.rstrip("\n "))
                    elif line.count("}") == 0 and line.count("{") > 1:
                        for x in range(line.count("{")):
                            # TODO: fix this so it has more
                            brackets.append("{")
                    else:
                        print("Unexpected brackets at line #" +
                              str(linenum) + ": " + line)
                elif "}" in line:
                    try:
                        brackets.pop()
                    except IndexError:  # This shouldn't happen.
                        print("No brackets to delete.")
                        print("Line", linenum, ":", line)
                elif len(brackets) > 1 and brackets[0] == "countries={":
                    for x in tagCapitals:
                        if x in brackets[1]:
                            # Here we have all the stats for country x on the players list
                            if len(brackets) == 2 and "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                                tagCapitals[x] = int(line.strip("\tcapitl=\n"))
            srcFile.close()
            # Draft Executive Reserves
            for res in reserves:
                if res.priority:
                    finalReserves.append(EU4Reserve.reservePick(
                        res.player, res.picks[0].upper()))
                    self.getFaction(
                        tagCapitals[res.picks[0].upper()]).taken += 1
                    reserves.remove(res)
            # Shuffle
            shuffle(reserves)
            # Draft Reserves
            for res in reserves:
                finaltag = None
                for tag in res.picks:
                    resFaction = self.getFaction(tagCapitals[tag.upper()])
                    # if faction is full, skip to next one
                    if (resFaction is None) or (resFaction.taken >= resFaction.maxPlayers):
                        continue
                    # If already taken, don't add (skip)
                    for x in finalReserves:
                        if (x.tag.upper() == tag.upper()):
                            break
                    else:  # This means they get this tag
                        finaltag = tag
                        resFaction.taken += 1
                        break
                finalReserves.append(
                    EU4Reserve.reservePick(res.player, finaltag))
            # At this point the finalReserves list is complete with all finished reserves. If a player had no reserves they could take, their tag is None
            string = "**Reserves are finished. The following are the draft order:**"
            count = 1
            for res in finalReserves:
                if res.tag is None:
                    string += "\n" + str(count) + " " + \
                        res.player + ": *[all taken]*"
                else:
                    t = EU4Lib.tagToName(res.tag)
                    if t is not None:
                        string += "\n" + str(count) + " " + \
                            res.player + ": " + t
                    else:
                        string += "\n" + str(count) + " " + \
                            res.player + ": " + res.tag
                count += 1
            await self.displayChannel.send(string)
            # aaand we're done!
            EU4Reserve.deleteReserve(str(self.displayChannel.id), conn=conn)
            interactions.remove(self)
            del(self)
        elif text.upper().startswith(self.prefix() + "RESERVE "):
            # RESERVE [nation1], [nation2], [nation3]
            await self.add(message.author, text.split(" ", 1)[1].strip("\n\t "))
            await message.delete()
            await self.updateText()
        # ADMRES [nation1], [nation2], [nation3] @[player]
        elif text.upper().startswith(self.prefix() + "ADMRES") and checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                res = text.split(maxsplit=1)[1].strip("\n\t <@!1234567890>")
                picks = res.split(",")
                if not len(picks) == 3:
                    await sendUserMessage(message.author, "Your reserve in " + self.interactChannel.mention + " for " + message.mentions[0].mention + " needs to be 3 elements in the format 'a,b,c'")
                    await message.delete()
                    return
                for pick in picks:
                    if EU4Lib.country(pick.strip("\n\t ")) is None:
                        await sendUserMessage(message.author, "Your reservation of " + pick.strip("\n\t ") + " in " + self.interactChannel.mention + " for " + message.mentions[0].mention + " was not a recognized nation.")
                        await message.delete()
                        return
                # at this point the reservation should be valid, because otherwise add will send the faliure to the target.
                await self.add(message.mentions[0], res)
                await self.updateText()
            else:
                await sendUserMessage(message.author, "Your reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        # ADMRES [nation] @[optional_player]
        elif text.upper().startswith(self.prefix() + "EXECRES") and checkResAdmin(message.guild, message.author):
            res = text.split(maxsplit=1)[1].strip("\n\t <@!1234567890>")
            user: Optional[DiscUser] = None
            if len(message.mentions) == 0:
                user = message.author
            else:
                user = message.mentions[0]
            pick = EU4Lib.country(res)
            if pick is None:  # Nation is invalid; tag not found.
                await sendUserMessage(message.author, "Your reservation of " + res.strip("\n\t ") + " in " + self.interactChannel.mention + " for " + user.mention + " was not a recognized nation.")
                await message.delete()
                return
            # Now reserve
            await message.delete()
            reserve = EU4Reserve.asiPick(user.mention, priority=True)
            reserve.picks = [pick]
            await self.remove(user)
            addInt = EU4Reserve.addPick(
                str(self.displayChannel.id), reserve, conn=conn)
            if addInt == 3:
                await sendUserMessage(message.author, EU4Lib.tagToName(pick) + " is already executive-reserved in " + message.channel.mention)
            elif addInt == 1 or addInt == 2:
                await self.updateText()
        elif text.upper() == self.prefix() + "DELRESERVE" or text.upper() == self.prefix() + "DELETERESERVE":  # DELRESERVE
            await self.remove(message.author)
            await message.delete()
            await self.updateText()
        # ADMDELRES @[player]
        elif text.upper().startswith(self.prefix() + "ADMDELRES") and checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                await self.remove(message.mentions[0].mention)
                await self.updateText()
            else:
                await sendUserMessage(message.author, "Your deletion of a reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        else:
            await message.delete()

    async def updateText(self):
        string = "How to reserve: " + self.prefix() + \
            "reserve [nation1], [nation2], [nation3]\nTo unreserve: " + \
            self.prefix() + "delreserve\n**Current players list:**"
        picks = EU4Reserve.getReserve(
            str(self.displayChannel.id), conn=conn).players
        if len(picks) == 0:
            string += "\n*It's so empty here...*"
        else:
            picks.sort(key=lambda x: x.time)
            for x in picks:
                if x.priority:
                    string += "\n" + x.player + ": **" + \
                        EU4Lib.tagToName(x.picks[0]) + "**"
                else:
                    string += "\n" + x.player + ": " + EU4Lib.tagToName(
                        x.picks[0]) + ", " + EU4Lib.tagToName(x.picks[1]) + ", " + EU4Lib.tagToName(x.picks[2]) + " | " + x.timeStr()
        if self.textID is None:
            self.textID = (await self.displayChannel.send(content=string)).id
            EU4Reserve.updateMessageIDs(
                str(self.displayChannel.id), textmsg=self.textID, conn=conn)
        else:
            await (await (self.displayChannel).fetch_message(self.textID)).edit(content=string)

    async def remove(self, user: DiscUser):
        EU4Reserve.deletePick(str(self.displayChannel.id),
                              user.mention, conn=conn)

    async def add(self, user: DiscUser, text: str):
        picks = text.split(",")
        if not len(picks) == 3:
            await sendUserMessage(user, "Your reserve in " + self.interactChannel.mention + " needs to be 3 elements in the format 'a,b,c'")
            return
        tags = []
        for pick in picks:
            tag = EU4Lib.country(pick.strip("\n\t "))
            if tag is not None:
                tags.append(tag)
            else:
                await sendUserMessage(user, "Your reservation of " + pick.strip("\n\t ") + " in " + self.interactChannel.mention + " was not a recognized nation.")
                return
        res = EU4Reserve.asiPick(user.mention)
        res.picks = tags
        await self.remove(user)
        EU4Reserve.addPick(str(self.displayChannel.id), res, conn=conn)

    async def msgdel(self, msgID: Union[str, int]):
        if msgID == self.textID:
            self.textID = None
            await self.updateText()

    async def userdel(self, user: DiscUser):
        await self.remove(user)
        await self.updateText()


# DISCORD CODE
interactions: List[AbstractChannel] = []


@client.event
async def on_ready():
    print("EU4 Reserve Bot!")
    print("Registering connected Guilds not yet registered...")
    newGuildCount = 0
    async for guild in client.fetch_guilds():
        if GuildManager.getGuildSave(guild, conn=conn) is None:
            GuildManager.addGuild(guild, conn=conn)
            newGuildCount += 1
    print("Registered " + str(newGuildCount) + " new Guilds.")
    print("Loading previous Reserves...")
    reserves = EU4Reserve.load(conn=conn)
    rescount = 0
    closedcount = 0
    for res in reserves:
        reschannel: DiscTextChannels = client.get_channel(int(res.name))
        if reschannel is None:
            EU4Reserve.deleteReserve(res, conn=conn)
            closedcount += 1
        else:
            if isinstance(res, EU4Reserve.Reserve):
                # Check that the textmsg still exists
                try:
                    await reschannel.fetch_message(res.textmsg)
                except:  # The message either doesn't exist or can't be reached by the bot
                    textmsg = None
                else:  # The message is accessable.
                    textmsg = res.textmsg
                # Check that the imgmsg still exists
                try:
                    await reschannel.fetch_message(res.imgmsg)
                except:  # The message either doesn't exist or can't be reached by the bot
                    imgmsg = None
                else:  # The message is accessable.
                    imgmsg = res.imgmsg
                # Create
                interactions.append(ReserveChannel(
                    None, reschannel, Load=True, textID=textmsg, imgID=imgmsg))
                # Update if anything was deleted
                if textmsg is None:
                    await interactions[-1].updateText()
                    await interactions[-1].updateImg()
                elif imgmsg is None:
                    await interactions[-1].updateImg()
            elif isinstance(res, EU4Reserve.ASIReserve):
                # Check that the textmsg still exists
                try:
                    await reschannel.fetch_message(res.textmsg)
                except:  # The message either doesn't exist or can't be reached by the bot
                    textmsg = None
                else:  # The message is accessable.
                    textmsg = res.textmsg
                # Create
                interactions.append(asiresChannel(
                    None, reschannel, Load=True, textID=textmsg))
                # Update if anything was deleted
                if textmsg is None:
                    await interactions[-1].updateText()
            rescount += 1
    print("Loaded " + str(rescount) + " channels and removed " +
          str(closedcount) + " no longer existing channels.")
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for new lands"))


@client.event
async def on_message(message: discord.Message):
    if not message.author.bot:
        text = message.content.strip("\n\t ")
        for interaction in interactions:  # Should be only abstractChannel descendants
            if await interaction.responsive(message):
                await interaction.process(message)
                return
        if (message.guild is not None and text.startswith(GuildManager.getGuildSave(message.guild, conn=conn).prefix)):
            prefix = GuildManager.getGuildSave(message.guild, conn=conn).prefix
            if text.upper() == prefix + "HELP":
                stringHelp = "__**Command help:**__"
                stringHelp += "\n**" + prefix + "HELP**\nGets you this information!"
                # Here we send info about commands only for admins
                if checkResAdmin(message.guild, message.author):
                    stringHelp += "\n**" + prefix + \
                        "NEW**\nTurns the text channel into a reservation channel\n(more commands within that; use this command in it for info)"
                    stringHelp += "\n**" + prefix + \
                        "STATS**\nCreates a eu4 stats image in the channel.\nUses DMs to gather the necessary files for creation."
                    stringHelp += "\n**" + prefix + \
                        "NEWASI**\nTurns the text channel into a ASI reservation channel\nThis is specific to my discord."
                    stringHelp += "\n**" + prefix + \
                        "PREFIX [prefix]**\nChanges the bot prefix on this server."
                    stringHelp += "\n**" + prefix + \
                        "ADMINRANK [@rank]**\nChanges the minimum rank necessary for admin control of the bot.\nPlease be sure before changing this. The highest rank can always control the bot.\nThe @ is optional in specifying the rank."
                    stringHelp += "\n**" + prefix + \
                        "ADDDEFAULTBAN [nation], [nation], ...**\nAdds nations to the default ban list for the server. When a new reserve channel is created, this list will be copied into that channel's ban list. The channel ban list may be changed separately thereafter."
                    stringHelp += "\n**" + prefix + \
                        "DELDEFAULTBAN [nation], [nation], ...**\nRemoves nations from the default ban list for the server. As many nations as needed may be changed in one command, with commas between them."
                await message.delete()
                await sendUserMessage(message.author, stringHelp)
            elif (text.upper() == prefix + "NEW") and checkResAdmin(message.guild, message.author):
                c = ReserveChannel(message.author, message.channel)
                await message.delete()
                await c.updateText()
                await c.updateImg()
                interactions.append(c)
            elif text.upper() == prefix + "STATS" and checkResAdmin(message.guild, message.author):
                interactions.append(await statsChannel(message.author, message.channel).asyncInit())
                await message.delete()
            elif text.upper() == prefix + "NEWASI" and checkResAdmin(message.guild, message.author):
                c = asiresChannel(message.guild, message.channel)
                await message.delete()
                await c.updateText()
                interactions.append(c)
            elif text.upper() == prefix + "LOAD" and checkResAdmin(message.guild, message.author):
                res = EU4Reserve.getReserve(str(message.channel.id), conn=conn)
                if res is None:
                    await sendUserMessage(message.author, "You tried to load a save in " + message.channel.mention + " but no save was found. Please try " + prefix + "NEW to create new reserves.")
                elif isinstance(res, EU4Reserve.Reserve):
                    c = ReserveChannel(
                        message.author, message.channel, Load=True)
                    await message.delete()
                    await c.updateText()
                    await c.updateImg()
                    interactions.append(c)
                elif isinstance(res, EU4Reserve.ASIReserve):
                    c = asiresChannel(
                        message.guild, message.channel, Load=True)
                    await message.delete()
                    await c.updateText()
                    interactions.append(c)
            elif text.upper().startswith(prefix + "PREFIX") and checkResAdmin(message.guild, message.author):
                newPrefix = text.partition(" ")[2].strip("\n\t ")
                if len(newPrefix) < 1:
                    await sendUserMessage(message.author, "The prefix must be at least 1 character.")
                elif any(char.isalpha() for char in newPrefix):
                    await sendUserMessage(message.author, "The prefix cannot contain letters.")
                else:
                    GuildManager.setPrefix(message.guild, newPrefix, conn=conn)
                    await sendUserMessage(message.author, "Prefix on " + message.guild.name + " set to " + newPrefix)
                await message.delete()
            elif text.upper().startswith(prefix + "ADMINRANK") and checkResAdmin(message.guild, message.author):
                if len(message.role_mentions) > 0:
                    newRank = message.role_mentions[0]
                else:
                    newRank = getRoleFromStr(
                        message.guild, text.partition(" ")[2].strip("\n\t "))
                if newRank is None:
                    await sendUserMessage(message.author, "The rank " + text.partition(" ")[2].strip("\n\t ") + " is not a valid rank on " + message.guild.name)
                else:
                    GuildManager.setAdmin(
                        message.guild, newRank.name, conn=conn)
                    await sendUserMessage(message.author, "Admin rank set to " + newRank.name + " on " + message.guild.name)
                await message.delete()
            # ADDDEFAULTBAN [nation], [nation], ...
            elif text.upper().startswith(prefix + "ADDDEFAULTBAN") and checkResAdmin(message.guild, message.author):
                bannations = text.partition(" ")[2].strip("\n\t ,").split(",")
                bantags = []
                fails = []
                for bannat in bannations:
                    tag = EU4Lib.country(bannat.strip("\n\t ,"))
                    if tag is not None:
                        bantags.append(tag)
                    else:
                        fails.append(bannat)
                string = ""
                if len(bantags) > 0:
                    string += "Added the following nations to the default ban list in " + \
                        message.guild.name + ": "
                    for tag in bantags:
                        GuildManager.addBan(message.guild, tag, conn=conn)
                        string += EU4Lib.tagToName(tag)
                        if tag is not bantags[-1]:
                            string += ", "
                if len(fails) > 0:
                    string += "\nDid not recognize the following nations: "
                    for tag in fails:
                        string += tag
                        if tag is not fails[-1]:
                            string += ", "
                    string += "\nThe unrecognized nations were not added to the default ban list."
                if string != "":
                    string += "\nThe new default ban list: "
                    newbanlist = GuildManager.getGuildSave(
                        message.guild, conn=conn).defaultBan
                    for tag in newbanlist:
                        string += EU4Lib.tagToName(tag)
                        if tag is not newbanlist[-1]:
                            string += ", "
                    await sendUserMessage(message.author, string)
                await message.delete()
            # DELDEFAULTBAN [nation], [nation], ...
            elif text.upper().startswith(prefix + "DELDEFAULTBAN") and checkResAdmin(message.guild, message.author):
                bannations = text.partition(" ")[2].strip("\n\t ,").split(",")
                bantags = []
                fails = []
                for bannat in bannations:
                    tag = EU4Lib.country(bannat.strip("\n\t ,"))
                    if tag is not None:
                        bantags.append(tag)
                    else:
                        fails.append(bannat)
                string = ""
                if len(bantags) > 0:
                    string += "Removed the following nations from the default ban list in " + \
                        message.guild.name + ": "
                    for tag in bantags:
                        GuildManager.removeBan(message.guild, tag, conn=conn)
                        string += EU4Lib.tagToName(tag)
                        if tag is not bantags[-1]:
                            string += ", "
                if len(fails) > 0:
                    string += "\nDid not recognize the following nations: "
                    for tag in fails:
                        string += tag
                        if tag is not fails[-1]:
                            string += ", "
                    string += "\nThe unrecognized nations were not removed from the default ban list."
                if string != "":
                    string += "\nThe new default ban list: "
                    newbanlist = GuildManager.getGuildSave(
                        message.guild, conn=conn).defaultBan
                    for tag in newbanlist:
                        string += EU4Lib.tagToName(tag)
                        if tag is not newbanlist[-1]:
                            string += ", "
                    await sendUserMessage(message.author, string)
                await message.delete()


@client.event
async def on_guild_channel_delete(channel: DiscTextChannels):
    for c in interactions:
        if c.displayChannel == channel or c.interactChannel == channel:
            if isinstance(c, ReserveChannel) or isinstance(c, asiresChannel):
                EU4Reserve.deleteReserve(str(c.displayChannel.id), conn=conn)
            interactions.remove(c)
            del(c)


@client.event
async def on_private_channel_delete(channel: DiscTextChannels):
    for c in interactions:
        if c.displayChannel == channel or c.interactChannel == channel:
            interactions.remove(c)
            del(c)


@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    for c in interactions:
        await c.msgdel(payload.message_id)


@client.event
async def on_member_remove(member: DiscUser):
    for c in interactions:
        await c.userdel(member)


@client.event
async def on_guild_join(guild: discord.Guild):
    GuildManager.addGuild(guild, conn=conn)


@client.event
async def on_guild_remove(guild: discord.Guild):
    GuildManager.removeGuild(guild, conn=conn)
    for c in interactions:
        if (hasattr(c.displayChannel, 'guild') and c.displayChannel.guild == guild) or (hasattr(c.interactChannel, 'guild') and c.interactChannel.guild == guild):
            if isinstance(c, ReserveChannel) or isinstance(c, asiresChannel):
                EU4Reserve.deleteReserve(str(c.displayChannel.id), conn=conn)
            interactions.remove(c)
            del(c)

client.run(token)
