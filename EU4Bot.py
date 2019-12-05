from PIL import Image, ImageDraw, ImageFont
import os
from random import shuffle
from io import BytesIO, StringIO
import EU4Lib, EU4Reserve
import discord, requests
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from typing import Union, Optional, List


load_dotenv()
token: str = os.getenv('DISCORD_TOKEN')
#imgFinal = Image.open("src//finalTemplate.png")
client = discord.Client()
serverID: str = os.getenv("DISCORD_SERVER")
prefix: str = os.getenv("PREFIX")

DiscUser = Union[discord.User, discord.Member]

def imageToFile(img: Image) -> discord.File:
    """Comverts PIL Images into discord File objects."""

    file = BytesIO()
    img.save(file, "PNG")
    file.seek(0)
    return discord.File(file, "img.png")

async def sendUserMessage(user: Union[str, int, DiscUser], message: str) -> discord.Message:
    """Sends a user a specified DM via discord. Returns the discord Message object sent."""

    u = None
    if isinstance(user, str) or isinstance(user, int): # id
        u = client.get_user(int(user))
    elif isinstance(user, discord.User) or isinstance(user, discord.Member):
        u = user
    else:
        print("ERROR: Could not find discord user to send message.")
        print(user)
        return #pass uh something went wrong
    if u.dm_channel is None:
        await u.create_dm()
    msg = await u.dm_channel.send(message)
    return msg
def getRoleFromStr(server: Union[str, int, discord.Guild], roleName: str) -> Optional[discord.Role]:
    """Converts a string into the role on a specified discord server.
    Use an '@role' string as the roleName argument. (@ is optional)
    Returns None if the role cannot be found."""

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
    s = None
    if isinstance(server, str) or isinstance(server, int):
        s = client.get_guild(int(server))
    elif isinstance(server, discord.Guild):
        s = server
    else: 
        print("ERROR: Could not find discord server to check for admin.")
        return False
    # Get member object
    u = None
    if isinstance(user, str) or isinstance(user, int): # id
        u = s.get_member(int(user))
    elif isinstance(user, discord.User):
        u = s.get_member(user.id)
    elif isinstance(user, discord.Member):
        u = user
    else:
        print("ERROR: Could not find discord user to check for admin.")
        print(user)
        return False #pass uh something went wrong.. false i guess?
    #OK now check
    return getRoleFromStr(s, os.getenv("MIN_ADMIN")) <= u.top_role

class AbstractChannel(ABC):
    @abstractmethod
    def __init__(self, user: DiscUser, initChannel: Union[discord.TextChannel, discord.GroupChannel, discord.DMChannel]):
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
    def __init__(self, user: DiscUser, initChannel: Union[discord.TextChannel, discord.GroupChannel, discord.DMChannel]):
        self.user = None
        self.interactChannel = initChannel
        self.displayChannel = initChannel
        self.textID = None
        self.imgID = None
        EU4Reserve.writeNewReservation(self.interactChannel.id)
    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel
    async def process(self, message: discord.Message):
        text = message.content.strip("\n\t ")
        if text.upper() == prefix + "HELP":
                stringHelp = "__**Command help for " + message.channel.mention + ":**__"
                stringHelp += "\n**" + prefix + "HELP**\nGets you this information!"
                stringHelp += "\n**" + prefix + "RESERVE [nation]**\nReserves a nation or overwrites your previous reservation. Don't include the brackets."
                stringHelp += "\n**" + prefix + "DELRESERVE**\nCancels your reservation."
                if checkResAdmin(message.guild, message.author): # Here we send info about commands only for admins
                    stringHelp += "\n**" + prefix + "END**\nStops allowing reservations and stops the bot's channel management.\nThis should be done by the time the game starts."
                    stringHelp += "\n**" + prefix + "ADMRES [nation] [@user]**\nReserves a nation on behalf of a player on the server.\nMake sure to actually @ the player."
                    stringHelp += "\n**" + prefix + "ADMDELRES [@user]**\nDeletes a player's reservation.\nMake sure to actually @ the player."
                    stringHelp += "\n**" + prefix + "UPDATE**\nUpdates the reservations list. Should usually not be necessary unless in debug or something went wrong."
                await message.delete()
                await sendUserMessage(message.author, stringHelp)
        elif text.upper() == prefix + "UPDATE" and checkResAdmin(message.guild, message.author): # UPDATE
            await message.delete()
            await self.updateText()
            await self.updateImg()
        elif text.upper() == prefix + "END" and checkResAdmin(message.guild, message.author): # END
            await message.delete()
            await self.displayChannel.send("*Reservations are now ended. Good Luck.*")
            interactions.remove(self)
            del(self)
        elif text.upper().startswith(prefix + "RESERVE "): # RESERVE [nation]
            res = text.split(" ", 1)[1].strip("\n\t ")
            tag = EU4Lib.country(res)
            if tag is not None:
                await self.add(EU4Reserve.Nation(message.author.mention, tag.upper()))
            else:
                await sendUserMessage(message.author, "Your country reservation in " + self.displayChannel.mention + " was not recorded, as \"" + res + "\" was not recognized.")
            await message.delete()
        elif text.upper().startswith(prefix + "ADMRES") and checkResAdmin(message.guild, message.author): # ADMRES [nation] @[player]
            if len(message.mentions) == 1:
                res = text.split(" ", 1)[1].replace(message.mentions[0].mention, "").strip("\n\t ")
                tag = EU4Lib.country(res)
                if tag is not None:
                    await self.add(EU4Reserve.Nation(message.mentions[0].mention, tag.upper()))
                else:
                    await sendUserMessage(message.author, "Your reservation for " + message.mentions[0].mention + " in " + self.displayChannel.mention + " was not recorded, as \"" + res + "\" was not recognized.")
            else:
                await sendUserMessage(message.author, "Your reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        elif text.upper() == prefix + "DELRESERVE" or text.upper() == prefix + "DELETERESERVE": # DELRESERVE
            await self.removePlayer(message.author.mention)
            await message.delete()
        elif text.upper().startswith(prefix + "ADMDELRES") and checkResAdmin(message.guild, message.author): # ADMDELRES @[player]
            if len(message.mentions) == 1:
                await self.removePlayer(message.mentions[0].mention)
            else:
                await sendUserMessage(message.author, "Your deletion of a reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        else:
            await message.delete()
    def setTextID(self, textID):
        self.textID = textID
    def getTextID(self):
        return self.textID
    def setImgID(self, imgID):
        self.imgID = imgID
    def getImgID(self):
        return self.imgID
    async def updateText(self):
        reserve = EU4Reserve.getReserve(str(self.interactChannel.id))
        string = "How to reserve: " + prefix + "reserve [nation]\nTo unreserve: " + prefix + "delreserve\n**Current players list:**"
        if reserve is None or len(reserve.nations) == 0:
            string = string + "\n*It's so empty here...*"
        else:
            for x in reserve.nations:
                string = string + "\n" + x.player + ": " + EU4Lib.tagToName(x.tag)
        if self.textID is None:
            self.setTextID((await self.displayChannel.send(content=string)).id)
        else:
            await (await (self.displayChannel).fetch_message(self.getTextID())).edit(content=string)
    async def updateImg(self):
        reserve = EU4Reserve.getReserve(str(self.interactChannel.id))
        if reserve is None:
            reserve = EU4Reserve.Reserve(str(self.interactChannel.id))
        if self.imgID is not None:
            await (await self.interactChannel.fetch_message(self.getImgID())).delete()
        else:
            self.setImgID((await self.displayChannel.send(file=imageToFile(EU4Reserve.createMap(reserve)))).id)
    async def add(self, nation: EU4Reserve.Nation) -> int:
        addInt = EU4Reserve.saveAdd(self.interactChannel.id, nation)
        if addInt == 1 or addInt == 2: # Success!
            await self.updateText()
            await self.updateImg()
        elif addInt == 0: # This is not a reserve channel. How did this happen?
            await sendUserMessage(client.get_user(int(nation.player.strip("\n\t <@>"))), "You can't reserve nations in " + self.displayChannel.mention + ".")
        elif addInt == 3: # This nation is already taken
            await sendUserMessage(client.get_user(int(nation.player.strip("\n\t <@>"))), "The nation " + EU4Lib.tagToName(nation.tag) + " is already reserved in " + self.displayChannel.mention + ".")
        return addInt
    async def remove(self, tag: str):
        pass
    async def removePlayer(self, name: str):
        if EU4Reserve.saveRemove(self.interactChannel.id, name): # If it did anything
            await self.updateText()
            await self.updateImg()
    async def msgdel(self, msgID: Union[str, int]):
        if msgID == self.textID:
            self.textID = None
            await self.updateText()
            await (await self.interactChannel.fetch_message(self.getImgID())).delete()
        if msgID == self.imgID:
            self.imgID = None
            reserve = EU4Reserve.getReserve(str(self.interactChannel.id))
            if reserve is None:
                reserve = EU4Reserve.Reserve(str(self.interactChannel.id))
            self.setImgID((await self.displayChannel.send(file=imageToFile(EU4Reserve.createMap(reserve)))).id)
    async def userdel(self, user: DiscUser):
        if (hasattr(self.displayChannel, 'guild') and self.displayChannel.guild == user.guild) or (hasattr(self.interactChannel, 'guild') and self.interactChannel.guild == user.guild):
            await self.removePlayer(user)
    
class Nation:
    def __init__(self, player):
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

class saveGame():
    def __init__(self):
        self.countries = []
        self.playertags: List[str] = []
        self.dlc: List[str] = []
        self.GP: List[str] = []
        self.date: Optional[str] = None
        self.mp: bool = True
        self.age: Optional[str] = None
        self.HRE: str = None
        self.china: str = None
        self.crusade: str = None

class statsChannel(AbstractChannel):
    def __init__(self, user: DiscUser, initChannel: Union[discord.TextChannel, discord.GroupChannel, discord.DMChannel]):
        self.user = user
        self.interactChannel = None
        self.displayChannel = initChannel
        self.saveFile = None
        self.politicalImage: Image = None
        self.playersImage: Image = Image.open("src//BlankPlayerMap.png")
        self.game = saveGame()
        self.modMsg = None
        self.doneMod = False
    async def asyncInit(self):
        """Does of the init stuff that needs to happen async. Returns self."""

        if self.user.dm_channel is None:
            await self.user.create_dm()
        self.interactChannel = self.user.dm_channel
        await self.interactChannel.send("**Send EITHER an uncompressed .eu4 save file\nor a direct link to an uncompressed .eu4 save file:**\nYou can do this by uploading to https://www.filesend.jp/l/en-US/ \n then right clicking on the DOWNLOAD to Copy Link Address.")
        return self
    def modPromptStr(self) -> str:
        """Makes and returns a string giving information for player list modification."""

        prompt = "**Current players list:**```"
        for x in self.game.countries:
            prompt += "\n"+x.tag+ ": "+ x.player
        #prompt += "```\n**Do you want to make any changes?\nType `'done'` to finish. Commands:\nadd TAG playername\nremove TAG**\n"
        prompt += "```\n**Do you want to make any changes?\nType `'done'` to finish. Commands:\nremove TAG**\n"
        return prompt
    async def readFile(self):
        """Gets all data from self.saveFile and saves it to the self.game"""

        lines = self.saveFile.readlines()
        brackets = []
        
        #Reading save file...
        linenum = 0
        for line in lines:
            linenum+=1
            if "{" in line:
                if line.count("{") == line.count("}"):
                    continue
                elif line.count("}") == 0 and line.count("{") == 1:
                    brackets.append(line.rstrip("\n "))
                elif line.count("}") == 0 and line.count("{") > 1:
                    for x in range(line.count("{")):
                        brackets.append("{") #TODO: fix this so it has more
                else:
                    #print("Unexpected brackets at line #" + str(linenum) + ": " + line)
                    pass
                #print("{")
            elif "}" in line:
                try:
                    brackets.pop()
                except IndexError:
                    #print("No brackets to delete.")
                    #print("Line", linenum, ":", line)
                    pass
                #print("}")
            #Get rid of long, useless sections
            elif len(brackets) < 0 and ("trade={" == brackets[1] or "provinces={" == brackets[0] or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
                continue
            else:
                #This is where we do stuff
                #Get current gamedate
                if line.startswith("date=") and brackets == []:
                    self.game.date = line.strip('date=\n')
                #Get save DLC (not sure if we use this...)
                elif brackets == ["dlc_enabled={"]:
                    self.game.dlc.append(line.strip('\t"\n'))
                #Check if game is mp
                elif "multi_player=" in line and brackets == []:
                    if "yes" in line:
                        self.game.mp = True
                    else:
                        self.game.mp = False
                #Get player names and country tags
                elif brackets == ["players_countries={"]:
                    #In the file, the format is like this:
                    #players_countries={
                    #   "playername"
                    #   "SWE"
                    #
                    #Where "   " is a tab \t
                    #This v adds a new Nation object and player name if there is none open.
                    if len(self.game.countries) == 0 or self.game.countries[len(self.game.countries)-1].tag is not None:
                        #print("Adding: ", line.strip('\t"\n'))
                        self.game.countries.append(Nation(line.strip('\t"\n')))
                    #Add country code to most recent country (which, because of ^ will not have a tag)
                    else:
                        for x in self.game.countries:
                            if x.tag == line.strip('\t"\n'): #Players are added later to the list as they join, so we remove all previous players
                                self.game.countries.remove(x)
                        self.game.countries[len(self.game.countries)-1].tag = line.strip('\t"\n')
                        self.game.playertags.append(line.strip('\t"\n'))
                        #print("Country: ", line.strip('\t"\n'))
                #Get current age
                elif "current_age=" in line and brackets == []:
                    self.game.age = line[12:].strip('"\n')
                    #print("\nAge: " + age)
                #Get top 8
                elif "country=" in line and brackets == ["great_powers={", "\toriginal={"]:
                    if len(self.game.GP) < 8: #Make sure to not include leaving GPs
                        self.game.GP.append(line.strip('\tcountry="\n'))
                        #print("Found GP: " + line.strip('\tcountry="\n'))
                #Get HRE emperor tag
                elif "\temperor=" in line and brackets == ["empire={"]:
                    self.game.HRE = line.strip('\temperor="\n')
                    #print("Found HRE Emperor: " + HRETag)
                #Get Celestial emperor tag
                elif "emperor=" in line and brackets == ["celestial_empire={"]:
                    self.game.china = line.strip('\temperor="\n')
                    #print("Found Celestial Empire: " + chinaTag)
                #Get target of crusade ('---' if none)
                elif "crusade_target=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
                    self.game.crusade = line.strip('\tcrusade_target="\n')
                    #print("Found crusade target: " + crusade)
                #Get papal controller
                elif "previous_controller=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
                    continue
                #Country-specific data (for players)
                elif len(brackets) > 1 and brackets[0] == "countries={" and brackets[1].strip("\t={\n") in self.game.playertags:
                    for x in self.game.countries:
                        if x.tag in brackets[1]:
                            #Here we have all the stats for country x on the players list
                            if len(brackets) == 2:
                                if "raw_development=" in line:
                                    x.development = round(float(line.strip("\traw_devlopmnt=\n")))
                                elif "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                                    x.capitalID = int(line.strip("\tcapitl=\n"))
                                elif "score_place=" in line:
                                    x.scorePlace = round(float(line.strip("\tscore_place=\n")))
                                elif "prestige=" in line:
                                    x.prestige = round(float(line.strip("\tprestige=\n")))
                                elif "stability=" in line:
                                    x.stability = round(float(line.strip("\tstability=\n")))
                                elif "treasury=" in line:
                                    x.treasury = round(float(line.strip("\ttreasury=\n")))
                                #elif "\tmanpower=" in line:
                                    #x.manpower = round(float(line.strip("\tmanpower=\n")))
                                #elif "max_manpower=" in line:
                                    #x.maxManpower = round(float(line.strip("\tmax_manpower=\n")))
                                else: continue
                            elif len(brackets) == 3:
                                #Get each loan and add its amount to debt
                                if brackets[2] == "\t\tloan={" and "amount=" in line:
                                    x.debt += round(float(line.strip("\tamount=\n")))
                                #Get Income from the previous month
                                elif brackets[2] == "\t\tledger={" and "\tlastmonthincome=" in line:
                                    x.totalIncome = round(float(line.strip("\tlastmonthincome=\n")), 2)
                                #Get Expense from the previous month
                                elif brackets[2] == "\t\tledger={" and "\tlastmonthexpense=" in line:
                                    x.totalExpense = round(float(line.strip("\tlastmonthexpense=\n")), 2)
                            elif len(brackets) == 4:
                                #Add 1 to army size for each regiment
                                if brackets[2] == "\t\tarmy={" and "regiment={" in brackets[3] and "morale=" in line:
                                    x.army = x.army + 1000
                                #Subtract damage done to units from army size
                                #This needs to be separate from ^ because for full regiments there is no "strength=" tag
                                elif brackets[2] == "\t\tarmy={" and "regiment={" in brackets[3] and "strength=" in line:
                                    try:
                                        x.army = round(x.army - 1000 + 1000*float(line.strip("\tstrength=\n")))
                                    except ValueError:
                                        continue
                                #Add 1 for each ship
                                elif brackets[2] == "\t\tnavy={" and brackets[3] == "\t\t\tship={" and "\thome=" in line:
                                    x.navy += 1

        for x in self.game.countries: #Remove dead countries from players list
            if x.development == 0:
                self.game.playertags.remove(x.tag)
                self.game.countries.remove(x)
        if self.game.GP == [] or self.game.date == None or self.game.age == None: # These signify that it's probably not a valid save file.
            raise Exception("This probably isn't a valid .eu4 uncompressed save file from " + self.user.mention)
        #Sort Data:
        self.game.countries.sort(key=lambda x: x.development, reverse=True)
    async def generateImage(self) -> Image:
        """Returns a stats Image based off the self.game data."""

        imgFinal = Image.open("src//finalTemplate.png")
        mapFinal = self.politicalImage.copy()
        #End Data Selection
        await self.interactChannel.send("**Processing...**")
        #Start Map Creation
        mapDraw = ImageDraw.Draw(mapFinal)
        for x in range(mapFinal.size[0]):
            for y in range(mapFinal.size[1]):
                #Get color for each pixel
                #In EU4 player mapmode screenshots,
                #Water: (68, 107, 163)
                #AI: (127, 127, 127)
                #Wasteland: (94, 94, 94)
                color = self.playersImage.getpixel((x, y))
                if color == (68, 107, 163) or color == (127, 127, 127) or color == (94, 94, 94):
                    #print(round(100*x*y/totalPixels, 2), "% Done (", x, ", ", y, ")")
                    continue
                else:
                    #All pixels on the edge should be water and wasteland so not get past ^ if, although custom games may break this by not being real pixels
                    #TODO: Make no borders for wasteland
                    if color != self.playersImage.getpixel((x - 1, y - 1)) or color != self.playersImage.getpixel((x - 1, y)) or color != self.playersImage.getpixel((x - 1, y + 1)) or color != self.playersImage.getpixel((x, y - 1)) or color != self.playersImage.getpixel((x, y + 1)) or color != self.playersImage.getpixel((x + 1, y - 1)) or color != self.playersImage.getpixel((x + 1, y)) or color != self.playersImage.getpixel((x + 1, y + 1)):
                        #Black for player borders
                        mapDraw.point((x, y), (255-color[0], 255-color[1], 255-color[2]))
                #print(round(100*x*y/totalPixels, 2), "% Done (", x, ", ", y, ")")
        #End Map Creation

        #Start Final Img Creation
        imgFinal.paste(mapFinal, (0, imgFinal.size[1]-mapFinal.size[1])) #Copy map into bottom of final image
        del(mapFinal)

        #The top has 5632x1119
        fontsmall = ImageFont.load_default()
        font = ImageFont.load_default()
        fontbig = ImageFont.load_default()
        try:
            fontsmall = ImageFont.truetype("FONT.TTF", 50)
            font = ImageFont.truetype("FONT.TTF", 100)
            fontbig = ImageFont.truetype("FONT.TTF", 180)
        except(FileNotFoundError, IOError):
            try:
                fontsmall = ImageFont.truetype("GARA.TTF", 50)
                font = ImageFont.truetype("GARA.TTF", 100)
                fontbig = ImageFont.truetype("GARA.TTF",180)
            except(FileNotFoundError, IOError):
                fontsmall = ImageFont.load_default()
                font = ImageFont.load_default()
                fontbig = ImageFont.load_default()
        imgDraw = ImageDraw.Draw(imgFinal)
        #================MULTIPLAYER================#
        if True:#mp == True:
            #Players section from (20,30) to (4710, 1100) half way is x=2345
            #So start with yborder = 38, yheight = 128 for each player row. x just make it half or maybe thirds depending on how it goes
            for nat in self.game.countries:
                natnum = self.game.countries.index(nat)
                x = 38 + 2335*int(natnum/8) #We have 2335 pixels to work with maximum for each player column
                y = 38 + 128*(natnum%8)
                if (natnum < 16):
                    #x: Country flag
                    imgFinal.paste(EU4Lib.flag(nat.tag), (x, y))
                    #x+128: Player
                    imgDraw.text((x+128, y), nat.player, (255, 255, 255), font)
                    #x+760: Army size
                    imgFinal.paste(Image.open("src//army.png"), (x+760, y))
                    armydisplay = str(round(nat.army/1000, 1))
                    if armydisplay.endswith(".0") or ("." in armydisplay and len(armydisplay) > 4):
                        armydisplay = armydisplay.partition(".")[0]
                    armydisplay = armydisplay + "k"
                    imgDraw.text((x+760+128, y), armydisplay, (255, 255, 255), font)
                    #x+1100: Navy size
                    imgFinal.paste(Image.open("src//navy.png"), (x+1100, y))
                    imgDraw.text((x+1100+128, y), str(nat.navy), (255, 255, 255), font)
                    #x+1440: Development
                    imgFinal.paste(Image.open("src//development.png"), (x+1440, y))
                    imgDraw.text((x+1440+128, y), str(nat.development), (255, 255, 255), font)
                    #x+1780: Income/Expense
                    monthlyProfit = nat.totalIncome-nat.totalExpense
                    imgIncome = Image.open("src//income.png")
                    if monthlyProfit < 0:
                        imgIncome = imgIncome.crop((128, 0, 255, 127))
                        imgFinal.paste(imgIncome, (x+1780, y))
                        imgDraw.text((x+1780+128, y), str(round(nat.totalIncome - nat.totalExpense)), (247, 16, 16), font)
                    else:
                        imgIncome = imgIncome.crop((0, 0, 127, 127))
                        imgFinal.paste(imgIncome, (x+1780, y))
                        imgDraw.text((x+1780+128, y), str(round(nat.totalIncome - nat.totalExpense)), (49, 190, 66), font)
                    imgDraw.text((x+2130, y), "+" + str(round(nat.totalIncome, 2)), (49, 190, 66), fontsmall)
                    imgDraw.text((x+2130, y+64), "-" + str(round(nat.totalExpense, 2)), (247, 16, 16), fontsmall)
                    #Possible TODO:
                    #navy_strength
                    #manpower
                    #max_manpower
                    #max_sailors
                else:
                    pass
                    #print(nat.tag + " does not fit!")
        #================SINGLEPLAYER================#
        else:
            pass
            #print("Unfortunately, Singleplayer does not work yet. ):")
        #================END  SECTION================#
        #Date
        year = self.game.date.partition(".")[0].strip("\t \n")
        month = self.game.date.partition(".")[2].partition(".")[0].strip("\t \n")
        day = self.game.date.partition(".")[2].partition(".")[2].strip("\t \n")
        if month == "1":
            imgDraw.text((4880,60), day + " January " + year, (255, 255, 255), font) #Good
        elif month == "2":
            imgDraw.text((4880-40,60), day + " Feburary " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "3":
            imgDraw.text((4880-20,60), day + " March " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "4":
            imgDraw.text((4880-20,60), day + " April " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "5":
            imgDraw.text((4880+50,60), day + " May " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "6":
            imgDraw.text((4880+50,60), day + " June " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "7":
            imgDraw.text((4880+50,60), day + " July " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "8":
            imgDraw.text((4880,60), day + " August " + year, (255, 255, 255), font) # Good
        elif month == "9":
            imgDraw.text((4880-45,60), day + " September " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "10":
            imgDraw.text((4880-25,60), day + " October " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "11":
            imgDraw.text((4880-60,60), day + " November " + year, (255, 255, 255), font) # Shift changed; need testing
        elif month == "12":
            imgDraw.text((4880-60,60), day + " December " + year, (255, 255, 255), font) # Shift changed; need testing
        return imgFinal
    
    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel and message.author.bot == False
    async def process(self, message: discord.Message):
        if message.content.upper() == prefix + "CANCEL":
            await self.interactChannel.send("**Cancelling the stats operation.**")
            interactions.remove(self)
            del(self)
        elif self.saveFile is None:
            if len(message.attachments) > 0 and message.attachments[0].filename.endswith(".eu4"):
                try:
                    self.saveFile = StringIO((await message.attachments[0].read()).decode('ansi'))
                except:
                    await self.interactChannel.send("**Something went wrong in decoding your .eu4 file.**\nThis may mean your file is not an eu4 save file, or has been changed from the ANSI encoding.\n**Please try another file or change the file's encoding and try again.**")
                    self.saveFile = None
                    return
            else: #str
                saveURL = message.content.strip("\n\t ")
                response = requests.get(saveURL)
                if response.status_code == 200: #200 == requests.codes.ok
                    try:
                        self.saveFile = StringIO(response.content.decode('ansi'))
                    except:
                        await self.interactChannel.send("**Something went wrong in decoding your .eu4 file.**\nThis may mean your file is not an eu4 save file, or has been changed from the ANSI encoding.\n**Please try another file or change the file's encoding and try again.**")
                        self.saveFile = None
                        return
                else:
                    await self.interactChannel.send("Something went wrong. Please try a different link.")
                    return
            await self.interactChannel.send("**Recieved save file. Processing...**")
            try:
                await self.readFile()
            except:
                await self.interactChannel.send("**Uh oh! something went wrong.**\nIt could be that your save file was incorrectly formatted. Is it uncompressed?\n**Please try another file.**")
                self.saveFile = None
                return
            await self.interactChannel.send("**Send the Political Mapmode screenshot in this channel (png):**")
        elif (self.saveFile is not None) and (self.politicalImage is None):
            if len(message.attachments) > 0 and message.attachments[0].filename.endswith(".png"):
                politicalFile = BytesIO()
                await message.attachments[0].save(politicalFile)
                self.politicalImage = Image.open(politicalFile)
                if self.politicalImage.size != (5632, 2048):
                    await self.interactChannel.send("**Your image was not the right size.** (5632, 2048)\nDid you submit a Political Mapmode screenshot? (f10)\n**Please try another image.**")
                    self.politicalImage = None
                    return
                self.modMsg = await self.interactChannel.send(self.modPromptStr())
        elif (self.saveFile is not None) and (self.politicalImage is not None) and (not self.doneMod):
            if message.content.strip("\n\t ") == "done":
                self.doneMod == True
                try:
                    await self.displayChannel.send(file = imageToFile(await self.generateImage()))
                except:
                    await self.interactChannel.send("**Image generation failed!**\nPerhaps something was wrong with one of the files?\n**Try " + prefix + "stats again after checking that the files are valid and unchanged from their creation.**")
                else:
                    await self.interactChannel.send("**Image posted to " + self.displayChannel.mention + "**")
                interactions.remove(self)
                del(self)
            #elif message.content.strip("\n\t ").startswith("add "):
            #    tag = message.content.strip("\n\t ").partition(" ")[2].partition(" ")[0].strip("\t\n ")
            #    name = message.content.strip("\n\t ").partition(" ")[2].partition(" ")[2].strip("\t\n ")
            #    if len(tag) != 3:
            #        await sendUserMessage(self.user, "Tag length is incorrect. Canceling action.")
            #        return
            #    for x in self.game.countries:
            #        if x.tag == tag: #Players are added later to the list as they join, so we remove all previous players
            #            self.game.countries.remove(x)
            #    self.game.countries.append(Nation(name))
            #    self.game.countries[len(self.game.countries)-1].tag = tag.upper().strip("\t \n")
            #    self.game.playertags.append(tag.upper().strip("\t \n"))
                
            elif message.content.strip("\n\t ").startswith("remove "):
                tag = message.content.strip("\n\t ").partition(" ")[2].strip("\t\n ")
                if len(tag) != 3:
                    await self.interactChannel.send("Tag length is incorrect. Canceling action.")
                    return
                for nat in self.game.countries:
                    if nat.tag.upper().strip("\t \n") == tag.upper().strip("\t \n"):
                        self.game.countries.remove(nat)
                        self.game.playertags.remove(nat.tag)
                        await self.modMsg.edit(content = self.modPromptStr())
                        break
                    elif self.game.countries[len(self.game.countries)-1] == nat: #This means we are on the last one and elif- it's still not on the list.
                        await self.interactChannel.send("Did not recognize " + tag.upper() + " as a played nation.")
    async def msgdel(self, msgID: Union[str, int]):
        pass
    async def userdel(self, user: DiscUser):
        if user == self.user:
            try:
                await self.interactChannel.send("You left the " + self.displayChannel.guild.name + " discord server, so this interaction is cancelled.")
            except: # This means the account was deleted. Oh well.
                pass
            interactions.remove(self)
            del(self)



class asiReserve:
    """A user's reservation for an ASI game."""

    def __init__(self, user: DiscUser):
        self.user: DiscUser = user
        self.picks = None

class asiresChannel(AbstractChannel): # This is custom for my discord group. Anybody else can ignore it or do what you will.
    def __init__(self, user: DiscUser, initChannel: Union[discord.TextChannel, discord.GroupChannel, discord.DMChannel]):
        self.user = None
        self.interactChannel = initChannel
        self.displayChannel = initChannel
        self.textID = None
        self.reserves: List[asiReserve] = []
    async def responsive(self, message: discord.Message) -> bool:
        return message.channel == self.interactChannel
    async def process(self, message: discord.Message):
        text = message.content.strip("\n\t ")
        if text.upper() == prefix + "HELP":
                stringHelp = "__**Command help for " + message.channel.mention + ":**__"
                stringHelp += "\n**" + prefix + "HELP**\nGets you this information!"
                stringHelp += "\n**" + prefix + "RESERVE [nation1], [nation2], [nation3]**\nReserves your picks or overwrites your previous reservation.\nThese are in the order of first pick to third. Don't include the brackets."
                stringHelp += "\n**" + prefix + "DELRESERVE**\nCancels your reservation."
                if checkResAdmin(message.guild, message.author): # Here we send info about commands only for admins
                    stringHelp += "\n**" + prefix + "END**\nStops allowing reservations and stops the bot's channel management.\nThen runs and displays the draft. Draft may need to be rearranged manually to ensure game balance."
                    stringHelp += "\n**" + prefix + "ADMRES [nation1], [nation2], [nation3] [@user]**\nReserves picks on behalf of a player on the server.\nMake sure to actually @ the player."
                    stringHelp += "\n**" + prefix + "ADMDELRES [@user]**\nDeletes a player's reservation.\nMake sure to actually @ the player."
                    stringHelp += "\n**" + prefix + "UPDATE**\nUpdates the reservations list. Should usually not be necessary unless in debug or something went wrong."
                await message.delete()
                await sendUserMessage(message.author, stringHelp)
        elif text.upper() == prefix + "UPDATE" and checkResAdmin(message.guild, message.author): # UPDATE
            await message.delete()
            await self.updateText()
        elif text.upper() == prefix + "END" and checkResAdmin(message.guild, message.author): # END
            await message.delete()
            finalReserves = [] # List of EU4Reserve.Nation objects
            shuffle(self.reserves)
            for res in self.reserves:
                finaltag = None
                for tag in res.picks:
                    for x in finalReserves:
                        if x.tag.upper() == tag.upper():
                            break
                    else: # This means they get this tag
                        finaltag = tag
                        break
                finalReserves.append(EU4Reserve.Nation(res.user.mention, finaltag))
            # At this point the finalReserves list is complete with all finished reserves. If a player had no reserves they could take, their tag is None
            string = "**Reserves are finished. The following are the draft order:**"
            count = 1
            for res in finalReserves:
                if res.tag is None:
                    string += "\n" + str(count) + " " + res.player + ": *[all taken]*"
                else:
                    string += "\n" + str(count) + " " + res.player + ": " + EU4Lib.tagToName(res.tag)
                count += 1
            await self.displayChannel.send(string)
            # aaand we're done!
            interactions.remove(self)
            del(self)
        elif text.upper().startswith(prefix + "RESERVE "):
            await self.add(message.author, text.split(" ", 1)[1].strip("\n\t ")) # RESERVE [nation1], [nation2], [nation3]
            await message.delete()
            await self.updateText()
        elif text.upper().startswith(prefix + "ADMRES") and checkResAdmin(message.guild, message.author): # ADMRES [nation1], [nation2], [nation3] @[player]
            if len(message.mentions) == 1:
                res = text.split(" ", 1)[1].strip("\n\t ").replace(message.mentions[0].mention, "")
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
                await self.add(message.mentions[0], res) # at this point the reservation should be valid, because otherwise add will send the faliure to the target.
                await self.updateText()
            else:
                await sendUserMessage(message.author, "Your reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        elif text.upper() == prefix + "DELRESERVE" or text.upper() == prefix + "DELETERESERVE": # DELRESERVE
            await self.remove(message.author)
            await message.delete()
            await self.updateText()
        elif text.upper().startswith(prefix + "ADMDELRES") and checkResAdmin(message.guild, message.author): # ADMDELRES @[player]
            if len(message.mentions) == 1:
                await self.remove(message.mentions[0].mention)
                await self.updateText()
            else:
                await sendUserMessage(message.author, "Your deletion of a reservation in " + self.displayChannel.mention + " needs to @ a player.")
            await message.delete()
        else:
            await message.delete()
    async def updateText(self):
        string = "How to reserve: " + prefix + "reserve [nation1], [nation2], [nation3]\nTo unreserve: " + prefix + "delreserve\n**Current players list:**"
        if len(self.reserves) == 0:
            string += "\n*It's so empty here...*"
        else:
            for x in self.reserves:
                string += "\n" + x.user.mention + ": " + EU4Lib.tagToName(x.picks[0]) + ", " + EU4Lib.tagToName(x.picks[1]) + ", " + EU4Lib.tagToName(x.picks[2])
        if self.textID is None:
            self.textID = (await self.displayChannel.send(content=string)).id
        else:
            await (await (self.displayChannel).fetch_message(self.textID)).edit(content=string)
    async def remove(self, user: DiscUser):
        for res in self.reserves:
            if res.user == user:
                self.reserves.remove(res)
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
        res = asiReserve(user)
        res.picks = tags
        await self.remove(user)
        self.reserves.append(res)
    async def msgdel(self, msgID: Union[str, int]):
        if msgID == self.textID:
            self.textID = None
            await self.updateText()
    async def userdel(self, user: DiscUser):
        await self.remove(user)
        await self.updateText()

#Start Data Selection


# DISCORD CODE
interactions: List[AbstractChannel] = []

@client.event
async def on_ready():
    print("EU4 Reserve Bot!")
    print("Prefix: " + os.getenv("PREFIX") + "\n")

@client.event
async def on_message(message: discord.Message):
    if not message.author.bot:
        text = message.content.strip("\n\t ")
        for interaction in interactions: # Should be only abstractChannel descendants
            if await interaction.responsive(message):
                await interaction.process(message)
                return
        if (text.startswith(prefix)):
            if text.upper() == prefix + "HELP":
                stringHelp = "__**Command help:**__"
                stringHelp += "\n**" + prefix + "HELP**\nGets you this information!"
                if checkResAdmin(message.guild, message.author): # Here we send info about commands only for admins
                    stringHelp += "\n**" + prefix + "NEW**\nTurns the text channel into a reservation channel\n(more commands within that; use this command in it for info)"
                    stringHelp += "\n**" + prefix + "STATS**\nCreates a eu4 stats image in the channel.\nUses DMs to gather the necessary files for creation."
                    stringHelp += "\n**" + prefix + "NEWASI**\nTurns the text channel into a ASI reservation channel\nThis is specific to my discord."
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

@client.event
async def on_guild_channel_delete(channel):
    for c in interactions:
        if c.displayChannel == channel or c.interactChannel == channel:
            interactions.remove(c)
            del(c)

@client.event
async def on_private_channel_delete(channel):
    for c in interactions:
        if c.displayChannel == channel or c.interactChannel == channel:
            interactions.remove(c)
            del(c)

@client.event
async def on_raw_message_delete(payload):
    for c in interactions:
        await c.msgdel(payload.message_id)

@client.event
async def on_member_remove(member: DiscUser):
    for c in interactions:
        await c.userdel(member)

@client.event
async def on_guild_remove(guild: discord.Guild):
    for c in interactions:
        if (hasattr(c.displayChannel, 'guild') and c.displayChannel.guild == guild) or (hasattr(c.interactChannel, 'guild') and c.interactChannel.guild == guild):
            interactions.remove(c)
            del(c)

client.run(token)