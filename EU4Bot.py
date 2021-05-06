import asyncio
import json
import os
import traceback
import zlib
from abc import ABC, abstractmethod
from io import BytesIO, StringIO
from random import shuffle
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import cppimport
import discord
from discord.errors import DiscordException
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

import EU4Lib
import EU4Reserve
import GuildManager
import Skanderbeg

print("Compiling C++ modules...")
try:
    EU4cpplib = cppimport.imp("EU4cpplib")
except Exception as e:
    cppcompiled = False
    print("C++ module compilation failed.")
    print(traceback.print_exc())
else:
    cppcompiled = True
    print("C++ module compilation successful.")


# Load Discord Client
load_dotenv()
token: str = os.getenv("DISCORD_TOKEN")
intents: discord.Intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
session: aiohttp.ClientSession = None

# Load Skanderbeg key if it exists
SKANDERBEGKEY = os.getenv("SKANDERBEG_KEY")
if SKANDERBEGKEY == "" or SKANDERBEGKEY.isspace():
    SKANDERBEGKEY = None

# Create reused typing Unions
DiscUser = Union[discord.User, discord.Member]
DiscTextChannels = Union[discord.TextChannel,
                         discord.DMChannel, discord.GroupChannel]


def imageToFile(img: Image.Image) -> discord.File:
    """
    Comverts PIL Images into discord File objects.
    """
    file = BytesIO()
    img.save(file, "PNG")
    file.seek(0)
    return discord.File(file, "img.png")


async def sendUserMessage(user: Union[str, int, DiscUser], message: str) -> discord.Message:
    """
    Sends a user a specified DM via discord. Returns the discord Message object sent.
    """
    u: DiscUser = None
    if isinstance(user, str) or isinstance(user, int):  # id
        u: DiscUser = client.get_user(int(user))
    elif isinstance(user, discord.User) or isinstance(user, discord.Member):
        u: DiscUser = user
    else:
        raise TypeError(f"Invalid type for user. Invalid object: {user}")
    if u.dm_channel is None:
        await u.create_dm()
    msg = await u.dm_channel.send(message)
    return msg


def getRoleFromStr(server: Union[str, int, discord.Guild], roleName: str) -> Optional[discord.Role]:
    """
    Converts a string into the role on a specified discord server.
    Use an '@role' string as the roleName argument. (@ is optional)
    Returns None if the role cannot be found.
    """
    if roleName is None:
        return None
    # Get server object
    s: discord.Guild = None
    if isinstance(server, str) or isinstance(server, int):
        s: discord.Guild = client.get_guild(int(server))
    elif isinstance(server, discord.Guild):
        s: discord.Guild = server
    else:
        raise TypeError(
            f"Invalid type for Discord server. Invalid object: {server}")
    for role in s.roles:
        if role.name.strip("\n\t @").lower() == roleName.strip("\n\t @").lower():
            return role
    return None


async def findUser(id: Union[int, str]) -> discord.User:
    id = int(id)
    author = client.get_user(id)
    if author is None:
        try:
            author = await client.fetch_user(id)
        except discord.NotFound:
            raise ValueError(f"Could not find discord user with ID {id}")
    return author


async def findMember(id: Union[int, str], guild: discord.Guild) -> Optional[discord.Member]:
    id = int(id)
    member = guild.get_member(id)
    if member is None:
        try:
            member = await guild.fetch_member(id)
        except discord.Forbidden:
            raise ValueError(
                f"Could not access the guild to find member with user ID {id}")
        except discord.HTTPException:
            return None
    return member


async def findChannel(id: Union[int, str]) -> DiscTextChannels:
    id = int(id)
    textc = client.get_channel(id)
    if textc is None:
        try:
            textc = await client.fetch_channel(id)
        except discord.NotFound:
            raise ValueError(f"Could not find discord channel with ID {id}")
        except discord.Forbidden:
            raise ValueError(
                f"Permission was denied when fetching discord channel with ID {id}")
    return textc


async def findGuild(id: Union[int, str]) -> discord.Guild:
    id = int(id)
    guild = client.get_guild(id)
    if guild is None:
        try:
            guild = await client.fetch_guild(id)
        except discord.Forbidden:
            raise ValueError(f"Could not access discord guild with ID {id}")
    return guild


async def checkResAdmin(server: Union[str, int, discord.Guild], user: Union[str, int, DiscUser]) -> bool:
    """
    Returns whether or not a user has bot admin control roles on a server.
    """
    # Get server object
    s: discord.Guild = None
    if isinstance(server, str) or isinstance(server, int):
        s: discord.Guild = await findGuild(server)
    elif isinstance(server, discord.Guild):
        s: discord.Guild = server
    else:
        raise TypeError(
            f"Invalid type for Discord server. Invalid object: {server}")
    # Get member object
    u: discord.Member = None
    if isinstance(user, str) or isinstance(user, int):  # id
        u: DiscUser = await findMember(user, s)
    elif isinstance(user, discord.User):
        u: DiscUser = await findMember(user.id, s)
    elif isinstance(user, discord.Member):
        u: DiscUser = user
    else:
        raise TypeError(
            f"Invalid type for Discord member. Invalid object: {user}")
    # OK now check
    try:
        role = s.get_role(GuildManager.getAdmin(s))
    except TypeError:
        role = None
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
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels, textID: Optional[int] = None, imgID: Optional[int] = None):
        self.user = None
        self.interactChannel = initChannel
        self.displayChannel = initChannel
        self.reserve: EU4Reserve.Reserve = EU4Reserve.Reserve(initChannel.id)
        self.textID = textID
        self.imgID = imgID

    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel

    @property
    def textID(self) -> Optional[int]:
        if hasattr(self, "_textID"):
            return self._textID
        return self.reserve.textID

    @property
    def imgID(self) -> Optional[int]:
        if hasattr(self, "_imgID"):
            return self._imgID
        return self.reserve.imgID

    @textID.setter
    def textID(self, id: int):
        self._textID = id
        self.reserve.textID = id

    @imgID.setter
    def imgID(self, id: int):
        self._imgID = id
        self.reserve.imgID = id

    async def process(self, message: discord.Message):
        text: str = message.content.strip()
        if text.upper() == "HELP":  # HELP
            stringHelp = f"__**Command help for {message.channel.mention}:**__"
            stringHelp += "\n**HELP**\nGets you this information!"
            stringHelp += "\n**RESERVE [nation]**\nReserves a nation or overwrites your previous reservation. Don't include the brackets."
            stringHelp += "\n**DELRESERVE**\nCancels your reservation."
            # Here we send info about commands only for admins
            if await checkResAdmin(message.guild, message.author):
                stringHelp += "\n**END**\nStops allowing reservations and stops the bot's channel management.\nThis should be done by the time the game starts."
                stringHelp += "\n**ADMRES [nation] [@user]**\nReserves a nation on behalf of a player on the server.\nMake sure to actually @ the player. This ignores the ban list."
                stringHelp += "\n**ADMDELRES [@user]**\nDeletes a player's reservation.\nMake sure to actually @ the player."
                stringHelp += "\n**UPDATE**\nUpdates the reservations list. Should usually not be necessary unless in debug or something went wrong."
                stringHelp += "\n**ADDBAN [nation], [nation], ... **\nAdds countries to the ban list. Add commas between each entry if there are more than one."
                stringHelp += "\n**DELBAN [nation], [nation], ... **\nRemoves countries from the ban list. Add commas between each entry if there are more than one."
            await message.delete()
            await sendUserMessage(message.author, stringHelp)
        elif text.upper() == "UPDATE" and await checkResAdmin(message.guild, message.author):  # UPDATE
            await message.delete()
            await self.updateText()
            await self.updateImg()
        elif text.upper() == "END" and await checkResAdmin(message.guild, message.author):  # END
            await message.delete()
            # Load the reserve
            string = "**Final players list:**"
            # Text String - Players
            if self.reserve.countPlayers() == 0:
                string += "\n*It's so empty here...*"
            else:
                players = self.reserve.getPlayers()
                players.sort(key=lambda x: x.time)
                for x in players:
                    string += f"\n{x.userID}: {EU4Lib.tagToName(x.tag)} | {x.timeStr()}"
            # Update the message or send a new one if nonexistant
            try:
                await (await self.displayChannel.fetch_message(self.textID())).edit(content=string)
            except:
                pass
            await self.displayChannel.send("*Reservations are now ended. Good Luck.*")
            self.reserve.delete()
            controlledChannels.remove(self)
            del(self)
        # RESERVE [nation]
        elif text.upper().startswith("RESERVE "):
            res = text[text.index(" ")+1:].strip()
            tag = EU4Lib.country(res)
            if tag is not None:
                if self.reserve.isBan(tag):
                    await sendUserMessage(message.author, f"You may not reserve {EU4Lib.tagToName(tag)} in {self.displayChannel.mention} because it is banned. If you still want to play it, please have an admin override.")
                else:
                    await self.add(EU4Reserve.reservePick(message.author.id, tag))
            else:
                await sendUserMessage(message.author, f"Your country reservation in {self.displayChannel.mention} was not recorded, as \"{res}\" was not recognized.")
            await message.delete()
        # ADMRES [nation] @[player]
        elif text.upper().startswith("ADMRES") and await checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                res = text[text.index(" ")+1:].strip("\n\t <@!1234567890>")
                tag = EU4Lib.country(res)
                if tag is not None:
                    await self.add(EU4Reserve.reservePick(message.mentions[0].id, tag.upper()))
                else:
                    await sendUserMessage(message.author, f"Your reservation for {message.mentions[0].mention} in {self.displayChannel.mention} was not recorded, as \"{res}\" was not recognized.")
            else:
                await sendUserMessage(message.author, f"Your reservation in {self.displayChannel.mention} needs to @ a player.")
            await message.delete()
        # DELRESERVE
        elif text.upper() == "DELRESERVE" or text.upper() == "DELETERESERVE":
            await self.removePlayer(message.author.id)
            await message.delete()
        # ADMDELRES @[player]
        elif text.upper().startswith("ADMDELRES") and await checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                await self.removePlayer(message.mentions[0].id)
            else:
                await sendUserMessage(message.author, f"Your deletion of a reservation in {self.displayChannel.mention} needs to @ a player.")
            await message.delete()
        # ADDBAN [nation], [nation], ...
        elif text.upper().startswith("ADDBAN") and await checkResAdmin(message.guild, message.author):
            # This is implemented by having lists of recognized and unrecognized bans, doing the recognized ones, and informing about the result.
            bannations = text[text.index(" ")+1:].strip("\n\t ,").split(",")
            bantags: List[str] = []
            fails: List[str] = []
            for bannat in bannations:
                tag = EU4Lib.country(bannat.strip("\n\t ,"))
                if tag is not None:
                    bantags.append(tag)
                else:
                    fails.append(bannat)
            string = ""
            if len(bantags) > 0:
                for tag in bantags:
                    self.reserve.addBan(tag)
                string += f"Added the following nations to the ban list in {self.displayChannel.mention}: "
                for tag in bantags:
                    string += EU4Lib.tagToName(tag) + \
                        ("" if tag is bantags[-1] else ",")
            if len(fails) > 0:
                string += "\nDid not recognize the following nations: "
                for tag in fails:
                    string += EU4Lib.tagToName(tag) + \
                        ("" if tag is fails[-1] else ", ")
                string += "\n The unrecognized nations were not added to the ban list."
            if string != "":
                await sendUserMessage(message.author, string)
            await message.delete()
            await self.updateText()
        # DELBAN [nation], [nation], ...
        elif text.upper().startswith("DELBAN") and await checkResAdmin(message.guild, message.author):
            # This is implemented by having lists of recognized and unrecognized bans, doing the recognized ones, and informing about the result.
            bannations = text[text.index(" ")+1:].strip("\n\t ,").split(",")
            bantags: List[str] = []
            fails: List[str] = []
            for bannat in bannations:
                tag = EU4Lib.country(bannat.strip("\n\t ,"))
                if tag is not None:
                    bantags.append(tag)
                else:
                    fails.append(bannat)
            string = ""
            if len(bantags) > 0:
                for tag in bantags:
                    self.reserve.delBan(tag)
                string += f"Removed the following nations from the ban list in {self.displayChannel.mention}: "
                for tag in bantags:
                    string += EU4Lib.tagToName(tag) + \
                        ("" if tag is bantags[-1] else ",")
            if len(fails) > 0:
                string += "\nDid not recognize the following nations: "
                for tag in fails:
                    string += EU4Lib.tagToName(tag) + \
                        ("" if tag is fails[-1] else ", ")
                string += "\n The unrecognized nations were not removed from the ban list."
            if string != "":
                await sendUserMessage(message.author, string)
            await message.delete()
            await self.updateText()
        else:
            await message.delete()

    async def updateText(self):
        # Text String - Header
        string = f"How to reserve: `reserve [nation]`\nTo unreserve: `delreserve`\n"
        # Text String - Banned Nations
        string += "Banned nations: "
        banlist = self.reserve.allBans()
        if len(banlist) == 0:
            string += "*none or unspecified*"
        for tag in banlist:
            name = EU4Lib.tagToName(tag)
            string += (tag if name is None else name) + \
                ("" if tag is banlist[-1] else ", ")
        playerCount = self.reserve.countPlayers()
        string += f"\n**Current players list: ** *({playerCount} players)*"
        # Text String - Players
        if playerCount == 0:
            string += "\n*It's so empty here...*"
        else:
            players = self.reserve.getPlayers()
            players.sort(key=lambda x: x.time)
            for x in players:
                string += f"\n<@{x.userID}>: {EU4Lib.tagToName(x.tag)} | {x.timeStr()}"
        # Update the message or send a new one if nonexistant
        try:
            await (await self.displayChannel.fetch_message(self.textID)).edit(content=string)
        except (discord.NotFound, discord.HTTPException):
            self.textID = (await self.displayChannel.send(content=string)).id

    async def updateImg(self):
        # Try to delete the previous image to trigger the upload of a new one.
        try:
            await (await self.interactChannel.fetch_message(self.imgID)).delete()
        except (discord.NotFound, discord.HTTPException):
            # Normally when deleted it'll create the new one in the delete event, but in case there's an issue this will fix it.
            # This issue is usually that the image message doesn't exist or has already been deleted.
            self.imgID = (await self.displayChannel.send(file=imageToFile(EU4Reserve.createMap(self.reserve)))).id

    async def add(self, nation: EU4Reserve.reservePick) -> int:
        """
        Adds a reservation for a player.

        Codes:
        0 = Failed; Reserve not found
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other
        4 = Nothing happens; Nation taken by self
        """
        addInt = self.reserve.add(nation)
        # Notifications based off the code returned by the backend.
        if addInt == 1 or addInt == 2:  # Success!
            await self.updateText()
            await self.updateImg()
        elif addInt == 0:  # This is not a reserve channel. How did this happen?
            await sendUserMessage(client.get_user(int(nation.userID.strip("\n\t <!@>"))), f"You can't reserve nations in {self.displayChannel.mention}.")
        elif addInt == 3:  # This nation is already taken
            await sendUserMessage(client.get_user(int(nation.userID.strip("\n\t <!@>"))), f"The nation {EU4Lib.tagToName(nation.tag)} is already reserved in {self.displayChannel.mention}.")
        return addInt

    async def remove(self, tag: str):
        pass

    async def removePlayer(self, id: str):
        """
        Deletes a player's reservation.
        """
        # If it did anything
        if self.reserve.removePlayer(id):
            await self.updateText()
            await self.updateImg()

    async def msgdel(self, msgID: Union[str, int]):
        """
        Method called whenever a message is deleted.
        """
        if msgID == self.textID:
            self.textID = None
            await self.updateText()
            # This will call msgdel again to update the image
            await (await self.interactChannel.fetch_message(self.imgID)).delete()
        elif msgID == self.imgID:
            self.imgID = (await self.displayChannel.send(file=imageToFile(EU4Reserve.createMap(self.reserve)))).id

    async def userdel(self, user: DiscUser):
        """
        Method called whenever a user leaves the guild.
        """
        if (hasattr(self.displayChannel, "guild") and self.displayChannel.guild == user.guild) or (hasattr(self.interactChannel, "guild") and self.interactChannel.guild == user.guild):
            await self.removePlayer(user.id)


class Nation:
    def __init__(self, tag: str):
        self.tag: str = tag.upper()
        self.othertags: List[str] = []
        self.development: int = 0
        self.prestige: int = None
        self.stability: int = None
        # self.manpower = None
        # self.maxManpower = None
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
        # self.revColors: color = None
        self.mapColor: Tuple[int, int, int] = None
        self.natColor: Tuple[int, int, int] = None

    def fullDataStr(self) -> str:
        """
        Returns a brief multi-line human-readable text representation of the data contained in this Nation object.
        """
        string = f"Tag: {self.tag} Previous Tags: {self.othertags}\n"
        string += f"Dev: {self.development} Prestige: {self.prestige} Stability: {self.stability}\n"
        string += f"Army: {self.army} Navy: {self.navy}\n"
        string += f"Treasury: {self.treasury} Debt: {self.debt}\n"
        string += f"Income: {self.totalIncome} Expenses: {self.totalExpense}\n"
        string += f"Capital: {self.capitalID}\n"
        string += f"Allies: {self.allies}\n"
        string += (f"Overlord: {self.overlord}" if self.overlord is not None else "") + (
            f"Subjects: {self.subjects}" if len(self.subjects) != 0 else "")
        return string


class war():
    WHITEPEACE: int = 1
    ATTACKERWIN: int = 2
    DEFENDERWIN: int = 3

    def __init__(self, name: str):
        self.name = name
        self.attackers: List[str] = []
        self.defenders: List[str] = []
        self.attackerLosses: int = 0
        self.defenderLosses: int = 0
        self.startDate: EU4cpplib.EU4Date = None
        self.endDate: EU4cpplib.eu4Date = None
        self.result: int = 0

    def isPlayerWar(self, playertags: List[str]) -> bool:
        """
        Returns True if there are players on both sides of a war.
        """
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

    def playerAttackers(self, playertags: List[str]) -> List[str]:
        """
        Returns a list of tags for nations on the attacking side played by players.
        """
        return list(filter(lambda x: x in self.attackers, playertags))

    def playerDefenders(self, playertags: List[str]) -> List[str]:
        """
        Returns a list of tags for nations on the defending side played by players.
        """
        return list(filter(lambda x: x in self.defenders, playertags))

    def warScale(self, playertags: List[str] = []) -> int:
        """
        Calculates a score for how important the war is for deciding which to display. May be somewhat arbitrary or subjective.
        """
        if playertags is None or playertags == []:  # Ignore player involvement
            # Base off casualties
            return self.attackerLosses + self.defenderLosses
        else:  # Include player involvement
            # Scale by number of players
            return (self.attackerLosses + self.defenderLosses) * max(min(len(self.playerAttackers(playertags)) * 0.7, len(self.playerDefenders(playertags)) * 0.7), 1)


class saveGame():
    def __init__(self):
        self.allNations: Dict[str, Nation] = {}
        self.playertags: Dict[str, str] = {}
        self.provinces: Dict[int, str] = {}
        self.dlc: List[str] = []
        self.GP: List[str] = []
        self.date: Optional[EU4cpplib.EU4Date] = None
        self.mp: bool = True
        self.age: Optional[str] = None
        self.HRE: str = None
        self.china: str = None
        self.crusade: str = None
        self.playerWars: List[war] = []

    def allPlayerTags(self) -> List[str]:
        if hasattr(self, "allplayertags"):
            return self.allplayertags
        else:
            # Player tags plus all previous tags those countries have had
            self.allplayertags: List[str] = []
            for tag in self.playertags:
                if tag not in self.allplayertags:
                    self.allplayertags.append(tag)
                for prevtag in self.allNations[tag].othertags:
                    if prevtag not in self.allplayertags:
                        self.allplayertags.append(prevtag)
            return self.allplayertags


class statsChannel(AbstractChannel):
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels):
        self.user = user
        self.interactChannel: DiscTextChannels = None
        self.displayChannel: DiscTextChannels = initChannel
        self.hasReadFile = False
        self.politicalImage: Image.Image = None
        self.game = saveGame()
        self.modMsg: discord.Message = None
        self.doneMod = False
        self.skanderbeg = True
        self.skanderbegURL: Optional[asyncio.Task] = None

    async def asyncInit(self):
        """
        Does all the init stuff that needs to happen async. Returns self.
        """
        if self.user.dm_channel is None:
            await self.user.create_dm()
        self.interactChannel = self.user.dm_channel
        await self.interactChannel.send("**Send EITHER an uncompressed .eu4 save file\nor a direct link to an uncompressed .eu4 save file:**\nYou can do this by uploading to https://www.file.io/\nthen clicking **Copy Link** and entering it here:")
        return self

    def modPromptStr(self) -> str:
        """
        Makes and returns a string giving information and instructions for player list modification.
        """
        prompt = "**Current players list:**```"
        for tag in self.game.playertags:
            natName = EU4Lib.tagToName(tag)
            prompt += f"\n{tag if natName is None else natName}: {self.game.playertags[tag]}"
        prompt += "```\n**Do you want to make any changes?\nType `done` to finish. Commands:\n`remove [nation]`\n`add [player], [nation]`**"
        return prompt

    async def readFile(self, file: StringIO):
        """
        Gets all data from file and saves it to the self.game.
        """

        brackets: List[str] = []
        currentReadWar: war = None
        currentReadWarParticTag: str = None
        currentWarLastLeave: EU4cpplib.EU4Date = None
        lastPlayerInList: str = None

        # Reading save file...
        linenum = 0
        for line in file:
            linenum += 1
            if "{" in line:
                if line.count("}") == 0 and line.count("{") == 1:
                    brackets.append(line.strip("\t ={\n"))
                elif line.count("{") == line.count("}"):
                    continue
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
            else:
                if "=" in line and not ('"' in line and line.index('"') < line.index("=")):
                    linekey, lineval = line.split("=", maxsplit=1)
                    lineval = lineval.strip()
                    linekey = linekey.strip()
                else:
                    # This probably means it's the interior of a list or something like that.
                    linekey = ""
                    lineval = line.strip()
                # This is where we do stuff
                if len(brackets) == 0:
                    # Get current gamedate
                    if linekey == "date":
                        self.game.date = EU4cpplib.EU4Date(lineval)
                    # Get save DLC (not sure if we use this...)
                    elif brackets == ["dlc_enabled"]:
                        self.game.dlc.append(lineval.strip('"'))
                    # Check if game is mp
                    elif linekey == "multi_player":
                        if "yes" == lineval:
                            self.game.mp = True
                        else:
                            self.game.mp = False
                    # Get current age
                    elif linekey == "current_age" and brackets == []:
                        self.game.age = lineval.strip('"')
                # Get player names and country tags
                elif brackets == ["players_countries"]:
                    # In the file, the format is like this:
                    # players_countries={
                    #   "playername"
                    #   "SWE"
                    #
                    # Where "   " is a tab \t
                    # Prepare to assign the player by recording it for the next line
                    if lastPlayerInList is None:
                        lastPlayerInList = lineval.strip('"')
                    # Add to playertags based on what was saved in the previous line as the player name
                    else:
                        self.game.playertags[lineval.strip(
                            '"')] = lastPlayerInList
                        lastPlayerInList = None
                # Get top 8
                elif linekey == "country" and brackets == ["great_powers", "original"]:
                    if len(self.game.GP) < 8:  # Make sure to not include leaving GPs
                        self.game.GP.append(lineval.strip('"'))
                # Get HRE emperor tag
                elif linekey == "emperor" and brackets == ["empire"]:
                    self.game.HRE = lineval.strip('"')
                # Get Celestial emperor tag
                elif linekey == "emperor" and brackets == ["celestial_empire"]:
                    self.game.china = lineval.strip('"')
                # Get target of crusade ('---' if none)
                elif linekey == "crusade_target" and brackets == ["religion_instance_data", "catholic", "papacy"]:
                    self.game.crusade = lineval.strip('"')
                # Get papal controller
                elif linekey == "previous_controller" and brackets == ["religion_instance_data", "catholic", "papacy"]:
                    continue
                
                elif len(brackets) > 1 and brackets[0] == "provinces":
                    provinceID = int(brackets[1][1:])
                    if len(brackets) == 2:
                        if linekey == "owner":
                            self.game.provinces[provinceID] = line[line.index('"')+1:line.rindex('"')]
                # Country-specific data (for players)
                elif len(brackets) > 1 and brackets[0] == "countries":
                    try:
                        bracketNation = self.game.allNations[brackets[1]]
                    except:
                        # This should be the government_rank= line where we create the Nation object.
                        pass
                    if len(brackets) == 2:
                        if linekey == "government_rank":
                            # This one is assignment so should NOT be referring to bracketNation
                            self.game.allNations[brackets[1]] = Nation(
                                brackets[1])
                        elif linekey == "previous_country_tags":
                            bracketNation.othertags.append(
                                line[line.index('"')+1:line.rindex('"')])
                        elif linekey == "raw_development":
                            bracketNation.development = round(
                                float(lineval))
                        elif linekey == "capital":
                            bracketNation.capitalID = int(lineval)
                        elif linekey == "score_place":
                            bracketNation.scorePlace = round(
                                float(lineval))
                        elif linekey == "prestige":
                            bracketNation.prestige = round(float(lineval))
                        elif linekey == "stability":
                            bracketNation.stability = round(float(lineval))
                        elif linekey == "treasury":
                            bracketNation.treasury = round(float(lineval))
                        # elif linekey == "manpower":
                            # bracketNation.manpower = round(float(lineval))
                        # elif linekey == "max_manpower":
                            # bracketNation.maxManpower = round(float(lineval))
                        elif linekey == "overlord":
                            bracketNation.overlord = lineval.strip('"')
                    elif len(brackets) == 3:
                        # Get each loan and add its amount to debt
                        if brackets[2] == "loan" and linekey == "amount":
                            bracketNation.debt += round(
                                float(lineval))
                        # Get Income from the previous month
                        elif brackets[2] == "ledger" and linekey == "lastmonthincome":
                            bracketNation.totalIncome = round(
                                float(lineval), 2)
                        # Get Expense from the previous month
                        elif brackets[2] == "ledger" and linekey == "lastmonthexpense":
                            bracketNation.totalExpense = round(
                                float(lineval), 2)
                        elif brackets[2] == "subjects":
                            for subject in line.split():
                                bracketNation.subjects.append(subject)
                        elif brackets[2] == "allies":
                            for ally in line.split():
                                bracketNation.allies.append(ally)
                    elif len(brackets) == 4:
                        # Add 1 to army size for each regiment
                        if brackets[2] == "army" and brackets[3] == "regiment" and linekey == "morale":
                            bracketNation.army += 1000
                        # Subtract damage done to units from army size
                        elif brackets[2] == "army" and brackets[3] == "regiment" and linekey == "strength":
                            try:
                                bracketNation.army = round(
                                    bracketNation.army - 1000 + 1000 * float(lineval))
                            except ValueError:
                                # Full unit
                                continue
                        # Add 1 for each ship
                        elif brackets[2] == "navy" and brackets[3] == "ship" and linekey == "home":
                            bracketNation.navy += 1
                        elif brackets[2] == "colors" and brackets[3] == "map_color":
                            bracketNation.mapColor = tuple(
                                map(lambda x: int(x), line.split()))
                        elif brackets[2] == "colors" and brackets[3] == "country_color":
                            bracketNation.natColor = tuple(
                                map(lambda x: int(x), line.split()))
                # Read wars
                elif len(brackets) > 0 and brackets[0] == "previous_war":
                    if len(brackets) == 1 and linekey == "name":
                        if currentReadWar is not None and currentReadWar.isPlayerWar(self.game.playertags):
                            currentReadWar.endDate = currentWarLastLeave
                            self.game.playerWars.append(currentReadWar)
                        currentReadWar = war(lineval.strip('"'))
                    elif len(brackets) == 3 and brackets[1] == "history":
                        if linekey == "add_attacker":
                            currentReadWar.attackers.append(
                                lineval.strip('"'))
                            if currentReadWar.startDate is None:
                                currentReadWar.startDate = EU4cpplib.EU4Date(
                                    brackets[2])
                        elif linekey == "add_defender":
                            currentReadWar.defenders.append(
                                lineval.strip('"'))
                        elif linekey == "rem_attacker" or linekey == "rem_defender":
                            currentWarLastLeave = EU4cpplib.EU4Date(
                                brackets[2])
                    elif len(brackets) >= 2 and brackets[1] == "participants":
                        if len(brackets) == 2 and linekey == "tag":
                            currentReadWarParticTag = lineval.strip('"')
                        elif len(brackets) == 4 and brackets[2] == "losses" and brackets[3] == "members":
                            if currentReadWarParticTag in currentReadWar.attackers:
                                for x in line.split():
                                    currentReadWar.attackerLosses += int(x)
                            elif currentReadWarParticTag in currentReadWar.defenders:
                                for x in line.split():
                                    currentReadWar.defenderLosses += int(x)
                            else:
                                print(
                                    "Something went wrong with the attacker/defender list.")
                    elif len(brackets) == 1 and linekey == "outcome":
                        currentReadWar.result = int(lineval)
                        if currentReadWar.isPlayerWar(self.game.playertags):
                            currentReadWar.endDate = currentWarLastLeave
                            self.game.playerWars.append(currentReadWar)
                            currentReadWar = None
        # Finalize data
        # These signify that it's probably not a valid save file.
        if self.game.GP == [] or self.game.date is None or self.game.age is None:
            raise Exception(
                f"This probably isn't a valid .eu4 uncompressed save file from {self.user.mention}")
        for nat in self.game.allNations.copy().keys():
            if self.game.allNations[nat].development == 0:
                try:
                    del(self.game.allNations[nat])
                except:
                    pass
                try:
                    del(self.game.playertags[nat])
                except:
                    pass
            # else:
                # print(self.game.allNations[nat].fullDataStr())
        # Sort Data:
        self.game.playerWars.sort(key=lambda nat: nat.warScale(
            self.game.playertags), reverse=True)

    async def generateImage(self, sendUpdates=True) -> Image.Image:
        """
        Returns a stats Image based off the self.game data.

        If sendUpdates is True, a message will be sent and edited in the interactChannel for this control channel.
        """
        progressMessage: discord.Message = None
        if sendUpdates and self.interactChannel is not None:
            progressMessage = await self.interactChannel.send("**Generating Image...**")

        async def updateProgress(text: str, num: int, maxnum: int):
            if progressMessage is not None:
                await progressMessage.edit(content=f"**Generating Image...**\n{text} ({num}/{maxnum})")

        def armyDisplay(army: int) -> str:
            """
            Makes the army display text

            Under 100,000: "12.3k" or "12k" when 12,000
            Under 1,000,000: "123k" rounded
            Above 1,000,000: "1.23M" rounded
            """
            if army < 1000000:
                armydisplay = str(round(army/1000, 1))
                if armydisplay.endswith(".0") or ("." in armydisplay and len(armydisplay) > 4):
                    armydisplay = armydisplay[:-2]
                return f"{armydisplay}k"
            else:  # army >= 1M
                armydisplay = str(round(army/1000000, 2))
                if armydisplay.endswith(".0"):
                    armydisplay = armydisplay[:-2]
                elif armydisplay.endswith("0"):
                    # This is the hundredth place. If the tenth place is 0, then floats will not include the hundredth place in a string and the previous if will catch it.
                    armydisplay = armydisplay[:-1]
                return f"{armydisplay}M"

        def invertColor(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
            """
            Inverts a color for the player border.
            """
            return (255 - color[0], 255 - color[1], 255 - color[2])

        await updateProgress("Finding players to draw borders...", 1, 8)

        tagColors: Dict[str, Tuple[int, int, int]] = {}
        for natTag in self.game.allNations:
            tagColors[natTag] = self.game.allNations[natTag].mapColor

        # Formatting: (map color) = (player contrast color)
        playerColors: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
        for natTag in self.game.allNations:
            try:
                nat: Nation = self.game.allNations[natTag]
                playerNatTag: str = None  # This is what nation actually is said to own the land
                # Check if this nation is a player
                if natTag in self.game.playertags:
                    playerNatTag = natTag
                # Check if any overlord(s) are players and if so, go with the highest one.
                while nat.overlord is not None:
                    if nat.overlord in self.game.playertags:
                        playerNatTag = nat.overlord
                    nat = self.game.allNations[nat.overlord]
                if playerNatTag is not None:
                    playerColors[self.game.allNations[natTag].mapColor] = invertColor(
                        self.game.allNations[playerNatTag].mapColor)
            except:
                pass
        # Modify the image
        await updateProgress("Calculating player borders...", 2, 8)
        print("pre")
        img: Image.Image = Image.frombytes("RGB", (5632, 2048), EU4cpplib.drawMap(tagColors, self.game.provinces))
        img.show()
        # Formatting: (draw color) = [(x, y), (x, y), ...]
        drawColors: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = EU4cpplib.drawBorders(
            playerColors, self.politicalImage.tobytes(), self.politicalImage.width, self.politicalImage.height)
        try:
            del(drawColors[(0, 0, 0)])
        except:
            pass
        await updateProgress("Drawing player borders...", 3, 8)
        mapDraw = ImageDraw.Draw(self.politicalImage)
        for drawColor in drawColors:
            mapDraw.point(drawColors[drawColor], drawColor)
        del(drawColors)
        del(playerColors)
        # Start Final Img Creation
        # Copy map into bottom of final image
        await updateProgress("Finalizing map section...", 4, 8)
        imgFinal: Image.Image = Image.open("resources/finalTemplate.png")
        imgFinal.paste(self.politicalImage,
                       (0, imgFinal.size[1]-self.politicalImage.size[1]))
        del(self.politicalImage)
        # The top has 5632x1119
        # Getting fonts
        fontmini = ImageFont.truetype("resources/GARA.TTF", 36)
        fontsmall = ImageFont.truetype("resources/GARA.TTF", 50)
        font = ImageFont.truetype("resources/GARA.TTF", 100)
        imgDraw = ImageDraw.Draw(imgFinal)
        #================MULTIPLAYER================#
        if True:  # mp == True:
            # Players section from (20,30) to (4710, 1100) half way is x=2345
            # So start with yborder = 38, yheight = 128 for each player row. x just make it half or maybe thirds depending on how it goes

            # Get the list of player Nations
            # TODO: make this more integrated with the new savefile data system rather than doing this conversion
            await updateProgress("Drawing player list...", 5, 8)
            playerNationList: List[Nation] = []
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
                    flag: Image.Image = None
                    if (nat.tag.startswith("C") and nat.tag[1:].isdigit() and nat.overlord is not None):
                        # This is a colonial nation, so make that flag instead.
                        flag = EU4Lib.colonialFlag(
                            nat.overlord, EU4Lib.colonialRegion(nat.capitalID))
                    else:
                        flag = EU4Lib.flag(nat.tag)
                    imgFinal.paste(flag, (x, y))
                    # x+128: Player
                    playerName = self.game.playertags[nat.tag]
                    while (imgDraw.textsize(playerName, font)[0] > 760 - 128):
                        # Make sure the name isn't too long
                        playerName = playerName[:-1]
                    imgDraw.text((x+128, y), playerName, (255, 255, 255), font)
                    # x+760: Army size
                    imgFinal.paste(Image.open(
                        "resources/army.png"), (x+760, y))
                    imgDraw.text((x+760+128, y),
                                 armyDisplay(nat.army), (255, 255, 255), font)
                    # x+1100: Navy size
                    imgFinal.paste(Image.open(
                        "resources/navy.png"), (x+1100, y))
                    imgDraw.text((x+1100+128, y), str(nat.navy),
                                 (255, 255, 255), font)
                    # x+1440: Development
                    imgFinal.paste(Image.open(
                        "resources/development.png"), (x+1440, y))
                    imgDraw.text((x+1440+128, y),
                                 str(nat.development), (255, 255, 255), font)
                    # x+1780: Income/Expense
                    monthlyProfit = nat.totalIncome-nat.totalExpense
                    imgIncome = Image.open("resources/income.png")
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
            await updateProgress("Drawing player wars...", 6, 8)
            for playerWar in self.game.playerWars:
                warnum = self.game.playerWars.index(playerWar)
                if warnum < 4:
                    x = 4742
                    y = 230 + 218 * warnum
                    # Draw Attacker Flags
                    for nat in playerWar.playerAttackers(self.game.allPlayerTags()):
                        natnum = playerWar.playerAttackers(
                            self.game.allPlayerTags()).index(nat)
                        if natnum < 8:
                            flag: Image.Image = None
                            if (nat.startswith("C") and nat[1:].isdigit() and self.game.allNations[nat].overlord is not None):
                                # This is a colonial nation, so make that flag instead.
                                try:
                                    flag = EU4Lib.colonialFlag(self.game.allNations[nat].overlord, EU4Lib.colonialRegion(
                                        self.game.allNations[nat].capitalID))
                                except:
                                    raise RuntimeWarning(
                                        f"Something went wrong in creating a colonial flag. Details:\n{nat.fullDataStr()}")
                            else:
                                flag = EU4Lib.flag(nat)
                            imgFinal.paste(flag.resize((64, 64)), (round(x + 3 * (12 + 64) - (
                                natnum % 4) * (64 + 12)), round(y + (natnum - natnum % 4) / 4 * (64 + 12) + 12)))
                    # Draw Attacker Casualties
                    attackerIcon = Image.open(
                        "resources/bodycount_attacker_button.png")
                    imgFinal.paste(
                        attackerIcon, (x + 290 - 12 - 32, y + 156), attackerIcon)
                    imgDraw.text((x + 290 - 12 - 32 - imgDraw.textsize(f"Losses: {armyDisplay(playerWar.attackerLosses)}", fontmini)[
                                 0], y + 152), f"Losses: {armyDisplay(playerWar.attackerLosses)}", (255, 255, 255), fontmini)
                    # Draw Defender Flags
                    for nat in playerWar.playerDefenders(self.game.allPlayerTags()):
                        natnum = playerWar.playerDefenders(
                            self.game.allPlayerTags()).index(nat)
                        if natnum < 8:
                            flag: Image.Image = None
                            if (nat.startswith("C") and nat[1:].isdigit() and self.game.allNations[nat].overlord is not None):
                                # This is a colonial nation, so make that flag instead.
                                try:
                                    flag = EU4Lib.colonialFlag(self.game.allNations[nat].overlord, EU4Lib.colonialRegion(
                                        self.game.allNations[nat].capitalID))
                                except:
                                    raise RuntimeWarning(
                                        f"Something went wrong in creating a colonial flag. Details:\n{nat.fullDataStr()}")
                            else:
                                flag = EU4Lib.flag(nat)
                            imgFinal.paste(flag.resize((64, 64)), (round(
                                x + (natnum % 4) * (64 + 12) + 585), round(y + (natnum - natnum % 4) / 4 * (64 + 12) + 12)))
                    # Draw Defender Casualties
                    defenderIcon = Image.open(
                        "resources/bodycount_defender_button.png")
                    imgFinal.paste(
                        defenderIcon, (x + 12 + 585, y + 156), defenderIcon)
                    imgDraw.text((x + 12 + 32 + 585, y + 152),
                                 f"Losses: {armyDisplay(playerWar.defenderLosses)}", (255, 255, 255), fontmini)
                    # Draw war details
                    remainingWords = playerWar.name.split()
                    lineLimit = 290  # pix/ln
                    nameStr = ""
                    for word in remainingWords:
                        if nameStr == "" or nameStr.endswith("\n"):
                            if imgDraw.textsize(word, fontmini)[0] >= lineLimit:
                                nameStr += f"{word}\n"
                            else:
                                nameStr += word
                        else:
                            if imgDraw.textsize(word, fontmini)[0] >= lineLimit:
                                nameStr += f"\n{word}\n"
                            elif imgDraw.textsize(nameStr.split('\n')[-1] + word, fontmini)[0] >= lineLimit:
                                nameStr += f"\n{word}"
                            else:
                                nameStr += f" {word}"
                    imgDraw.text((round(x + 437.5 - imgDraw.textsize(nameStr, fontmini)
                                        [0]/2), y + 12), nameStr, (255, 255, 255), fontmini, align="center")
                    dateStr = str(playerWar.startDate.year) + \
                        "-" + str(playerWar.endDate.year)
                    imgDraw.text((round(x + 437.5 - imgDraw.textsize(dateStr, fontmini)
                                        [0]/2), y + 115), dateStr, (255, 255, 255), fontmini, align="center")
                    # Draw result
                    if playerWar.result == war.WHITEPEACE:
                        WPIcon = Image.open("resources/icon_peace.png")
                        imgFinal.paste(WPIcon, (x + 437 - 32, y + 140), WPIcon)
                    elif playerWar.result == war.ATTACKERWIN:
                        WinnerIcon = Image.open("resources/star.png")
                        imgFinal.paste(
                            WinnerIcon, (x + 290, y + 148), WinnerIcon)
                    elif playerWar.result == war.DEFENDERWIN:
                        WinnerIcon = Image.open("resources/star.png")
                        imgFinal.paste(
                            WinnerIcon, (x + 12 + 585 - 48, y + 148), WinnerIcon)
        #================SINGLEPLAYER================#
        else:
            pass
        #================END  SECTION================#
        # Date
        await updateProgress("Drawing date...", 7, 8)
        imgDraw.text((round(5177 - imgDraw.textsize(self.game.date.fancyStr(),
                                                    font)[0] / 2), 60), self.game.date.fancyStr(), (255, 255, 255), font)
        await updateProgress("**Image generation complete.** Uploading...", 8, 8)
        return imgFinal

    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel and not message.author.bot

    async def process(self, message: discord.Message):
        if message.content.upper() == "CANCEL":
            await self.interactChannel.send("**Cancelling the stats operation.**")
            controlledChannels.remove(self)
            if self.skanderbegURL is not None:
                self.skanderbegURL.cancel()
            del(self)
        elif not self.hasReadFile:  # First step - get .eu4 file
            saveFile: Optional[bytes] = None
            if len(message.attachments) > 0 and message.attachments[0].filename.endswith(".eu4"):
                saveFile = await message.attachments[0].read()
            else:  # str
                saveURL: str = message.content.strip()
                try:
                    response = await session.get(saveURL)
                except Exception as e:
                    await self.interactChannel.send(f"Something went wrong. This may not be a valid link.\n```{repr(e)}```")
                    return
                if response.status == 200:  # 200 == ok
                    saveFile = await response.content.read()
                else:
                    await self.interactChannel.send("Something went wrong. Please try a different link.")
                    return
            await self.interactChannel.send("**Recieved save file. Processing...**")
            try:
                await self.readFile(StringIO(saveFile.decode("cp1252")))
            except DiscordException as e:
                await self.interactChannel.send(f"**Uh oh! something went wrong.**\nIt could be that your save file was incorrectly formatted. Make sure it is uncompressed.\n**Please try another file.**\n```{repr(e)}```")
                return
            except:
                await self.interactChannel.send(f"**Something went wrong in decoding your `.eu4` file.**\nThis may mean your file is not an eu4 save file, or has been changed from the cp1252 encoding.\n**Please try another file or change the file's encoding and try again.**\n```{repr(e)}```")
                return
            else:
                await self.interactChannel.send("**Send the `.png` Political Mapmode screenshot in this channel:**")
                self.hasReadFile = True
                if self.skanderbeg and SKANDERBEGKEY is not None:
                    await self.interactChannel.send("Started upload to Skanderbeg. This may take much longer than the stats image generation.")
                    self.skanderbegURL = asyncio.create_task(Skanderbeg.upload(
                        saveFile, f"{self.game.date.fancyStr()} - Cartographer Upload", SKANDERBEGKEY))
                    # We don't manually delete saveFile here, but that's probably fine since once the upload is done there shouldn't be any other references
                else:
                    del(saveFile)
        # Second step - get .png file
        elif self.hasReadFile and (self.politicalImage is None):
            if len(message.attachments) == 0:  # Check there is a file
                await self.interactChannel.send("File not received. Please send a file as a message attachment.")
            # Needs to be a .png file
            elif not message.attachments[0].filename.endswith(".png"):
                await self.interactChannel.send("File type needs to be `.png`. Please send a `.png` EU4 player mapmode screenshot.")
            else:  # This means that all the checks succeeded
                politicalFile = BytesIO()
                await message.attachments[0].save(politicalFile)
                self.politicalImage: Image.Image = Image.open(politicalFile)
                del(politicalFile)
                if self.politicalImage.size != (5632, 2048):
                    await self.interactChannel.send("**Your image was not the right size.** `(5632, 2048)`\nDid you submit a Political Mapmode screenshot? (f10)\n**Please try another image.**")
                    self.politicalImage = None
                else:
                    if message.content.strip().lower() == "done":
                        await self.process(message)
                    else:
                        self.modMsg = await self.interactChannel.send(self.modPromptStr())
        # Third step - player list modification
        elif self.hasReadFile and (self.politicalImage is not None) and (not self.doneMod):
            # done
            if message.content.strip().lower() == "done":
                self.doneMod == True
                # Create the Image and convert to discord.File
                img: discord.File = imageToFile(await self.generateImage())
                try:
                    if self.skanderbeg:
                        if self.skanderbegURL.done():
                            await self.displayChannel.send(self.skanderbegURL.result(), file=img)
                        else:
                            imgmsg: discord.Message = await self.displayChannel.send("*Uploading to Skanderbeg.pm...*", file=img)
                            await self.interactChannel.send(f"Sent image to {self.displayChannel.mention}... Waiting for upload to Skanderbeg.")
                            await imgmsg.edit(content=await self.skanderbegURL)
                    else:
                        await self.displayChannel.send(file=img)
                # If we're not allowed to send on the server, just give it in dms. They can post it themselves.
                except discord.Forbidden:
                    await self.interactChannel.send(f"**Unable to send the image to {self.displayChannel.mention} due to lack of permissions. Posting image here:**\nYou can right-click and copy link then post that.", file=imageToFile(img))
                else:
                    await self.interactChannel.send(f"**Done! Check {self.displayChannel.mention}**")
                controlledChannels.remove(self)
                del(self)
            # add [player], [nation]
            elif message.content.strip().lower().startswith("add "):
                player = message.content.strip().partition(
                    " ")[2].partition(",")[0].strip()
                natName = message.content.strip().partition(",")[2].strip()
                tag = EU4Lib.country(natName)
                if tag is None:
                    await message.add_reaction("\u2754")  # Question Mark
                elif tag in self.game.playertags:
                    await sendUserMessage(self.user, f"{EU4Lib.tagToName(tag)} is already played. If you wish to replace the player, please remove them first.")
                elif not tag in self.game.allNations:
                    await sendUserMessage(self.user, f"{EU4Lib.tagToName(tag)} does not exist in this game.")
                else:
                    self.game.playertags[tag] = player
                    await self.modMsg.edit(content=self.modPromptStr())
                    await message.add_reaction("\u2705")  # Check Mark
            # remove [nation]
            elif message.content.strip().lower().startswith("remove "):
                name = message.content.strip().partition(" ")[2].strip()
                tag = EU4Lib.country(name)
                if tag is None:
                    await message.add_reaction("\u2754")  # Question Mark
                elif tag in self.game.playertags:
                    del(self.game.playertags[tag])
                    await self.modMsg.edit(content=self.modPromptStr())
                    await message.add_reaction("\u2705")  # Check Mark
                else:
                    pass
                    # await self.interactChannel.send(f"Did not recognize {tag.upper()} as a played nation.")

    async def msgdel(self, msgID: Union[str, int]):
        pass

    async def userdel(self, user: DiscUser):
        if user == self.user:
            try:  # If this fails, it probably means the account was deleted. We still should delete.
                await self.interactChannel.send(f"You left the {self.displayChannel.guild.name} discord server, so this stats interaction has been cancelled.")
            finally:
                controlledChannels.remove(self)
                del(self)


class asiFaction:
    """
    Represents a faction for an ASI game.
    """

    def __init__(self, name: str, territory: List[str], maxPlayers: int = 256):
        self.name = name
        self.territory = territory
        self.maxPlayers = maxPlayers
        self.taken = 0

    def isInTerritory(self, provinceID: Union[str, int]) -> bool:
        """
        Returns whether or not the given province is within this faction's territory.
        """
        for land in self.territory:
            if EU4Lib.isIn(provinceID, land):
                return True
        return False


# This is custom for my discord group. Anybody else can ignore it or do what you will.
class asiresChannel(AbstractChannel):
    def __init__(self, user: DiscUser, initChannel: DiscTextChannels, textID: int = None):
        self.user = None
        self.interactChannel = initChannel
        self.displayChannel = initChannel
        self.reserve = EU4Reserve.ASIReserve(initChannel.id)
        self.textID = textID
        self.factions: List[asiFaction] = []
        self.factions.append(asiFaction("West", ["france_region", "british_isles_region", "iberia_region", "corsica_sardinia_area",
                                                 "piedmont_area", "liguria_area", "tuscany_area", "naples_area", "calabria_area", "sicily_area"], 4))
        self.factions.append(asiFaction("East", ["low_countries_region", "north_german_region", "south_german_region", "scandinavia_region", "poland_region", "baltic_region",
                                                 "russia_region", "ruthenia_region", "carpathia_region", "venetia_area", "lombardy_area", "emilia_romagna_area", "apulia_area", "central_italy_area"]))
        self.factions.append(asiFaction("Mid", [
                             "balkan_region", "near_east_superregion", "persia_superregion", "egypt_region", "maghreb_region"]))
        # self.factions.append(asiFaction(
        #    "India", ["india_superregion", "burma_region"]))
        self.factions.append(asiFaction("Asia", ["china_superregion", "tartary_superregion", "far_east_superregion",
                                                 "malaya_region", "moluccas_region", "indonesia_region", "indo_china_region", "oceania_superregion", "india_superregion", "burma_region"], 4))

    def getFaction(self, provinceID: Union[str, int]) -> Optional[asiFaction]:
        """
        Returns the faction that owns a given province.

        This should only be one faction, but if more than one have the province in their territory list, only the first faction with the territory on its list will be returned.
        """
        for faction in self.factions:
            if faction.isInTerritory(provinceID):
                return faction
        return None

    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel

    @property
    def textID(self) -> Optional[int]:
        if hasattr(self, "_textID"):
            return self._textID
        return self.reserve.textID

    @textID.setter
    def textID(self, id: int):
        self._textID = id
        self.reserve.textID = id

    async def process(self, message: discord.Message):
        text = message.content.strip()
        if text.upper() == "HELP":  # HELP
            stringHelp = f"__**Command help for {message.channel.mention}:**__"
            stringHelp += "\n**HELP**\nGets you this information!"
            stringHelp += "\n**RESERVE [nation1], [nation2], [nation3]**\nReserves your picks or overwrites your previous reservation.\nThese are in the order of first pick to third. Don't include the brackets."
            stringHelp += "\n**DELRESERVE**\nCancels your reservation."
            # Here we send info about commands only for admins
            if await checkResAdmin(message.guild, message.author):
                stringHelp += "\n**END**\nStops allowing reservations and stops the bot's channel management.\nThen runs and displays the draft. Draft may need to be rearranged manually to ensure game balance."
                stringHelp += "\n**ADMRES [nation1], [nation2], [nation3] [@user]**\nReserves picks on behalf of a player on the server.\nMake sure to actually @ the player."
                stringHelp += "\n**EXECRES [nation] [optional @user]**\nReserves a pick on behalf of yourself or another player on the server.\nEnsures that this player gets the reservation first."
                stringHelp += "\n**ADMDELRES [@user]**\nDeletes a player's reservation.\nMake sure to actually @ the player."
                stringHelp += "\n**UPDATE**\nUpdates the reservations list. Should usually not be necessary unless in debug or something went wrong."
            await message.delete()
            await sendUserMessage(message.author, stringHelp)
        elif text.upper() == "UPDATE" and await checkResAdmin(message.guild, message.author):  # UPDATE
            await message.delete()
            await self.updateText()
        elif text.upper() == "END" and await checkResAdmin(message.guild, message.author):  # END
            await message.delete()
            finalReserves: List[EU4Reserve.reservePick] = []
            # This stores the capitals of all possible tags, so that their factions can be determined.
            tagCapitals: Dict[str, int] = {}
            # Add all possibly reserved nations to the tagCapitals dictionary with a capital of -1
            reserves = self.reserve.getPlayers()
            for res in reserves:
                for tag in res.picks:
                    if tagCapitals.get(tag.upper()) is None:
                        tagCapitals[tag.upper()] = -1
            # Get the actual capitals and add to tagCapitals.
            srcFile = open("resources/save_1444.eu4", "r", encoding="cp1252")
            brackets: List[str] = []
            linenum = 0
            for line in srcFile:
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
                        print(f"Unexpected brackets at line {linenum}: {line}")
                elif "}" in line:
                    try:
                        brackets.pop()
                    except IndexError:  # This shouldn't happen.
                        print(
                            f"No brackets to delete at line {linenum}: {line}")
                elif len(brackets) > 1 and brackets[0] == "countries={":
                    for x in tagCapitals:
                        if x in brackets[1]:
                            # Here we have all the stats for country x on the players list
                            if len(brackets) == 2 and "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                                tagCapitals[x] = int(line.strip("\tcapitl=\n"))
            # Draft Executive Reserves
            for res in reserves:
                if res.priority:
                    finalReserves.append(EU4Reserve.reservePick(
                        res.userID, res.picks[0].upper()))
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
                    if resFaction is None or resFaction.taken >= resFaction.maxPlayers:
                        continue
                    # If already taken, don't add (skip)
                    if tag.upper() not in finalReserves:
                        finaltag = tag.upper()
                        resFaction.taken += 1
                        break
                finalReserves.append(
                    EU4Reserve.reservePick(res.userID, finaltag))
            # At this point the finalReserves list is complete with all finished reserves. If a player had no reserves they could take, their tag is None
            string = "**Reserves are finished. The following is the draft order:**"
            count = 1
            for res in finalReserves:
                if res.tag is None:
                    string += f"\n{count} <@{res.userID}>: *[all taken]*"
                else:
                    natname = EU4Lib.tagToName(res.tag)
                    string += f"\n{count} <@{res.userID}>: {res.tag if natname is None else natname}"
                count += 1
            await self.displayChannel.send(string)
            # aaand we're done!
            self.reserve.delete()
            controlledChannels.remove(self)
            del(self)
        # RESERVE [nation1], [nation2], [nation3]
        elif text.upper().startswith("RESERVE "):
            await self.add(message.author, text[text.index(" ")+1:].strip())
            await message.delete()
            await self.updateText()
        # ADMRES [nation1], [nation2], [nation3] @[player]
        elif text.upper().startswith("ADMRES") and await checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                # Get the part "[nation1], [nation2], [nation3]" by stripping the rest
                res = text[text.index(" ")+1:].strip("\n\t <@!1234567890>")
                # Split that into the individual picks
                picks = res.split(",")
                # Check for problems
                if not len(picks) == 3:
                    await sendUserMessage(message.author, f"Your reserve in {self.interactChannel.mention} for {message.mentions[0].mention} needs to be 3 elements in the format `a,b,c`")
                    await message.delete()
                    return
                for pick in picks:
                    if EU4Lib.country(pick.strip()) is None:
                        await sendUserMessage(message.author, f"Your reservation of {pick.strip()} in {self.interactChannel.mention} for {message.mentions[0].mention} was not a recognized nation.")
                        await message.delete()
                        return
                # At this point the reservation should be valid, because otherwise add will send the failure to the target.
                await self.add(message.mentions[0], res)
                await self.updateText()
            else:
                await sendUserMessage(message.author, f"Your reservation in {self.displayChannel.mention} needs to @ a player.")
            await message.delete()
        # EXECRES [nation] @[optional_player]
        elif text.upper().startswith("EXECRES") and await checkResAdmin(message.guild, message.author):
            # Get the part "[nation]" by stripping the rest
            res = text[text.index(" ")+1:].strip("\n\t <@!1234567890>")
            # Find the targeted user
            user: Optional[DiscUser] = None
            if len(message.mentions) == 0:
                user = message.author
            else:
                user = message.mentions[0]
            # Get the tag for the specified nation
            pick = EU4Lib.country(res)
            if pick is None:  # Nation is invalid; tag not found.
                await sendUserMessage(message.author, f"Your reservation of {res.strip()} in {self.interactChannel.mention} for {user.mention} was not a recognized nation.")
                await message.delete()
                return
            # Now reserve
            await message.delete()
            asipick = EU4Reserve.asiPick(user.id, priority=True)
            asipick.picks = [pick, None, None]
            addInt = self.reserve.add(asipick)
            if addInt == 3:
                await sendUserMessage(message.author, f"{EU4Lib.tagToName(pick)} is already executive-reserved in {message.channel.mention}")
            elif addInt == 1 or addInt == 2:
                await self.updateText()
        elif text.upper() == "DELRESERVE" or text.upper() == "DELETERESERVE":  # DELRESERVE
            await self.remove(message.author)
            await message.delete()
            await self.updateText()
        # ADMDELRES @[player]
        elif text.upper().startswith("ADMDELRES") and await checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                await self.remove(message.mentions[0].id)
                await self.updateText()
            else:
                await sendUserMessage(message.author, f"Your deletion of a reservation in {self.displayChannel.mention} needs to @ one player.")
            await message.delete()
        else:
            await message.delete()

    async def updateText(self):
        """
        Updates the text for the reserves list based on the current players list. Either edits the previous message or sends new if nonexistant.
        """
        # Constructing the text string
        # Text String - Header
        string = "How to reserve: `reserve [nation1], [nation2], [nation3]`\nTo unreserve: `delreserve`\n**Current players list:**"
        # Load player list
        picks = self.reserve.getPlayers()
        # Text String - Players
        if len(picks) == 0:
            string += "\n*It's so empty here...*"
        else:
            picks.sort(key=lambda x: x.time)
            for x in picks:
                if x.priority:
                    string += f"\n<@{x.userID}>: **{EU4Lib.tagToName(x.picks[0])}** | {x.timeStr()}"
                else:
                    string += f"\n<@{x.userID}>: {EU4Lib.tagToName(x.picks[0])}, {EU4Lib.tagToName(x.picks[1])}, {EU4Lib.tagToName(x.picks[2])} | {x.timeStr()}"
        # Update the previous text or post new
        if self.textID is None:
            self.textID = (await self.displayChannel.send(content=string)).id
        else:
            await (await self.displayChannel.fetch_message(self.textID)).edit(content=string)

    async def add(self, user: DiscUser, text: str):
        """
        Adds a user's reservation.
        """
        picks: List[str] = text.split(",")
        # Check that there is the correct format.
        if not len(picks) == 3:
            await sendUserMessage(user, f"Your reserve in {self.interactChannel.mention} needs to be 3 elements in the format `a,b,c`")
            return
        tags: List[str] = []
        # Find each tag or cancel if one is invalid.
        for pick in picks:
            tag = EU4Lib.country(pick.strip())
            if tag is not None:
                tags.append(tag)
            else:
                await sendUserMessage(user, f"Your reservation of {pick.strip()} in {self.interactChannel.mention} was not a recognized nation.")
                return
        # Create and add player's reservation to the reserve.
        res = EU4Reserve.asiPick(user.id, picks=tags)
        self.reserve.add(res)

    async def remove(self, user: DiscUser):
        """
        Deletes a user's reservation.
        """
        self.reserve.removePlayer(user.id)

    async def msgdel(self, msgID: Union[str, int]):
        if msgID == self.textID:
            self.textID = None
            await self.updateText()

    async def userdel(self, user: DiscUser):
        await self.remove(user)
        await self.updateText()


# DISCORD CODE
controlledChannels: List[AbstractChannel] = []


@client.event
async def on_ready():
    print("EU4 Reserve Bot!")
    # Create http session
    global session
    session = aiohttp.ClientSession()
    # Register guilds
    print("Registering connected Guilds not yet registered...")
    newGuildCount = 0
    async for guild in client.fetch_guilds():
        if GuildManager.getGuildSave(guild) is None:
            GuildManager.addGuild(guild)
            newGuildCount += 1
    print(f"Registered {newGuildCount} new Guilds.")
    # Load reserves
    print("Loading previous Reserves...")
    reserves = EU4Reserve.load()
    rescount = 0
    closedcount = 0
    for res in reserves:
        reschannel = await findChannel(res.channelID)
        if reschannel is None:
            res.delete()
            closedcount += 1
        else:
            if isinstance(res, EU4Reserve.Reserve):
                # Check that the textmsg still exists
                try:
                    await reschannel.fetch_message(res.textID)
                except:  # The message either doesn't exist or can't be reached by the bot
                    textmsg = None
                else:  # The message is accessable.
                    textmsg = res.textID
                # Check that the imgmsg still exists
                try:
                    await reschannel.fetch_message(res.imgID)
                except:  # The message either doesn't exist or can't be reached by the bot
                    imgmsg = None
                else:  # The message is accessable.
                    imgmsg = res.imgID
                # Create the ReserveChannel object and add to control channels list
                controlledChannels.append(ReserveChannel(
                    None, reschannel, textID=textmsg, imgID=imgmsg))
                # Update if anything was deleted
                if textmsg is None:
                    await controlledChannels[-1].updateText()
                    await controlledChannels[-1].updateImg()
                elif imgmsg is None:
                    await controlledChannels[-1].updateImg()
            elif isinstance(res, EU4Reserve.ASIReserve):
                # Check that the textmsg still exists
                try:
                    await reschannel.fetch_message(res.textID)
                except:  # The message either doesn't exist or can't be reached by the bot
                    textmsg = None
                else:  # The message is accessable.
                    textmsg = res.textID
                # Create asiresChannel object and add to control channels list
                controlledChannels.append(asiresChannel(
                    None, reschannel, textID=textmsg))
                # Update if anything was deleted
                if textmsg is None:
                    await controlledChannels[-1].updateText()
            rescount += 1
    print(
        f"Loaded {rescount} channels and removed {closedcount} no longer existing channels.")
    # Set activity
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for new lands"))


@client.event
async def on_message(message: discord.Message):
    if not message.author.bot:
        for channel in controlledChannels:
            if await channel.responsive(message):
                await channel.process(message)
                return


@client.event
async def on_guild_channel_delete(channel: DiscTextChannels):
    for c in controlledChannels:
        # Delete any control channels related to the deleted channel.
        if c.displayChannel == channel or c.interactChannel == channel:
            if isinstance(c, (ReserveChannel, asiresChannel)):
                c.reserve.delete()
            controlledChannels.remove(c)
            del(c)


@client.event
async def on_private_channel_delete(channel: DiscTextChannels):
    for c in controlledChannels:
        # Delete any control channels related to the deleted DM channel.
        if c.displayChannel == channel or c.interactChannel == channel:
            controlledChannels.remove(c)
            del(c)


@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    for c in controlledChannels:
        await c.msgdel(payload.message_id)


@client.event
async def on_member_remove(member: DiscUser):
    for c in controlledChannels:
        await c.userdel(member)


@client.event
async def on_guild_join(guild: discord.Guild):
    # Setup the joined guild with the GuildManager
    GuildManager.addGuild(guild)


@client.event
async def on_guild_remove(guild: discord.Guild):
    GuildManager.removeGuild(guild)
    for c in controlledChannels:
        # Delete any control channels related to the guild that was left.
        if (hasattr(c.displayChannel, "guild") and c.displayChannel.guild == guild) or (hasattr(c.interactChannel, "guild") and c.interactChannel.guild == guild):
            if isinstance(c, (ReserveChannel, asiresChannel)):
                c.reserve.delete()
            controlledChannels.remove(c)
            del(c)


@client.event
async def on_socket_response(msg: Dict):
    # This is not a publically listed event, but we can intercept it to catch interactions
    if msg["op"] == 0 and msg["t"] == "INTERACTION_CREATE":
        # This means it's an interaction.
        # https://discord.com/developers/docs/interactions/slash-commands#interaction
        interaction: Dict[str, Any] = msg["d"]
        # Verify this is for us
        if int(interaction["application_id"]) != (await client.application_info()).id or interaction["type"] != 2:
            # Not sure if this'll ever happen, but we're recieving an interaction not for us.
            return
        commandname: str = interaction["data"]["name"]
        responseurl = f"https://discord.com/api/v8/interactions/{interaction['id']}/{interaction['token']}/callback"

        async def permissionDenied():
            responsejson = {
                "type": 4,
                "data": {
                    "content": "You do not have permission to use this command.",
                    "flags": 64
                }
            }
            await session.post(responseurl, json=responsejson)
        authorid: int = int(interaction["member"]["user"]["id"]
                            if "member" in interaction else interaction["user"]["id"])
        guild: discord.Guild = await findGuild(interaction["guild_id"])
        responsejson: Dict[str, Any] = {}

        if commandname.lower() == "help":  # ~~NOT REGISTERED~~
            stringHelp = "__**Command help:**__"
            stringHelp += f"\n**/help**\nGets you this information!"
            stringHelp += f"\n**/defaultban <add|del|list>**\nModifies or displays the default reservation ban list. Only admins can modify."
            # Here we send info about commands only for admins
            if await checkResAdmin(guild, authorid):
                stringHelp += f"\n**/reservations**\nTurns the text channel into a reservation channel\n(more commands within that; use `help` in it for info)"
                stringHelp += f"\n**/stats**\nCreates a eu4 stats image in the channel.\nUses DMs to gather the necessary files for creation."
                stringHelp += f"\n**/asireservations**\nTurns the text channel into a ASI reservation channel\nThis is specific to my discord."
                stringHelp += f"\n**/adminrank**\nChanges the minimum rank necessary for admin control of the bot.\nPlease be sure before changing this. The highest rank can always control the bot.\nThe @ is optional in specifying the rank."
            responsejson = {
                "type": 4,
                "data": {
                    "content": stringHelp,
                    "flags": 64
                }
            }
            await session.post(responseurl, json=responsejson)
        elif commandname.lower() == "reservations":
            if not await checkResAdmin(guild, authorid):
                await permissionDenied()
                return
            for channel in controlledChannels:
                if channel.interactChannel.id == int(interaction["channel_id"]):
                    await session.post(responseurl, json={
                        "type": 4,
                        "data": {
                            "content": "This channel already contains a controlled channel.",
                            "flags": 64
                        }
                    })
                    return
            responsejson = {
                "type": 4,
                "data": {
                    "content": "Loading Reservation Channel..."
                }
            }
            await session.post(responseurl, json=responsejson)
            c = ReserveChannel(None, await findChannel(interaction["channel_id"]))
            await c.updateText()
            await c.updateImg()
            controlledChannels.append(c)
            await session.delete(f"https://discord.com/api/v8/webhooks/{interaction['application_id']}/{interaction['token']}/messages/@original")
        elif commandname.lower() == "asireservations":
            if not await checkResAdmin(guild, authorid):
                await permissionDenied()
                return
            for channel in controlledChannels:
                if channel.interactChannel.id == int(interaction["channel_id"]):
                    await session.post(responseurl, json={
                        "type": 4,
                        "data": {
                            "content": "This channel already contains a controlled channel.",
                            "flags": 64
                        }
                    })
                    return
            responsejson = {
                "type": 4,
                "data": {
                    "content": "Loading ASI Reservation Channel..."
                }
            }
            await session.post(responseurl, json=responsejson)
            c = asiresChannel(None, await findChannel(interaction["channel_id"]))
            await c.updateText()
            controlledChannels.append(c)
            await session.delete(f"https://discord.com/api/v8/webhooks/{interaction['application_id']}/{interaction['token']}/messages/@original")
        elif commandname.lower() == "stats":
            for channel in controlledChannels:
                if channel.interactChannel.id == int(interaction["channel_id"]):
                    await session.post(responseurl, json={
                        "type": 4,
                        "data": {
                            "content": "This channel already contains a controlled channel.",
                            "flags": 64
                        }
                    })
                    return
            responsejson = {
                "type": 4,
                "data": {
                    "content": "Sent stats creation details to your DMs!",
                    "flags": 64
                }
            }
            await session.post(responseurl, json=responsejson)
            c = await statsChannel(await findUser(authorid), await findChannel(interaction["channel_id"])).asyncInit()
            if "options" in interaction["data"]:
                for option in interaction["data"]["options"]:
                    if option["name"] == "skanderbeg":
                        c.skanderbeg = option["value"]
            else:
                # Default if not specified
                c.skanderbeg = False
            controlledChannels.append(c)
        elif commandname.lower() == "defaultban":
            if guild is None:
                responsejson = {
                    "type": 4,
                    "data": {
                        "content": "Either this command was not sent in a server or something went very wrong.",
                        "flags": 64
                    }
                }
                await session.post(responseurl, json=responsejson)
                return
            subcommand: Dict[str, Any] = interaction["data"]["options"]
            string = "Something went wrong."
            if subcommand[0]["name"] == "add":
                if not await checkResAdmin(guild, authorid):
                    await permissionDenied()
                    return
                tag: str = EU4Lib.country(subcommand[0]["options"][0]["value"])
                if tag is None:
                    string = f"Could not find country named {subcommand[0]['options'][0]['value']}."
                else:
                    GuildManager.addBan(guild, tag)
                    string = f"Adding {EU4Lib.tagToName(tag)} to default ban list."
                    string += "\nNew default ban list: "
                    banlist = GuildManager.getBan(guild)
                    for listtag in banlist:
                        string += f"{EU4Lib.tagToName(listtag)}{'' if listtag is banlist[-1] else ', '}"
            elif subcommand[0]["name"] == "del":
                if not await checkResAdmin(guild, authorid):
                    await permissionDenied()
                    return
                tag: str = EU4Lib.country(subcommand[0]["options"][0]["value"])
                if tag is None:
                    string = f"Could not find country named {subcommand[0]['options'][0]['value']}."
                if tag is not None:
                    GuildManager.removeBan(guild, tag)
                    string = f"Removing {EU4Lib.tagToName(tag)} from default ban list."
                    string += "\nNew default ban list: "
                    banlist = GuildManager.getBan(guild)
                    for listtag in banlist:
                        string += f"{EU4Lib.tagToName(listtag)}{'' if listtag is banlist[-1] else ', '}"
            elif subcommand[0]["name"] == "list":
                string = "Default ban list: "
                banlist = GuildManager.getBan(guild)
                for tag in banlist:
                    string += EU4Lib.tagToName(tag) + \
                        ("" if tag is banlist[-1] else ", ")
            responsejson = {
                "type": 4,
                "data": {
                    "content": string,
                    "flags": 64
                }
            }
            await session.post(responseurl, json=responsejson)
        elif commandname.lower() == "adminrank":
            if not await checkResAdmin(guild, authorid):
                await permissionDenied()
                return
            newRankID: int = int(interaction["data"]["options"][0]["value"])
            GuildManager.setAdmin(guild, newRankID)
            responsejson = {
                "type": 4,
                "data": {
                    "content": f"Admin rank set to <@&{newRankID}>.",
                    "flags": 64
                }
            }
            await session.post(responseurl, json=responsejson)
        else:
            responsejson = {
                "type": 4,
                "data": {
                    "content": "The bot was unable to process this command. Please report with details to the developer.",
                    "flags": 64
                }
            }
            await session.post(responseurl, json=responsejson)


client.run(token)
