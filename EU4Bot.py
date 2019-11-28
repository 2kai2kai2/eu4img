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