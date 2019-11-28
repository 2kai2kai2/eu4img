from PIL import Image, ImageDraw, ImageFont
import os
from io import BytesIO, StringIO
import EU4Lib, EU4Reserve
import discord, requests
from dotenv import load_dotenv


load_dotenv()
token = os.getenv('DISCORD_TOKEN')
#imgFinal = Image.open("src//finalTemplate.png")
client = discord.Client()
serverID = os.getenv("DISCORD_SERVER")



def imageToFile(img): #input Image object; return discord.File object
    file = BytesIO()
    img.save(file, "PNG")
    file.seek(0)
    return discord.File(file, "img.png")

async def sendUserMessage(user, message): # user can be id, User object. message can be str
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

async def inquiryStr(user, message):
    if message is not None:
        await sendUserMessage(user, message)
    def check(m):
        return m.channel == user.dm_channel and not m.author.bot
    return (await client.wait_for('message', timeout=300.0, check=check)).content

async def inquiryFile(user, message, type, repeat):
    await sendUserMessage(user, message)
    async def check(m):
        if m.channel == user.dm_channel and not m.author.bot:
            if len(m.attachments) > 0 and m.attachments[0].filename.endswith(type):
                return True
            else:
                await sendUserMessage(user, "Please include a file of the type " + type)
        return False
    file = BytesIO()
    message = await client.wait_for('message', timeout=180.0, check=check)
    await client.wait_until_ready()
    await message.attachments[0].save(file)
    file.seek(0)
    return file

def getRoleFromStr(server, roleName):
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

def checkResAdmin(server, user): # Both can be int id or object
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


class ReserveChannel:
    def __init__(self, id):
        self.id = id
        self.textID = None
        self.imgID = None
        EU4Reserve.writeNewReservation(self.id)
    def setTextID(self, textID):
        self.textID = textID
    def getTextID(self):
        return self.textID
    def setImgID(self, imgID):
        self.imgID = imgID
    def getImgID(self):
        return self.imgID
    async def updateText(self):
        reserve = EU4Reserve.getReserve(str(self.id))
        string = "Current players list:"
        if reserve is None or len(reserve.nations) == 0:
            string = string + "\n*It's so empty here...*"
        else:
            for x in reserve.nations:
                string = string + "\n" + x.player + ": " + EU4Lib.tagToName(x.tag)
        if self.textID is None:
            self.setTextID((await client.get_channel(self.id).send(content=string)).id)
        else:
            await (await (await client.fetch_channel(self.id)).fetch_message(self.getTextID())).edit(content=string)
    async def updateImg(self):
        reserve = EU4Reserve.getReserve(str(self.id))
        if reserve is None:
            reserve = EU4Reserve.Reserve(str(self.id))
        if self.imgID is not None:
            await (await (await client.fetch_channel(self.id)).fetch_message(self.getImgID())).delete()
        self.setImgID((await client.get_channel(self.id).send(file=imageToFile(EU4Reserve.createMap(reserve)))).id)
    async def add(self, nation): # nation should be EU4Reserve.Nation object
        addInt = EU4Reserve.saveAdd(self.id, nation)
        if addInt == 1 or addInt == 2: # Success!
            await self.updateText()
            await self.updateImg()
        elif addInt == 0: # This is not a reserve channel. How did this happen?
            await sendUserMessage(client.get_user(int(nation.player.strip("\n\t <@>"))), "You can't reserve nations in " + client.get_channel(int(self.id)).mention + ".")
        elif addInt == 3: # This nation is already taken
            await sendUserMessage(client.get_user(int(nation.player.strip("\n\t <@>"))), "The nation " + EU4Lib.tagToName(nation.tag) + " is already reserved in " + client.get_channel(int(self.id)).mention + ".")
        return addInt
    async def remove(self, tag): # tag should be nation tag str
        pass
    async def removePlayer(self, name): # name should be player name str
        await self.updateText()
        await self.updateImg()

channels = []


class Nation:
    def __init__(self, player):
        self.player = player
        self.tag = None
        self.development = 0
        self.prestige = None
        self.stability = None
        #self.manpower = None
        #self.maxManpower = None
        self.army = 0.0
        self.navy = 0
        self.debt = 0
        self.treasury = 0.0
        self.totalIncome = 0.0
        self.totalExpense = 0.0
        self.scorePlace = None
        self.capitalID = 0

#Start Data Selection
async def runStats(srcFile, imgPolitical, imgPlayers, user):
    imgFinal = Image.open("src//finalTemplate.png")
    mapFinal = imgPolitical.copy()
    countries = []
    playertags = []
    dlc = []
    GP = []
    lines = srcFile.readlines()
    brackets = []
    playersEditReady = False #so that we can tell if we have scanned through all the players yet or not
    def promptStr():
        prompt = "**Current players list:**```"
        for x in countries:
            prompt += "\n"+x.tag+ ": "+ x.player
        prompt += "```\n**Do you want to make any changes?\nType `'done'` to finish. Commands:\nadd TAG playername\nremove TAG**\n"
        return prompt
    #Reading save file...
    linenum = 0
    for line in lines:
        linenum+=1
        #Separately:
        if playersEditReady == True and not brackets == ["players_countries={"]:
            #Data corrections
            playersEditReady = False #don't do it over and over again
            msg = await sendUserMessage(user, promptStr())
            lastcommand = "null"
            while lastcommand != "done":
                await msg.edit(content=promptStr())
                lastcommand = (await inquiryStr(user, None)).strip("\n ")
                if lastcommand is None:
                    await sendUserMessage(user, "Response timed out. Please try again if you want to continue.")
                    return
                if lastcommand.startswith("add "):
                    tag = lastcommand.partition(" ")[2].partition(" ")[0].strip("\t\n ")
                    name = lastcommand.partition(" ")[2].partition(" ")[2].strip("\t\n ")
                    if len(tag) != 3:
                        await sendUserMessage(user, "Tag length is incorrect. Canceling action.")
                        continue
                    for x in countries:
                        if x.tag == tag: #Players are added later to the list as they join, so we remove all previous players
                            countries.remove(x)
                    countries.append(Nation(name))
                    countries[len(countries)-1].tag = tag.upper().strip("\t \n")
                    playertags.append(tag.upper().strip("\t \n"))
                    
                elif lastcommand.startswith("remove "):
                    tag = lastcommand.partition(" ")[2].strip("\t\n ")
                    if len(tag) != 3:
                        await sendUserMessage(user, "Tag length is incorrect. Canceling action.")
                        continue
                    for nat in countries:
                        if nat.tag.upper().strip("\t \n") == tag.upper().strip("\t \n"):
                            countries.remove(nat)
                            playertags.remove(nat.tag)
                            break
                        elif countries[len(countries)-1] == nat: #This means we are on the last one and elif- it's still not on the list.
                            await sendUserMessage(user,"Did not recognize " + tag.upper() + " as a played nation.")
        #Now the actual stuff

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
                date = line.strip('date=\n')
            #Get save DLC (not sure if we use this...)
            elif brackets == ["dlc_enabled={"]:
                dlc.append(line.strip('\t"\n'))
            #Check if game is mp
            elif "multi_player=" in line and brackets == []:
                if "yes" in line:
                    mp = True
                else:
                    mp = False
            #Get player names and country tags
            elif brackets == ["players_countries={"]:
                playersEditReady = True
                #In the file, the format is like this:
                #players_countries={
                #   "playername"
                #   "SWE"
                #
                #Where "   " is a tab \t
                #This v adds a new Nation object and player name if there is none open.
                if len(countries) == 0 or countries[len(countries)-1].tag is not None:
                    #print("Adding: ", line.strip('\t"\n'))
                    countries.append(Nation(line.strip('\t"\n')))
                #Add country code to most recent country (which, because of ^ will not have a tag)
                else:
                    for x in countries:
                        if x.tag == line.strip('\t"\n'): #Players are added later to the list as they join, so we remove all previous players
                            countries.remove(x)
                    countries[len(countries)-1].tag = line.strip('\t"\n')
                    playertags.append(line.strip('\t"\n'))
                    #print("Country: ", line.strip('\t"\n'))
            #Get current age
            elif "current_age=" in line and brackets == []:
                age = line[12:].strip('"\n')
                #print("\nAge: " + age)
            #Get top 8
            elif "country=" in line and brackets == ["great_powers={", "\toriginal={"]:
                if len(GP) < 8: #Make sure to not include leaving GPs
                    GP.append(line.strip('\tcountry="\n'))
                    #print("Found GP: " + line.strip('\tcountry="\n'))
            #Get HRE emperor tag
            elif "\temperor=" in line and brackets == ["empire={"]:
                HRETag = line.strip('\temperor="\n')
                #print("Found HRE Emperor: " + HRETag)
            #Get Celestial emperor tag
            elif "emperor=" in line and brackets == ["celestial_empire={"]:
                chinaTag = line.strip('\temperor="\n')
                #print("Found Celestial Empire: " + chinaTag)
            #Get target of crusade ('---' if none)
            elif "crusade_target=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
                crusade = line.strip('\tcrusade_target="\n')
                #print("Found crusade target: " + crusade)
            #Get papal controller
            elif "previous_controller=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
                continue
            #Country-specific data (for players)
            elif len(brackets) > 1 and brackets[0] == "countries={" and brackets[1].strip("\t={\n") in playertags:
                for x in countries:
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

    for x in countries: #Remove dead countries from players list
        if x.development == 0:
            playertags.remove(x.tag)
            countries.remove(x)
    #Sort Data:
    countries.sort(key=lambda x: x.development, reverse=True)

    #End Data Selection
    await sendUserMessage(user, "**Processing...**")
    #Start Map Creation
    mapDraw = ImageDraw.Draw(mapFinal)
    for x in range(mapFinal.size[0]):
        for y in range(mapFinal.size[1]):
            #Get color for each pixel
            #In EU4 player mapmode screenshots,
            #Water: (68, 107, 163)
            #AI: (127, 127, 127)
            #Wasteland: (94, 94, 94)
            color = imgPlayers.getpixel((x, y))
            if color == (68, 107, 163) or color == (127, 127, 127) or color == (94, 94, 94):
                #print(round(100*x*y/totalPixels, 2), "% Done (", x, ", ", y, ")")
                continue
            else:
                #All pixels on the edge should be water and wasteland so not get past ^ if, although custom games may break this by not being real pixels
                #TODO: Make no borders for wasteland
                if color != imgPlayers.getpixel((x - 1, y - 1)) or color != imgPlayers.getpixel((x - 1, y)) or color != imgPlayers.getpixel((x - 1, y + 1)) or color != imgPlayers.getpixel((x, y - 1)) or color != imgPlayers.getpixel((x, y + 1)) or color != imgPlayers.getpixel((x + 1, y - 1)) or color != imgPlayers.getpixel((x + 1, y)) or color != imgPlayers.getpixel((x + 1, y + 1)):
                    #Black for player borders
                    mapDraw.point((x, y), (255-color[0], 255-color[1], 255-color[2]))
            #print(round(100*x*y/totalPixels, 2), "% Done (", x, ", ", y, ")")
    #End Map Creation

    #Start Final Img Creation
    imgFinal.paste(mapFinal, (0, imgFinal.size[1]-mapFinal.size[1])) #Copy map into bottom of final image
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
        for nat in countries:
            natnum = countries.index(nat)
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
    year = date.partition(".")[0].strip("\t \n")
    month = date.partition(".")[2].partition(".")[0].strip("\t \n")
    day = date.partition(".")[2].partition(".")[2].strip("\t \n")
    if month == "1":
        imgDraw.text((4880,60), day + " January " + year, (255, 255, 255), font)
    elif month == "2":
        imgDraw.text((4880,60), day + " Feburary " + year, (255, 255, 255), font)
    elif month == "3":
        imgDraw.text((4880,60), day + " March " + year, (255, 255, 255), font)
    elif month == "4":
        imgDraw.text((4880,60), day + " April " + year, (255, 255, 255), font)
    elif month == "5":
        imgDraw.text((4880,60), day + " May " + year, (255, 255, 255), font)
    elif month == "6":
        imgDraw.text((4880,60), day + " June " + year, (255, 255, 255), font)
    elif month == "7":
        imgDraw.text((4880,60), day + " July " + year, (255, 255, 255), font)
    elif month == "8":
        imgDraw.text((4880,60), day + " August " + year, (255, 255, 255), font)
    elif month == "9":
        imgDraw.text((4880,60), day + " September " + year, (255, 255, 255), font)
    elif month == "10":
        imgDraw.text((4880,60), day + " October " + year, (255, 255, 255), font)
    elif month == "11":
        imgDraw.text((4880,60), day + " November " + year, (255, 255, 255), font)
    elif month == "12":
        imgDraw.text((4880,60), day + " December " + year, (255, 255, 255), font)
    return imgFinal

# DISCORD CODE


@client.event
async def on_ready():
    print("EU4 Reserve Bot!")
    print("Prefix: " + os.getenv("PREFIX") + "\n")

@client.event
async def on_message(message):
    if not message.author.bot:
        text = message.content.strip("\n\t ")
        channelID = message.channel.id
        prefix = os.getenv("PREFIX")
        if (text.startswith(prefix)):
            user = message.author
            if (text.upper() == prefix + "UPDATE"):
                for channel in channels:
                    if channel.id == channelID and checkResAdmin(message.guild, user):
                        await message.delete()
                        await channel.updateText()
                        await channel.updateImg()
                        break
            elif (text.upper() == prefix + "NEW") and checkResAdmin(message.guild, user):
                await message.delete()
                c = ReserveChannel(channelID)
                await c.updateText()
                await c.updateImg()
                channels.append(c)
            elif text.upper() == prefix + "END" and checkResAdmin(message.guild, user):
                await message.delete()
                for channel in channels:
                    if channel.id == channelID:
                        channels.remove(channel)
                        await client.get_channel(channelID).send("*Reservations are now ended. Good Luck.*")
            elif text.upper().startswith(prefix + "RESERVE "):
                await message.delete()
                res = text.split(" ", 1)[1].strip("\n\t ")
                for channel in channels:
                    if channel.id == channelID:
                        tag = EU4Lib.country(res)
                        if tag is not None:
                            #await sendUserMessage(user, "You reserved " + tag + ".")
                            await channel.add(EU4Reserve.Nation(user.mention, tag.upper()))
                        else:
                            await sendUserMessage(user, "Your country reservation in " + client.get_channel(channelID).mention + " was not recorded, as \"" + res + "\" was not recognized.")
            elif text.upper() == prefix + "DELRESERVE" or text.upper() == prefix + "DELETERESERVE":
                await message.delete()
                for channel in channels:
                    if channel.id == channelID:
                        await channel.removePlayer(user.mention)
            elif text.upper() == prefix + "STATS" and checkResAdmin(message.guild, user):
                await message.delete()
                saveURL = await inquiryStr(user, "Send a direct link to an uncompressed .eu4 save file:\nYou can do this by uploading to https://www.filesend.jp/l/en-US/ \n then right clicking on the DOWNLOAD to Copy Link Address.")
                if saveURL is None:
                    sendUserMessage(user, "Inquiry timed out. If you still want to post stats, please try again.")
                    return
                response = requests.get(saveURL)
                if not response.status_code == requests.codes.OK:
                    while True:
                        saveURL = await inquiryStr(user, "Something went wrong. Please try a different link.")
                        if saveURL is None:
                            sendUserMessage(user, "Inquiry timed out. If you still want to post stats, please try again.")
                            return
                        response = requests.get(saveURL)
                        if response.status_code == requests.codes.OK:
                            break
                saveFile = StringIO(response.content.decode('ansi'))
                politicalFile = await inquiryFile(user, "Send the Political Mapmode screenshot in this channel (png):", ".png", True)
                if politicalFile is None:
                    sendUserMessage(user, "Inquiry timed out. If you still want to post stats, please try again.")
                    return
                politicalImage = Image.open(politicalFile)
                playersImage = Image.open("src//BlankPlayerMap.png")
                await message.channel.send(file = imageToFile(await runStats(saveFile, politicalImage, playersImage, user)))
            else:
                for channel in channels:
                    if channel.id == channelID:
                        await message.delete()
        else:
            for i in channels:
                if i.id == channelID:
                    await message.delete()

@client.event
async def on_guild_channel_delete(channel):
    for c in channels:
        if c.id == channel.id:
            channels.remove(c)

client.run(token)