from PIL import Image, ImageDraw, ImageFont
import os
from io import BytesIO
import EU4Lib, EU4Reserve
import discord
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
    await u.dm_channel.send(message)
    print("Sent message \"" + message + "\" to " + user.mention + ".")

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
        self.setImgID((await client.get_channel(self.id).send("[image]")).id)#file=imageToFile(EU4Reserve.createMap(reserve)))).id)
    async def add(self, nation): # nation should be EU4Reserve.Nation object
        EU4Reserve.saveAdd(self.id, nation)
        await self.updateText()
        await self.updateImg()
    async def remove(self, tag): # tag should be nation tag str
        pass
    async def removePlayer(self, name): # name should be player name str
        EU4Reserve.saveRemove(self.id, name)
        await self.updateText()
        await self.updateImg()

channels = []




# DISCORD CODE


@client.event
async def on_ready():
    pass

@client.event
async def on_message(message):
    if not message.author.bot:
        text = message.content.strip("\n\t ")
        channelID = message.channel.id
        if (text.startswith(os.getenv("PREFIX"))):
            user = message.author
            await message.delete()
            if (text.upper() == "$UPDATE"):
                for channel in channels:
                    if channel.id == channelID:
                        await channel.updateText()
                        await channel.updateImg()
                        break
            elif (text.upper() == "$NEW"):
                c = ReserveChannel(channelID)
                await c.updateText()
                await c.updateImg()
                channels.append(c)
            elif text.upper() == "$END":
                for channel in channels:
                    if channel.id == channelID:
                        channels.remove(channel)
                        await client.get_channel(channelID).send("*Reservations are now ended. Good Luck.*")
            elif text.upper().startswith("$RESERVE "):
                res = text.split(" ", 1)[1].strip("\n\t ")
                for channel in channels:
                    if channel.id == channelID:
                        tag = EU4Lib.country(res)
                        if tag is not None:
                            #await sendUserMessage(user, "You reserved " + tag + ".")
                            await channel.add(EU4Reserve.Nation(user.mention, tag.upper()))
                        else:
                            await sendUserMessage(user, "Your country reservation in " + client.get_channel(channelID).mention + " was not recorded, as \"" + res + "\" was not recognized.")
            elif text.upper() == "$DELRESERVE" or text.upper() == "$DELETERESERVE":
                for channel in channels:
                    if channel.id == channelID:
                        await channel.removePlayer(user.mention)
        else:
            for i in channels:
                if i.id == channelID:
                    await message.delete()
                

client.run(token)