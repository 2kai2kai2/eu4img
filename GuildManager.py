import json
import os
from typing import List, Optional, Union

import discord
import psycopg2
from dotenv import load_dotenv


""" Data Structure - Json
{
	"<GuildID>": {
		"prefix": "<$>",
		"adminRank": "<@Rank>",
		"announcements": "<ChannelID>",
		"defaultBan": [
			"<TAG>",
			"<TAG>",
			"<TAG>"
		]
	}
}
"""

""" Data Structure - SQL Database
+------+--------+-------+---------------+------------+
| name | prefix | admin | announcements | defaultBan |
| str  | str    | str   | str           | str[]      |
+------+--------+-------+---------------+------------+
"""


class GuildSave:
    def __init__(self, name: Union[str, int], prefix: str = None, admin: str = None, announcements: str = None, defaultBan: List[str] = []):
        self.name = str(name)
        self.prefix = prefix
        self.admin = admin
        self.announcements = announcements
        self.defaultBan = defaultBan

    def toDict(self) -> dict:
        return {"prefix": self.prefix, "adminRank": self.admin, "announcements": self.announcements, "defaultBan": self.defaultBan}


def fileLoadGuilds() -> List[GuildSave]:
    guilds: List[GuildSave] = []
    try:
        with open("guildsave.json", "r") as x:
            jsonLoad: dict = json.load(x)
            x.close()
    except FileNotFoundError:  # There are no reserves.
        return []
    except json.decoder.JSONDecodeError:
        print("Something is wrong with the guilds json formatting. You can try to delete the file to reset.")
        return []
    else:
        if len(jsonLoad) == 0:
            return []
    for gld in jsonLoad:
        guilds.append(GuildSave(gld, jsonLoad[gld]["prefix"], jsonLoad[gld]
                                ["adminRank"], jsonLoad[gld]["announcements"], jsonLoad[gld]["defaultBan"]))
    return guilds


def fileSaveGuilds(guilds: List[GuildSave]):
    jsonSave = {}
    for gld in guilds:
        jsonSave[gld.name] = gld.toDict()
    with open("guildsave.json", "w") as x:
        json.dump(jsonSave, x)
        x.close()


def addGuild(guild: Union[discord.Guild, int], prefix: Optional[str] = "$", admin: Optional[str] = None, conn: Optional[psycopg2.extensions.connection] = None):
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        guilds.append(GuildSave(guildName, prefix, admin))
        fileSaveGuilds(guilds)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            # Somehow we ended up joining a guild we already have saved.
            if cur.fetchone() is not None:
                return  # Do nothing.
            else:
                cur.execute("INSERT INTO Guilds (name, prefix, admin, announcements, defaultBan) VALUES (%s, %s, %s, %s, %s)", [
                            guildName, prefix, admin, None, []])
        finally:
            cur.close()


def setPrefix(guild: Union[discord.Guild, int], prefix: str, conn: Optional[psycopg2.extensions.connection] = None):
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                gld.prefix = prefix
        fileSaveGuilds(guilds)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            current = cur.fetchone()
            if current is None:
                raise ValueError  # This guild is not joined.
            else:
                cur.execute("DELETE FROM Guilds WHERE name=%s", [guildName])
                cur.execute("INSERT INTO Guilds (name, prefix, admin, announcements, defaultBan) VALUES (%s, %s, %s, %s, %s)", [
                            guildName, prefix, current[2], current[3], current[4]])
        finally:
            cur.close()


def setAdmin(guild: Union[discord.Guild, int], admin: str, conn: Optional[psycopg2.extensions.connection] = None):
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                gld.admin = admin
        fileSaveGuilds(guilds)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            current = cur.fetchone()
            if current is None:
                raise ValueError  # This guild is not joined.
            else:
                cur.execute("DELETE FROM Guilds WHERE name=%s", [guildName])
                cur.execute("INSERT INTO Guilds (name, prefix, admin, announcements, defaultBan) VALUES (%s, %s, %s, %s, %s)", [
                            guildName, current[1], admin, current[3], current[4]])
        finally:
            cur.close()


def setAnnouncements(guild: Union[discord.Guild, int], announcements: str, conn: Optional[psycopg2.extensions.connection] = None):
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                gld.announcements = announcements
        fileSaveGuilds(guilds)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            current = cur.fetchone()
            if current is None:
                raise ValueError  # This guild is not joined.
            else:
                cur.execute("DELETE FROM Guilds WHERE name=%s", [guildName])
                cur.execute("INSERT INTO Guilds (name, prefix, admin, announcements, defaultBan) VALUES (%s, %s, %s, %s, %s)", [
                            guildName, current[1], current[2], announcements, current[4]])
        finally:
            cur.close()


def addBan(guild: Union[discord.Guild, int], ban: str, conn: Optional[psycopg2.extensions.connection] = None):
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                gld.defaultBan.append(ban)
        fileSaveGuilds(guilds)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            current = cur.fetchone()
            if current is None:
                raise ValueError  # This guild is not joined.
            else:
                newBanList: List[str] = current[4]
                newBanList.append(ban)
                cur.execute("DELETE FROM Guilds WHERE name=%s", [guildName])
                cur.execute("INSERT INTO Guilds (name, prefix, admin, announcements, defaultBan) VALUES (%s, %s, %s, %s, %s)", [
                            guildName, current[1], current[2], current[3], newBanList])
        finally:
            cur.close()


def removeBan(guild: Union[discord.Guild, int], ban: str, conn: Optional[psycopg2.extensions.connection] = None):
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                try:
                    gld.defaultBan.remove(ban)
                except:
                    pass
        fileSaveGuilds(guilds)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            current = cur.fetchone()
            if current is None:
                raise ValueError  # This guild is not joined.
            else:
                newBanList: List[str] = current[4]
                newBanList.remove(ban)
                cur.execute("DELETE FROM Guilds WHERE name=%s", [guildName])
                cur.execute("INSERT INTO Guilds (name, prefix, admin, announcements, defaultBan) VALUES (%s, %s, %s, %s, %s)", [
                            guildName, current[1], current[2], current[3], newBanList])
        finally:
            cur.close()


def getGuildSave(guild: Union[discord.Guild, int], conn: Optional[psycopg2.extensions.connection] = None) -> GuildSave:
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                return gld
        return None
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
        else:
            current = cur.fetchone()
            cur.close()
            if current is None:
                return None  # This guild is not joined.
            else:
                return GuildSave(current[0], prefix=current[1], admin=current[2], announcements=current[3], defaultBan=current[4])


def removeGuild(guild: Union[discord.Guild, int], conn: Optional[psycopg2.extensions.connection] = None) -> bool:
    if isinstance(guild, discord.Guild):
        guildName: str = str(guild.id)
    elif isinstance(guild, int):
        guildName: str = str(guild)
    else:
        raise TypeError
    # File
    if conn is None:
        removed = False
        guilds = fileLoadGuilds()
        for gld in guilds:
            if gld.name == guildName:
                guilds.remove(gld)
                removed = True
        fileSaveGuilds(guilds)
        return removed
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Guilds WHERE name=%s", [guildName])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Guilds (name varchar, prefix varchar, admin varchar, announcements varchar, defaultBan varchar[])")
            return False
        else:
            current = cur.fetchone()
            cur.close()
            if current is None:
                return False  # This guild is not joined.
            else:
                cur.execute("DELETE FROM Guilds WHERE name=%s", [guildName])
                return True
