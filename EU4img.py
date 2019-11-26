from PIL import Image, ImageDraw, ImageFont
import os
from io import BytesIO
import EU4Lib
import discord
from dotenv import load_dotenv
imgPolitical = Image.open("src//map_1444.png")

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
#imgFinal = Image.open("src//finalTemplate.png")
client = discord.Client()
serverID = os.getenv("DISCORD_SERVER")


#Clears terminal
def clear():
    #print(chr(27) + "[2J")
    #os.system('cls' if os.name == 'nt' else 'clear')
    print("\n" * 1000)

class Nation:
    #def __init__(self, player, tag):
    def __init__(self, tag):
        #self.player = player
        self.tag = tag
        self.capitalID = 0

class Reserve:
    def __init__(self, name):
        self.tags = [] # list of tuples of str
        self.name = name #str
    def add(self, tag):
        self.tags.append(tag)
    def remove(self, tag):
        for i in self.tags:
            if i[0] == tag:
                self.tags.remove(i)
    def getSaveText(self):
        string = self.name + "\n"
        for tag in self.tags:
            string += "\t" + tag[0] + " " + tag[1] + "\n"
        return string

def imageToFile(img): #input Image object; return discord.File object
    file = BytesIO()
    img.save(file, "PNG")
    file.seek(0)
    return discord.File(file, "img.png")

def writeNewReservation(name):
    if not os.path.isfile("savedreservationgames.txt"):
        f = open("savedreservationgames.txt", "w")
        f.write(Reserve(name).getSaveText())
        f.close()
    else:
        reservations = getSavedReserves()
        for r in reservations:
            if r.name == name:
                reservations.remove(r)
        reservations.append(Reserve(name))
        
        text = ""
        for r in reservations:
            text += r.getSaveText()
        f = open("savedreservationgames.txt", "w")
        f.write(text)
        f.close()

def save(reservation, tag):
    reservations = getSavedReserves()
    for r in reservations:
        if r.name == reservation:
            reservations.add(tag)
    
    text = ""
    for r in reservations:
        text += r.getSaveText()
    f = open("savedreservationgames.txt", "w")
    f.write(text)
    f.close()


#Start Data Selection
def createMap(reserve): #input a Reserve object
    countries = [] # List of Nation objects
    for res in reserve.tags:
        print(res[0])
        countries.append(Nation(res[0]))
    mapFinal = imgPolitical.copy()
    srcFile = open("src\\save_1444.eu4", "r")
    lines = srcFile.readlines()
    brackets = []
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
                print("Unexpected brackets at line #" + str(linenum) + ": " + line)
            #print("{")
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:
                print("No brackets to delete.")
                print("Line", linenum, ":", line)
            #print("}")
        #Get rid of long, useless sections
        elif len(brackets) < 0 and ("trade={" == brackets[1] or "provinces={" == brackets[0] or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
            continue
        elif len(brackets) > 1 and brackets[0] == "countries={":
            for x in countries:
                if x.tag in brackets[1]:
                    #Here we have all the stats for country x on the players list
                    if len(brackets) == 2 and "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                            x.capitalID = int(line.strip("\tcapitl=\n"))
    srcFile.close()
    imgX = Image.open("src//xIcon.png")
    for x in countries:
        loc = EU4Lib.province(x.capitalID)
        mapFinal.paste(imgX, (int(loc[0]-imgX.size[0]/2), int(loc[1]-imgX.size[1]/2)), imgX)
        # I hope this doesn't break if a capital is too close to the edge
    return mapFinal

def getSavedReserves():
    reserves = []
    f = open("savedreservationgames.txt", "r")
    currentReserve = None
    while True:
        line = f.readline()
        if line is None or line == "":
            if currentReserve is not None:
                reserves.append(currentReserve)
            return reserves
        elif line.startswith("\t"):
            currentReserve.add(line.strip("\n\t ").split(" ", 1))
        elif not line.startswith("\t") and not line.startswith(" ") and not line == "\n":
            if currentReserve is not None:
                reserves.append(currentReserve)
            currentReserve = Reserve(line.strip("\n\t "))
        else:
            pass # Uh this shouldn't happen unless the file is formatted incorrectly.
    f.close()
    return reserves

def getReserve(name):
    for r in getSavedReserves():
        if r.name == name:
            return r
    return None

class ReserveChannel: #I should make this save
    def __init__(self, id, resName):
        self.id = id
        self.resName = resName
        self.textID = None
        self.imgID = None
    def setTextID(self, textID):
        self.textID = textID
    def getTextID(self):
        return self.textID
    def setImgID(self, imgID):
        self.imgID = imgID
    def getImgID(self):
        return self.imgID
    async def updateText(self):
        reserve = getReserve(self.resName)
        string = "Current players list:"
        if reserve is None or len(reserve.tags) == 0:
            string = string + "\n*It's so empty here...*"
        else:
            for x in reserve.tags:
                string = string + "\n" + x[1] + ": " + x[0]
        if self.textID is None:
            self.setTextID((await client.get_channel(self.id).send(content=string)).id)
        else:
            await (await (await client.fetch_channel(self.id)).fetch_message(self.getTextID())).edit(content=string)
    async def updateImg(self):
        reserve = getReserve(self.resName)
        if self.imgID is not None:
            await (await (await client.fetch_channel(self.id)).fetch_message(self.getImgID())).delete()
        self.setImgID((await client.get_channel(self.id).send(file=imageToFile(createMap(reserve)))).id)

channels = []




# DISCORD CODE


@client.event
async def on_ready():
    pass

@client.event
async def on_message(message):
    if not message.author.bot: #and message.guild.id == serverID:
        text = message.content.strip("\n\t ")
        channelID = message.channel.id
        await message.delete()
        if (text.upper() == "$UPDATE"):
            for channel in channels:
                if channel.id == channelID:
                    await channel.updateText()
                    await channel.updateImg()
                    break
        elif (text.upper() == "$NEW"):
            c = ReserveChannel(channelID, "abc")
            await c.updateText()
            await c.updateImg()
            channels.append(c)
        elif text.upper() == "$END":
            for channel in channels:
                if channel.id == channelID:
                    channels.remove(channel)
                    await client.get_channel(channelID).send("*Reservations are now ended. Good Luck.*")
                

client.run(token)