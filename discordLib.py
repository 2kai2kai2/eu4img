from io import BytesIO
import discord
from typing import Union, Optional
from PIL import Image


client: discord.Client = None


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


async def findUser(user: Union[int, str, discord.User, discord.Member]) -> discord.User:
    if isinstance(user, discord.User) or isinstance(user, discord.Member):
        return user
    user = int(user)
    author = client.get_user(user)
    if author is None:
        try:
            author = await client.fetch_user(user)
        except discord.NotFound:
            raise ValueError(f"Could not find discord user with ID {user}")
    return author


async def findMember(member: Union[int, str, discord.User, discord.Member], guild: discord.Guild) -> Optional[discord.Member]:
    if isinstance(member, discord.Member):
        return member
    elif isinstance(member, discord.User):
        member = member.id
    if not isinstance(member, int) and not isinstance(member, str):
        raise TypeError(
            f"Invalid type for Discord member. Invalid object: {member}")
    member = int(member)
    member = guild.get_member(member)
    if member is None:
        try:
            member = await guild.fetch_member(member)
        except discord.Forbidden:
            raise ValueError(
                f"Could not access the guild to find member with user ID {member}")
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


async def findGuild(guild: Union[int, str, discord.Guild]) -> discord.Guild:
    if isinstance(guild, discord.Guild):
        return guild
    elif not isinstance(guild, int) and not isinstance(guild, str):
        raise TypeError(
            f"Invalid type for Discord server. Invalid object: {guild}")

    guild = client.get_guild(int(guild))
    if guild is not None:
        return guild
    try:
        return await client.fetch_guild(int(guild))
    except discord.Forbidden:
        raise ValueError(f"Could not access discord guild with ID {guild}")


async def sendDM(user: Union[str, int, DiscUser], message: str) -> discord.Message:
    """
    Sends a user a specified DM via discord. Returns the discord Message object sent.
    """
    user = findUser(user)
    if user.dm_channel is None:
        await user.create_dm()
    msg = await user.dm_channel.send(message)
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
    server = findGuild(server)

    for role in server.roles:
        if role.name.strip("\n\t @").lower() == roleName.strip("\n\t @").lower():
            return role
    return None
