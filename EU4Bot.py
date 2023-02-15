import asyncio
import os
from abc import ABC, abstractmethod
from io import StringIO
from random import shuffle
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import EU4cpplib
import discord
from discord.errors import DiscordException
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps

import EU4Lib
import EU4Reserve
import discordLib as dLib
import baseLib
import GuildManager
import Skanderbeg


# Load Discord Client
load_dotenv()
token: str = os.getenv("DISCORD_TOKEN")
intents: discord.Intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
dLib.client = client

session: aiohttp.ClientSession = None

# Load Skanderbeg key if it exists
SKANDERBEGKEY = os.getenv("SKANDERBEG_KEY")
if SKANDERBEGKEY == "" or SKANDERBEGKEY.isspace():
    SKANDERBEGKEY = None


async def checkResAdmin(server: Union[str, int, discord.Guild], user: Union[str, int, dLib.DiscUser]) -> bool:
    """
    Returns whether or not a user has bot admin control roles on a server.
    """
    # Get server object
    server = await dLib.findGuild(server)
    # Get member object
    user = await dLib.findMember(user, server)
    # OK now check
    try:
        role = server.get_role(GuildManager.getAdmin(server))
    except TypeError:
        role = None
    return (role is not None and role <= user.top_role) or user.top_role.id == server.roles[-1].id or user._user.id == 249680375280959489


class AbstractChannel(ABC):
    @abstractmethod
    def __init__(self, user: dLib.DiscUser, initChannel: dLib.DiscTextChannels):
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
    async def userdel(self, user: dLib.DiscUser):
        pass


class ReserveChannel(AbstractChannel):
    def __init__(self, user: dLib.DiscUser, initChannel: dLib.DiscTextChannels, textID: Optional[int] = None, imgID: Optional[int] = None):
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
            await dLib.sendDM(message.author, stringHelp)
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
                    await dLib.sendDM(message.author, f"You may not reserve {EU4Lib.tagToName(tag)} in {self.displayChannel.mention} because it is banned. If you still want to play it, please have an admin override.")
                else:
                    await self.add(EU4Reserve.reservePick(message.author.id, tag))
            else:
                await dLib.sendDM(message.author, f"Your country reservation in {self.displayChannel.mention} was not recorded, as \"{res}\" was not recognized.")
            await message.delete()
        # ADMRES [nation] @[player]
        elif text.upper().startswith("ADMRES") and await checkResAdmin(message.guild, message.author):
            if len(message.mentions) == 1:
                res = text[text.index(" ")+1:].strip("\n\t <@!1234567890>")
                tag = EU4Lib.country(res)
                if tag is not None:
                    await self.add(EU4Reserve.reservePick(message.mentions[0].id, tag.upper()))
                else:
                    await dLib.sendDM(message.author, f"Your reservation for {message.mentions[0].mention} in {self.displayChannel.mention} was not recorded, as \"{res}\" was not recognized.")
            else:
                await dLib.sendDM(message.author, f"Your reservation in {self.displayChannel.mention} needs to @ a player.")
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
                await dLib.sendDM(message.author, f"Your deletion of a reservation in {self.displayChannel.mention} needs to @ a player.")
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
                await dLib.sendDM(message.author, string)
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
                await dLib.sendDM(message.author, string)
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
            self.imgID = (await self.displayChannel.send(file=dLib.imageToFile(EU4Reserve.createMap(self.reserve)))).id

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
            await dLib.sendDM(client.get_user(int(nation.userID.strip("\n\t <!@>"))), f"You can't reserve nations in {self.displayChannel.mention}.")
        elif addInt == 3:  # This nation is already taken
            await dLib.sendDM(client.get_user(int(nation.userID.strip("\n\t <!@>"))), f"The nation {EU4Lib.tagToName(nation.tag)} is already reserved in {self.displayChannel.mention}.")
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
            self.imgID = (await self.displayChannel.send(file=dLib.imageToFile(EU4Reserve.createMap(self.reserve)))).id

    async def userdel(self, user: dLib.DiscUser):
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
        self.mod: str = "vanilla"

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
    def __init__(self, user: dLib.DiscUser, initChannel: dLib.DiscTextChannels):
        self.user = user
        self.interactChannel: dLib.DiscTextChannels = None
        self.displayChannel: dLib.DiscTextChannels = initChannel
        self.hasReadFile = False
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
            natName = EU4Lib.tagToName(tag, self.game.mod)
            prompt += f"\n{tag if natName is None else natName}: {self.game.playertags[tag]}"
        prompt += "```\n**Do you want to make any changes?\nType `done` to finish. Commands:\n`remove [nation]`\n`add [player], [nation]`**"
        return prompt

    async def readFile(self, file: iter):
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
                elif len(brackets) == 2 and brackets[0] == "mods_enabled_names" and linekey == "name":
                    if lineval == '"Anbennar: A Fantasy Total Conversion Mod"':
                        self.game.mod = "anbennar"
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
                            self.game.provinces[provinceID] = line[line.index(
                                '"')+1:line.rindex('"')]
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
                            bracketNation.debt += round(float(lineval))
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
                        if brackets[2:] == ["army", "regiment"] and linekey == "morale":
                            bracketNation.army += 1000
                        # Subtract damage done to units from army size
                        elif brackets[2:] == ["army", "regiment"] and linekey == "strength":
                            try:
                                bracketNation.army = round(
                                    bracketNation.army - 1000 + 1000 * float(lineval))
                            except ValueError:
                                # Full unit
                                continue
                        # Add 1 for each ship
                        elif brackets[2:] == ["navy", "ship"] and linekey == "home":
                            bracketNation.navy += 1
                        elif brackets[2:] == ["colors", "map_color"]:
                            bracketNation.mapColor = tuple(
                                map(lambda x: int(x), line.split()))
                        elif brackets[2:] == ["colors", "country_color"]:
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
                        elif len(brackets) == 4 and brackets[2:] == ["losses", "members"]:
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
            raise ValueError(
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

        await updateProgress("Finding colors...", 1, 9)

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
                    playerColors[self.game.allNations[natTag].mapColor] = baseLib.invertColor(
                        self.game.allNations[playerNatTag].mapColor)
            except:
                pass
        # All tags' colors
        tagColors: Dict[str, Tuple[int, int, int]] = {}
        for natTag in self.game.allNations:
            tagColors[natTag] = self.game.allNations[natTag].mapColor

        # Modify the image
        await updateProgress("Drawing map...", 2, 9)
        img: Image.Image = Image.frombytes(
            "RGB", (5632, 2048), EU4cpplib.drawMap(tagColors, self.game.provinces, self.game.mod))
        img = ImageOps.flip(img)

        await updateProgress("Calculating player borders...", 3, 9)
        # Formatting: (draw color) = [(x, y), (x, y), ...]
        drawColors: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = EU4cpplib.drawBorders(
            playerColors, img.tobytes(), img.width, img.height)
        try:
            del(drawColors[(0, 0, 0)])
        except:
            pass
        await updateProgress("Drawing player borders...", 4, 9)
        mapDraw = ImageDraw.Draw(img)
        for drawColor in drawColors:
            mapDraw.point(drawColors[drawColor], drawColor)
        del(drawColors)
        del(playerColors)
        # Start Final Img Creation
        # Copy map into bottom of final image
        await updateProgress("Finalizing map section...", 5, 9)
        imgFinal: Image.Image = Image.open("resources/finalTemplate.png")
        imgFinal.paste(img, (0, imgFinal.size[1]-img.size[1]))
        del(img)
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
            await updateProgress("Drawing player list...", 6, 9)
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
                        flag = EU4Lib.colonialFlag(nat.overlord, EU4Lib.colonialRegion(
                            nat.capitalID, self.game.mod), self.game.mod)
                    else:
                        flag = EU4Lib.flag(nat.tag, self.game.mod)
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
                    imgDraw.text(
                        (x+760+128, y), baseLib.armyDisplay(nat.army), (255, 255, 255), font)
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
            await updateProgress("Drawing player wars...", 7, 9)
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
                                        self.game.allNations[nat].capitalID, self.game.mod), self.game.mod)
                                except:
                                    raise RuntimeWarning(
                                        f"Something went wrong in creating a colonial flag. Details:\n{nat.fullDataStr()}")
                            else:
                                flag = EU4Lib.flag(nat, self.game.mod)
                            imgFinal.paste(flag.resize((64, 64)), (round(x + 3 * (12 + 64) - (
                                natnum % 4) * (64 + 12)), round(y + (natnum - natnum % 4) / 4 * (64 + 12) + 12)))
                    # Draw Attacker Casualties
                    attackerIcon = Image.open(
                        "resources/bodycount_attacker_button.png")
                    imgFinal.paste(
                        attackerIcon, (x + 290 - 12 - 32, y + 156), attackerIcon)

                    lossesStr = f"Losses: {baseLib.armyDisplay(playerWar.attackerLosses)}"
                    imgDraw.text((x + 290 - 12 - 32 - imgDraw.textsize(lossesStr,
                                 fontmini)[0], y + 152), lossesStr, (255, 255, 255), fontmini)
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
                                        self.game.allNations[nat].capitalID, self.game.mod), self.game.mod)
                                except:
                                    raise RuntimeWarning(
                                        f"Something went wrong in creating a colonial flag. Details:\n{nat.fullDataStr()}")
                            else:
                                flag = EU4Lib.flag(nat, self.game.mod)
                            imgFinal.paste(flag.resize((64, 64)), (round(
                                x + (natnum % 4) * (64 + 12) + 585), round(y + (natnum - natnum % 4) / 4 * (64 + 12) + 12)))
                    # Draw Defender Casualties
                    defenderIcon = Image.open(
                        "resources/bodycount_defender_button.png")
                    imgFinal.paste(
                        defenderIcon, (x + 12 + 585, y + 156), defenderIcon)
                    imgDraw.text((x + 12 + 32 + 585, y + 152),
                                 f"Losses: {baseLib.armyDisplay(playerWar.defenderLosses)}", (255, 255, 255), fontmini)
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
        await updateProgress("Drawing date...", 8, 9)
        imgDraw.text((round(5177 - imgDraw.textsize(self.game.date.fancyStr(),
                                                    font)[0] / 2), 60), self.game.date.fancyStr(), (255, 255, 255), font)
        await updateProgress("**Image generation complete.** Uploading...", 9, 9)
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
                    response = await session.get(saveURL, allow_redirects=False)
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
                await self.readFile(StringIO(saveFile.decode("cp1252", "replace")))
            except UnicodeDecodeError as e:
                await self.interactChannel.send(f"****Something went wrong in decoding your `.eu4` file.**\nThis may mean your file is not an eu4 save file or has been changed from cp1252 encoding.\n**Please try another file or fix the file's encoding and try again.**\n```{baseLib.stringifyTrbk(e)}```")
                return
            except DiscordException as e:
                await self.interactChannel.send(f"**Uh oh! something went wrong.**\nIt could be that your save file was incorrectly formatted. Make sure it is uncompressed.\n**Please try another file.**\n```{baseLib.stringifyTrbk(e)}```")
                return
            except Exception as e:
                await self.interactChannel.send(f"**Something went wrong.**\n```{baseLib.stringifyTrbk(e)}```")
                return
            else:
                self.hasReadFile = True
                if self.skanderbeg and SKANDERBEGKEY is not None:
                    await self.interactChannel.send("Started upload to Skanderbeg. This may take much longer than the stats image generation.")
                    self.skanderbegURL = asyncio.create_task(Skanderbeg.upload(
                        saveFile, f"{self.game.date.fancyStr()} - Cartographer Upload", SKANDERBEGKEY))
                    # We don't manually delete saveFile here, but that's probably fine since once the upload is done there shouldn't be any other references
                else:
                    del(saveFile)
                self.modMsg = await self.interactChannel.send(self.modPromptStr())
        # Second step - player list modification
        elif self.hasReadFile and not self.doneMod:
            # done
            if message.content.strip().lower() == "done":
                self.doneMod == True
                # Create the Image and convert to discord.File
                img: discord.File = dLib.imageToFile(await self.generateImage())
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
                    await self.interactChannel.send(f"**Unable to send the image to {self.displayChannel.mention} due to lack of permissions. Posting image here:**\nYou can right-click and copy link then post that.", file=dLib.imageToFile(img))
                else:
                    if hasattr(self.displayChannel, "mention"):
                        await self.interactChannel.send(f"**Done! Check {self.displayChannel.mention}**")
                    else:
                        await self.interactChannel.send(f"**Done!**")
                controlledChannels.remove(self)
                del(self)
            # add [player], [nation]
            elif message.content.strip().lower().startswith("add "):
                player = message.content.strip().partition(
                    " ")[2].partition(",")[0].strip()
                natName = message.content.strip().partition(",")[2].strip()
                tag = EU4Lib.country(natName, self.game.mod)
                if tag is None:
                    await message.add_reaction("\u2754")  # Question Mark
                elif tag in self.game.playertags:
                    await dLib.sendDM(self.user, f"{EU4Lib.tagToName(tag, self.game.mod)} is already played. If you wish to replace the player, please remove them first.")
                elif not tag in self.game.allNations:
                    await dLib.sendDM(self.user, f"{EU4Lib.tagToName(tag, self.game.mod)} does not exist in this game.")
                else:
                    self.game.playertags[tag] = player
                    await self.modMsg.edit(content=self.modPromptStr())
                    await message.add_reaction("\u2705")  # Check Mark
            # remove [nation]
            elif message.content.strip().lower().startswith("remove "):
                name = message.content.strip().partition(" ")[2].strip()
                tag = EU4Lib.country(name, self.game.mod)
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

    async def userdel(self, user: dLib.DiscUser):
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
    def __init__(self, user: dLib.DiscUser, initChannel: dLib.DiscTextChannels, textID: int = None):
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
            await dLib.sendDM(message.author, stringHelp)
        elif text.upper() == "UPDATE" and await checkResAdmin(message.guild, message.author):  # UPDATE
            await message.delete()
            await self.updateText()
        elif text.upper() == "END" and await checkResAdmin(message.guild, message.author):  # END
            await message.delete()
            finalReserves: List[EU4Reserve.reservePick] = []
            reserves = self.reserve.getPlayers()

            # Draft Executive Reserves
            for res in reserves:
                if res.priority:
                    finalReserves.append(EU4Reserve.reservePick(
                        res.userID, res.picks[0].upper()))
                    self.getFaction(EU4Lib.tagCapital(
                        res.picks[0].upper())).taken += 1
                    reserves.remove(res)
            # Shuffle
            shuffle(reserves)
            # Draft Reserves
            for res in reserves:
                finaltag = None
                for tag in res.picks:
                    resFaction = self.getFaction(
                        EU4Lib.tagCapital(tag.upper()))
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
                    await dLib.sendDM(message.author, f"Your reserve in {self.interactChannel.mention} for {message.mentions[0].mention} needs to be 3 elements in the format `a,b,c`")
                    await message.delete()
                    return
                for pick in picks:
                    if EU4Lib.country(pick.strip()) is None:
                        await dLib.sendDM(message.author, f"Your reservation of {pick.strip()} in {self.interactChannel.mention} for {message.mentions[0].mention} was not a recognized nation.")
                        await message.delete()
                        return
                # At this point the reservation should be valid, because otherwise add will send the failure to the target.
                await self.add(message.mentions[0], res)
                await self.updateText()
            else:
                await dLib.sendDM(message.author, f"Your reservation in {self.displayChannel.mention} needs to @ a player.")
            await message.delete()
        # EXECRES [nation] @[optional_player]
        elif text.upper().startswith("EXECRES") and await checkResAdmin(message.guild, message.author):
            # Get the part "[nation]" by stripping the rest
            res = text[text.index(" ")+1:].strip("\n\t <@!1234567890>")
            # Find the targeted user
            user: Optional[dLib.DiscUser] = None
            if len(message.mentions) == 0:
                user = message.author
            else:
                user = message.mentions[0]
            # Get the tag for the specified nation
            pick = EU4Lib.country(res)
            if pick is None:  # Nation is invalid; tag not found.
                await dLib.sendDM(message.author, f"Your reservation of {res.strip()} in {self.interactChannel.mention} for {user.mention} was not a recognized nation.")
                await message.delete()
                return
            # Now reserve
            await message.delete()
            asipick = EU4Reserve.asiPick(user.id, priority=True)
            asipick.picks = [pick, None, None]
            addInt = self.reserve.add(asipick)
            if addInt == 3:
                await dLib.sendDM(message.author, f"{EU4Lib.tagToName(pick)} is already executive-reserved in {message.channel.mention}")
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
                await dLib.sendDM(message.author, f"Your deletion of a reservation in {self.displayChannel.mention} needs to @ one player.")
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

    async def add(self, user: dLib.DiscUser, text: str):
        """
        Adds a user's reservation.
        """
        picks: List[str] = text.split(",")
        # Check that there is the correct format.
        if not len(picks) == 3:
            await dLib.sendDM(user, f"Your reserve in {self.interactChannel.mention} needs to be 3 elements in the format `a,b,c`")
            return
        tags: List[str] = []
        # Find each tag or cancel if one is invalid.
        for pick in picks:
            tag = EU4Lib.country(pick.strip())
            if tag is not None:
                tags.append(tag)
            else:
                await dLib.sendDM(user, f"Your reservation of {pick.strip()} in {self.interactChannel.mention} was not a recognized nation.")
                return
        # Create and add player's reservation to the reserve.
        res = EU4Reserve.asiPick(user.id, picks=tags)
        self.reserve.add(res)

    async def remove(self, user: dLib.DiscUser):
        """
        Deletes a user's reservation.
        """
        self.reserve.removePlayer(user.id)

    async def msgdel(self, msgID: Union[str, int]):
        if msgID == self.textID:
            self.textID = None
            await self.updateText()

    async def userdel(self, user: dLib.DiscUser):
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
        try:
            reschannel = await dLib.findChannel(res.channelID)
        except ValueError:
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
async def on_guild_channel_delete(channel: dLib.DiscTextChannels):
    for c in controlledChannels:
        # Delete any control channels related to the deleted channel.
        if c.displayChannel == channel or c.interactChannel == channel:
            if isinstance(c, (ReserveChannel, asiresChannel)):
                c.reserve.delete()
            controlledChannels.remove(c)
            del(c)


@client.event
async def on_private_channel_delete(channel: dLib.DiscTextChannels):
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
async def on_member_remove(member: dLib.DiscUser):
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

        async def respond(content: str, hidden: bool = False):
            responsejson = {
                "type": 4,
                "data": {
                    "content": content,
                    "flags": 64
                }
            }
            if hidden:
                responsejson["data"]["flags"] = 64
            await session.post(responseurl, json=responsejson)

        async def guildRequired():
            await respond("You must be in a guild to use this command.", True)

        async def permissionDenied():
            await respond("You do not have permission to use this command.", True)

        authorid: int = int(interaction["member"]["user"]["id"]
                            if "member" in interaction else interaction["user"]["id"])
        guild: discord.Guild = None
        if "guild_id" in interaction:
            guild = await dLib.findGuild(interaction["guild_id"])

        if commandname.lower() == "reservations":
            if guild is None:
                await guildRequired()
                return
            elif not await checkResAdmin(guild, authorid):
                await permissionDenied()
                return
            for channel in controlledChannels:
                if channel.interactChannel.id == int(interaction["channel_id"]):
                    await respond("This channel already contains a controlled channel.", True)
                    return
            await respond("Loading Reservation Channel...")
            c = ReserveChannel(None, await dLib.findChannel(interaction["channel_id"]))
            await c.updateText()
            await c.updateImg()
            controlledChannels.append(c)
            await session.delete(f"https://discord.com/api/v8/webhooks/{interaction['application_id']}/{interaction['token']}/messages/@original")
        elif commandname.lower() == "asireservations":
            if guild is None:
                await guildRequired()
                return
            elif not await checkResAdmin(guild, authorid):
                await permissionDenied()
                return
            for channel in controlledChannels:
                if channel.interactChannel.id == int(interaction["channel_id"]):
                    await respond("This channel already contains a controlled channel.", True)
                    return
            await respond("Loading ASI Reservation Channel...")
            c = asiresChannel(None, await dLib.findChannel(interaction["channel_id"]))
            await c.updateText()
            controlledChannels.append(c)
            await session.delete(f"https://discord.com/api/v8/webhooks/{interaction['application_id']}/{interaction['token']}/messages/@original")
        elif commandname.lower() == "stats":
            for channel in controlledChannels:
                if channel.interactChannel.id == int(interaction["channel_id"]):
                    await respond("This channel already contains a controlled channel.", True)
                    return
            await respond("Sent stats creation details to your DMs!", True)
            c = await statsChannel(await dLib.findUser(authorid), await dLib.findChannel(interaction["channel_id"])).asyncInit()
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
                await guildRequired()
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
            await respond(string, True)
        elif commandname.lower() == "adminrank":
            if guild is None:
                await guildRequired()
                return
            elif not await checkResAdmin(guild, authorid):
                await permissionDenied()
                return
            newRankID: int = int(interaction["data"]["options"][0]["value"])
            GuildManager.setAdmin(guild, newRankID)
            await respond(f"Admin rank set to <@&{newRankID}>.", True)
        else:
            await respond("The bot was unable to process this command. Please report with details to the developer.", True)


client.run(token)
