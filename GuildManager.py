import os
from typing import Any, Dict, List, Optional, Union

import discord
import dotenv
import pymongo
from pymongo.database import Database

"""
Data Structure
Database: guilds
Collection: index
{
	"guildID": int,
    "adminRank": int|None,
    "announcements": int|None,
    "defaultBan": [
        "TAG",
        "TAG",
        "TAG"
    ]
}
"""

dotenv.load_dotenv()
client = pymongo.MongoClient(
    f"mongodb+srv://{os.environ['MONGODB_USERNAME']}:{os.environ['MONGODB_PASSWORD']}@{os.environ['MONGODB_CLUSTERURL']}/guilds?retryWrites=true&w=majority")
database: Database = client.guilds


def _guildIDType(guild: Union[discord.Guild, int]) -> int:
    """
    Gets a guild id from either the guild or the id.
    """
    if isinstance(guild, discord.Guild):
        return guild.id
    elif isinstance(guild, int):
        return guild
    else:
        raise TypeError(f"{type(guild)} is not a valid type for a guild.")


class GuildSave:
    def __init__(self, guildID: Union[str, int], admin: int = None, announcements: int = None, defaultBan: List[str] = []):
        self.guildID = int(guildID)
        self.admin = admin
        self.announcements = announcements
        self.defaultBan = defaultBan

    def toDict(self) -> dict:
        return {"guildID": self.guildID, "adminRank": self.admin, "announcements": self.announcements, "defaultBan": self.defaultBan}


def addGuild(guild: Union[discord.Guild, int], admin: Optional[int] = None):
    """
    Add a new guild to the database.
    """
    guildID = _guildIDType(guild)
    if admin is not None and not isinstance(admin, int):
        raise TypeError("Admin rank must be an int (role ID).")

    # Check if the guild is already registered
    if database.index.count_documents({"guildID": guildID}) != 0:
        return
    # Add to database
    database.index.insert_one({
        "guildID": guildID,
        "adminRank": admin,
        "announcements": None,
        "defaultBan": []
    })


def removeGuild(guild: Union[discord.Guild, int]) -> bool:
    """
    Removes a specified guild from the list and storage data.
    """
    guildID = _guildIDType(guild)

    return database.index.delete_many({"guildID": guildID}).deleted_count > 0


def getAdmin(guild: Union[discord.Guild, int]) -> int:
    """
    Sets the minimum admin role for a specified guild.
    """
    guildID = _guildIDType(guild)

    return database.index.find_one({"guildID": guildID}, {"adminRank": True})["adminRank"]


def setAdmin(guild: Union[discord.Guild, int], admin: int):
    """
    Sets the minimum admin role for a specified guild.
    """
    guildID = _guildIDType(guild)
    if admin is not None and not isinstance(admin, int):
        raise TypeError("Admin rank must be an int (role ID).")

    database.index.find_one_and_update(
        {"guildID": guildID}, {"$set": {"adminRank": admin}})


def setAnnouncements(guild: Union[discord.Guild, int], announcements: int):
    """
    Sets the announcements channel for a specified guild.
    """
    guildID = _guildIDType(guild)
    if announcements is not None and not isinstance(announcements, int):
        raise TypeError("Announcements channel must be an int (channel ID).")

    database.index.find_one_and_update(
        {"guildID": guildID}, {"$set": {"announcements": announcements}})


def getBan(guild: Union[discord.Guild, int]) -> List[str]:
    """
    Gets the default nation ban list for a specified guild.
    """
    guildID = _guildIDType(guild)

    return database.index.find_one({"guildID": guildID}, {"defaultBan": True})["defaultBan"]


def addBan(guild: Union[discord.Guild, int], ban: str):
    """
    Adds a tag to the default nation ban list for a specified guild.
    """
    guildID = _guildIDType(guild)
    ban = ban.upper()

    database.index.find_one_and_update(
        {"guildID": guildID}, {"$addToSet": {"defaultBan": ban}})


def removeBan(guild: Union[discord.Guild, int], ban: str):
    """
    Removes a tag from the default ban list for a specified guild.
    """
    guildID = _guildIDType(guild)
    ban = ban.upper()

    database.index.find_one_and_update(
        {"guildID": guildID}, {"$pull": {"defaultBan": ban}})


def getGuildSave(guild: Union[discord.Guild, int]) -> GuildSave:
    """
    Gets the GuildSave data for a specified guild.
    """
    guildID = _guildIDType(guild)

    guildDoc: Dict[str, Any] = database.index.find_one({"guildID": guildID})
    if guildDoc is None:
        return None
    return GuildSave(guildDoc["guildID"], guildDoc["adminRank"], guildDoc["announcements"], guildDoc["defaultBan"])
