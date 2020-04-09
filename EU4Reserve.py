import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Union
import time
import datetime

import psycopg2
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

import EU4Lib


""" Data Structure - Python side
AbstractReserve ("Reserve")
    players: List[AbstractPick ("Pick")]
        player: str; user mention
    name: str; Channel ID as a str
    textmsg: int; the msg ID in the channel
"""

""" Data Structure - JSON Formatting
In Python, this becomes a dict.

{
    "<ChannelID>": {
        "kind": "reserve",
        "textmsg": 1234567890,
        "imgmsg": 1234567890,
        "reserves": [
        {
            "player": "<PlayerMention>",
            "tag": "<TAG>",
            "time": 1234567
        },
        {...}
        ],
        "bans": [
            "<TAG>",
            "<TAG>",
            "<TAG>"
        ]
    },
    "<ChannelID>": {
        "kind": "asi",
        "textmsg": 1234567890,
        "reserves": [
            {
                "player": "<PlayerMention>",
                "priority": false,
                "picks": [
                    "<TAG>",
                    "<TAG>",
                    "<TAG>"
                ]
            },
            {
                "player": "<PlayerMention>",
                "priority": true,
                "picks": [
                    "<TAG>"
                ],
                "time": 1234567
            }
        ]
    }
}
"""

""" Data Structure - SQL Database
Reserves
+------+------+-------+----------+
| name | kind | ban   | specdata |
| str  | str  | str[] | str[]    |
+------+------+-------+----------+
kind:
    Reserve - 'reserve'
    ASIReserve - 'asi'
specdata:
    Reserve - [<textmsgID>, <imgmsgID>]
    ASIReserve - [<textmsgID>]

ReservePicks
+---------+--------+-----+--------+
| reserve | player | tag | time   |
| str     | str    | str | bigint |
+---------+--------+-----+--------+
reserve refers to the name of the Reserve in the Reserves table this pick is for.

ASIPicks
+---------+--------+------+------+------+--------+
| reserve | player | tag1 | tag2 | tag3 | time   |
| str     | str    | str  | str  | str  | bigint |
+---------+--------+------+------+------+--------+
reserve refers to the name of the ASIReserve in the Reserves table this pick is for.
If the pick is priority, tag2 and tag3 are 'NULL' (a str).
"""

class Eastern(datetime.tzinfo):
    def __init__(self):
        pass
    def dst(self, dt: datetime.datetime) -> datetime.timedelta:
        if dt.month < 3 or 11 < dt.month:
            return datetime.timedelta(0)
        elif 3 < dt.month and dt.month < 11:
            return datetime.timedelta(hours=1)
        elif dt.month == 3: # DST starts second Sunday of March
            week2Day = dt.day - 7
            if week2Day > 0 and (dt.weekday() == 6 or week2Day < dt.weekday() + 1):
                return datetime.timedelta(0)
            else:
                return datetime.timedelta(hours=1)
        elif dt.month == 11: # DST ends first Sunday of November
            if dt.weekday() == 6 or dt.day > dt.weekday() + 1:
                return datetime.timedelta(hours=1)
            else:
                return datetime.timedelta(0)
    def utcoffset(self, dt: datetime.datetime) -> datetime.timedelta:
        return datetime.timedelta(hours=-5) + self.dst(dt)
    def tzname(self, dt: datetime.datetime) -> str:
        if self.dst(dt).total_seconds() == 0:
            return "EST"
        else:
            return "EDT"

class AbstractPick(ABC):
    def __init__(self, player: str):
        self.player = player
        self.time: int = None

    @abstractmethod
    def toDict(self) -> dict:
        pass

    def timeStr(self) -> str:
        date = datetime.datetime.fromtimestamp(self.time, Eastern())
        return date.strftime("%m/%d/%y %I:%M:%S %p %Z")


class reservePick(AbstractPick):
    """A Nation for the nation reserve channel interaction."""

    def __init__(self, player: str, tag: str, time: int = None):
        self.player: str = player
        self.tag = tag
        self.capitalID: int = 0
        self.time: int = time

    def toDict(self) -> dict:
        return {"player": self.player, "tag": self.tag, "time": self.time}

class asiPick(AbstractPick):
    """A user's reservation for an ASI game."""

    def __init__(self, player: str, priority: bool = False, time: int = None):
        self.player: str = player
        self.picks: List[str] = None
        self.priority = priority
        self.time: int = time

    def toDict(self) -> dict:
        return {"player": self.player, "priority": self.priority, "picks": self.picks, "time": self.time}

class AbstractReserve(ABC):
    @abstractmethod
    def __init__(self, name: str):
        self.players: list = []
        self.name = name  # Should be channelID
        self.textmsg: Optional[int] = None

    @abstractmethod
    def add(self, pick: AbstractPick) -> int:
        """Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other (ONLY for priority)
        4 = Failed; Nation taken by self (ONLY for priority)
        """
        pass

    @abstractmethod
    def removePlayer(self, name: str) -> bool:
        pass

    @abstractmethod
    def delete(self):
        pass

    @abstractmethod
    def toDict(self) -> dict:
        pass


class Reserve(AbstractReserve):
    """Represents a reservation list for a specific game. The name should be the id of the channel it represents."""

    def __init__(self, name: str):
        self.players: List[reservePick] = []  # list of reservePick objects
        self.name = name
        self.bans: List[str] = []
        self.textmsg: Optional[int] = None
        self.imgmsg: Optional[int] = None

    def add(self, nation: reservePick) -> int:
        """Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other
        4 = Failed; Nation taken by self
        """
        addInt = 1
        for pick in self.players:
            if pick.tag.upper() == nation.tag.upper():
                if pick.player == nation.player:
                    return 4
                else:
                    return 3
            elif pick.player == nation.player:
                addInt = 2
                self.players.remove(pick)
        if nation.time is None:
            nation.time = int(time.time())
        self.players.append(nation)
        return addInt

    def remove(self, tag: str) -> bool:
        for i in self.players:
            if i.tag == tag:
                self.players.remove(i)
                return True
        return False

    def removePlayer(self, name: str) -> bool:
        for i in self.players:
            if i.player == name:
                self.players.remove(i)
                return True
        return False

    def delete(self):
        pass

    def toDict(self) -> dict:
        pickDictList = [pick.toDict() for pick in self.players]
        return {"kind": "reserve", "textmsg": self.textmsg, "imgmsg": self.imgmsg, "reserves": pickDictList, "bans": self.bans}


class ASIReserve(AbstractReserve):
    def __init__(self, name: str):
        self.players: List[asiPick] = []
        self.name = name  # Should be channelID
        self.textmsg: Optional[int] = None

    def add(self, pick: asiPick) -> int:
        """Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other (ONLY for priority)
        4 = Failed; Nation taken by self (ONLY for priority)
        """
        addInt = 1
        for player in self.players:
            if pick.priority and player.priority and pick.picks[0] == player.picks[0]:
                if pick.player == player.player:
                    return 4
                else:
                    return 3
            elif pick.player == player.player:
                addInt = 2
                self.players.remove(pick)
        if pick.time is None:
            pick.time = int(time.time())
        self.players.append(pick)
        return addInt

    def removePlayer(self, name: str) -> bool:
        for pick in self.players:
            if pick.player == name:
                self.players.remove(pick)
                return True
        return False

    def delete(self):
        pass

    def toDict(self) -> dict:
        pickDictList = [pick.toDict() for pick in self.players]
        return {"kind": "asi", "textmsg": self.textmsg, "reserves": pickDictList}


def load(conn: Optional[psycopg2.extensions.connection] = None) -> List[AbstractReserve]:
    """Loads the full list of reserves.

    If conn is specified, it uses that database connection. Otherwise, it loads from the json.

    Should only be used with a database connection if ALL reserves are needed. That is pretty much just on startup.
    For json load, this is the only way of getting stuff from on file. Other methods such as getReserve() call this.
    """
    # Note that for json save this is referenced by getReserve, whereas for SQL save it references getReserve. If this got messed up, things would be bad.
    if conn is None:
        try:
            with open("ressave.json", "r") as x:
                jsonLoad: dict = json.load(x)
                x.close()
            if len(jsonLoad) == 0:
                return []
        except FileNotFoundError:  # There are no reserves.
            return []
        except json.decoder.JSONDecodeError:
            print(
                "Something is wrong with the save json formatting. You can try to delete the file to reset.")
            return []
        resList = []
        for res in jsonLoad:
            if jsonLoad[res]["kind"] == "reserve":
                r = Reserve(res)
                try:
                    r.bans = jsonLoad[res]["bans"]
                except:
                    r.bans = []
                r.textmsg = jsonLoad[res]["textmsg"]
                r.imgmsg = jsonLoad[res]["imgmsg"]
                for pick in jsonLoad[res]["reserves"]:
                    try:
                        r.add(reservePick(pick["player"], pick["tag"], pick["time"]))
                    except:
                        r.add(reservePick(pick["player"], pick["tag"]))
                resList.append(r)
            elif jsonLoad[res]["kind"] == "asi":
                r = ASIReserve(res)
                r.textmsg = jsonLoad[res]["textmsg"]
                for pick in jsonLoad[res]["reserves"]:
                    asirespick = asiPick(pick["player"], pick["priority"])
                    asirespick.picks = pick["picks"]
                    try:
                        asirespick.time = pick["time"]
                    except:
                        pass
                    r.add(asirespick)
                resList.append(r)
        return resList
    else:  # With the new SQL format, this should only be called if there is a connection when everything is being loaded initially.
        resList = []
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves")
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        else:
            for res in cur.fetchall():
                resList.append(getReserve(res[0], conn=conn))
        cur.close()
        return resList


def save(reserves: List[AbstractReserve]):
    """Overwrites the json save file with the given reserve list."""
    jsonSave = {}
    for res in reserves:
        jsonSave[res.name] = res.toDict()
    with open("ressave.json", "w") as x:
        json.dump(jsonSave, x)
        x.close()


def getReserve(name: str, conn: Optional[psycopg2.extensions.connection] = None) -> AbstractReserve:
    """Gets an AbstractReserve saved based on the name given.

    If conn is given, the psycopg2 connection will be used to access the database. Otherwise, the json file method will be used.

    If no reserve can be found by the given name, None will be returned.
    """
    # File
    if conn is None:
        resList = load()
        for res in resList:
            if res.name == str(name):
                return res
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        else:
            resTup = cur.fetchone()
            if resTup is not None:  # There is a reserve on file
                if resTup[1] == "reserve":
                    res = Reserve(name)
                    try:
                        # Get the textmsg ID
                        res.textmsg = int(resTup[3][0])
                    except:  # Probably means the textmsg is not yet set
                        res.textmsg = None
                    try:
                        # Get the imgmsg ID
                        res.imgmsg = int(resTup[3][1])
                    except:  # Probably means the imgmsg is not yet set
                        res.imgmsg = None
                    # Get banned nations
                    res.bans = resTup[2]
                    # Get picks
                    try:
                        cur.execute(
                            "SELECT * FROM ReservePicks WHERE reserve=%s", [name])
                    except psycopg2.Error:
                        cur.execute(
                            "CREATE TABLE ReservePicks (reserve varchar, player varchar, tag varchar, time bigint)")
                    else:
                        for pick in cur.fetchall():
                            res.add(reservePick(pick[1], pick[2], pick[3]))
                        cur.close()
                        return res
                elif resTup[1] == "asi":
                    res = ASIReserve(name)
                    try:
                        # Get the textmsg ID
                        res.textmsg = int(resTup[3][0])
                    except:  # Probably means the textmsg is not yet set
                        res.textmsg = None
                    try:
                        cur.execute(
                            "SELECT * FROM ASIPicks WHERE reserve=%s", [name])
                    except psycopg2.Error:
                        cur.execute(
                            "CREATE TABLE ASIPicks (reserve varchar, player varchar, tag1 varchar, tag2 varchar, tag3 varchar, time bigint)")
                    else:
                        for pick in cur.fetchall():
                            pickObj = asiPick(
                                pick[1], (pick[3] == "NULL" and pick[4] == "NULL"), pick[5])
                            if pickObj.priority:
                                pickObj.picks = [pick[2]]
                            else:
                                pickObj.picks = [pick[2], pick[3], pick[4]]
                            res.add(pickObj)
                        cur.close()
                        return res
        cur.close()
    return None


def updateMessageIDs(reserve: Union[str, AbstractReserve], textmsg: int = None, imgmsg: int = None, conn: Optional[psycopg2.extensions.connection] = None):
    """Updates the saved message IDs for the given reserve.

    For normal Reserve, this is both textmsg and imgmsg. Either or both may be given as optional arguments, and only those given will be changed.

    In ASIReserve, the same applies but ASIReserve does not have imgmsg, so entering this for an ASIReserve will be ignored."""
    # If they haven't given either to change, do nothing
    if textmsg is None and imgmsg is None:
        return
    # Get the reserve name
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                if textmsg is not None:
                    x.textmsg = textmsg
                if imgmsg is not None and isinstance(x, Reserve):
                    x.imgmsg = imgmsg
                break
        save(resList)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        else:
            res = cur.fetchone()
            if res is not None:
                # Write the new specData list
                newspecData = []
                if textmsg is None:  # This call is not editing textmsg; get previous value
                    newspecData.append(res[3][0])
                else:  # This call is editing textmsg
                    newspecData.append(str(textmsg))
                if res[1] == "reserve":  # Only reserve has an imgmsg
                    if imgmsg is None:
                        newspecData.append(res[3][1])
                    else:
                        newspecData.append(str(imgmsg))
                # Update on the database
                cur.execute("DELETE FROM Reserves WHERE name=%s", [res[0]])
                cur.execute("INSERT INTO Reserves (name, kind, ban, specData) VALUES (%s, %s, %s, %s)", [
                            res[0], res[1], res[2], newspecData])
            else:
                # Oh no! you're editing a nonexistant entry. Let's do nothing.
                pass


def deleteReserve(reserve: Union[str, AbstractReserve], conn: Optional[psycopg2.extensions.connection] = None):
    """Deletes a Reserve from on save"""
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                resList.remove(x)
                break
        save(resList)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("DELETE FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        try:
            cur.execute("DELETE FROM ReservePicks WHERE reserve=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE ReservePicks (reserve varchar, player varchar, tag varchar, time bigint)")
        try:
            cur.execute("DELETE FROM ASIPicks WHERE reserve=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE ASIPicks (reserve varchar, player varchar, tag1 varchar, tag2 varchar, tag3 varchar, time bigint)")
        cur.close()


def deletePick(reserve: Union[str, AbstractReserve], player: str, conn: Optional[psycopg2.extensions.connection] = None) -> bool:
    """Deletes a player's pick from a specified reserve on save.

    Returns a bool of whether or not a change occured. (False means that there was no pick to begin with)"""
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    # This value is returned at the end of whether changes were made.
    didStuff = False
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                didStuff = x.removePlayer(player)
                break
        save(resList)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        # Delete from ReservePicks
        try:
            # See if there are any that meet the requirements
            cur.execute(
                "SELECT FROM ReservePicks WHERE reserve=%s AND player=%s", [name, player])
            if len(cur.fetchall()) != 0:
                # If so, delete them and didStuff is true. Otherwise didStuff continues to be False
                cur.execute(
                    "DELETE FROM ReservePicks WHERE reserve=%s AND player=%s", [name, player])
                didStuff = True
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE ReservePicks (reserve varchar, player varchar, tag varchar, time bigint)")
        # Delete from ASIPicks
        try:
            # See if there are any that meet the requirements
            cur.execute(
                "SELECT FROM ASIPicks WHERE reserve=%s AND player=%s", [name, player])
            if len(cur.fetchall()) != 0:
                # If so, delete them and didStuff is true. Otherwise didStuff continues its previous value
                cur.execute(
                    "DELETE FROM ASIPicks WHERE reserve=%s AND player=%s", [name, player])
                didStuff = True
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE ASIPicks (reserve varchar, player varchar, tag1 varchar, tag2 varchar, tag3 varchar, time bigint)")
        cur.close()
    return didStuff


def addReserve(reserve: AbstractReserve, conn: Optional[psycopg2.extensions.connection] = None):
    """Adds a new reserve on save."""
    # File
    if conn is None:
        resList = load()
        resList.append(reserve)
        save(resList)
    # SQL
    else:
        # Setup the specData based on the given reserve
        specData: List[str] = []
        if isinstance(reserve, Reserve):
            kind = "reserve"
            specData.append(str(reserve.textmsg))
            specData.append(str(reserve.imgmsg))
        elif isinstance(reserve, ASIReserve):
            kind = "asi"
            specData.append(str(reserve.textmsg))
        # Update on the database
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("DELETE FROM Reserves WHERE name=%s", [reserve.name])
            cur.execute("INSERT INTO Reserves (name, kind, ban, specData) VALUES (%s, %s, %s, %s)", [
                        reserve.name, kind, reserve.bans, specData])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        cur.close()


def addPick(reserve: Union[str, AbstractReserve], pick: AbstractPick, conn: Optional[psycopg2.extensions.connection] = None) -> int:
    """Adds a pick to a specified reserve and returns a code based on the result.

    Codes:
    0 = Failed; Reserve not found
    1 = Success; New Reservation
    2 = Success; Replaced old reservation
    3 = Failed; Nation taken by other
    4 = Failed; Nation taken by self
    """
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    addInt = 0
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                addInt = x.add(pick)
                break
        save(resList)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
            # addInt is 0
        else:
            res = cur.fetchone()
            if res is None:
                pass
                # addInt is 0
            else:
                if res[1] == "reserve" and isinstance(pick, reservePick):
                    try:
                        cur.execute(
                            "SELECT * FROM ReservePicks WHERE reserve=%s AND tag=%s", [res[0], pick.tag])
                        tagres = cur.fetchone()
                        cur.execute(
                            "SELECT * FROM ReservePicks WHERE reserve=%s AND player=%s", [res[0], pick.player])
                        playerres = cur.fetchone()
                        if tagres is None and playerres is None:  # Nobody else has reserved this; player has not reserved
                            if pick.time is None:
                                resTime = int(time.time())
                            else:
                                resTime = pick.time
                            cur.execute("INSERT INTO ReservePicks (reserve, player, tag, time) VALUES (%s, %s, %s, %s)", [
                                        res[0], pick.player, pick.tag, resTime])
                            addInt = 1
                        # Nobody else has reserved this, but player has another reservation
                        elif tagres is None and playerres is not None:
                            cur.execute("DELETE FROM ReservePicks WHERE reserve=%s AND player=%s", [
                                        res[0], pick.player])
                            if pick.time is None:
                                resTime = int(time.time())
                            else:
                                resTime = pick.time
                            cur.execute("INSERT INTO ReservePicks (reserve, player, tag, time) VALUES (%s, %s, %s, %s)", [
                                        res[0], pick.player, pick.tag, resTime])
                            addInt = 2
                        elif tagres == playerres:  # This player has already reserved this
                            addInt = 4
                        else:  # Another player has reserved this. tagres is not None and tagres != playerres.
                            addInt = 3
                    except psycopg2.Error:
                        cur.execute(
                            "CREATE TABLE ReservePicks (reserve varchar, player varchar, tag varchar, time bigint)")
                elif res[1] == "asi" and isinstance(pick, asiPick):
                    try:
                        cur.execute(
                            "SELECT * FROM ASIPicks WHERE reserve=%s AND tag1=%s AND tag2='NULL'", [res[0], pick.picks[0]])
                        tagres = cur.fetchone()  # Any priority reserve of the first res
                        cur.execute(
                            "SELECT * FROM ASIPicks WHERE reserve=%s AND player=%s", [res[0], pick.player])
                        playerres = cur.fetchone()
                        if tagres == playerres and tagres is not None:  # The player has priority reserved this already
                            addInt = 4
                        elif tagres is None and playerres is None:  # Nobody else has priority reserved this; player has not reserved
                            if pick.time is None:
                                resTime = int(time.time())
                            else:
                                resTime = pick.time
                            if pick.priority:
                                cur.execute("INSERT INTO ASIPicks (reserve, player, tag1, tag2, tag3, time) VALUES (%s, %s, %s, 'NULL', 'NULL', %s)", [
                                            res[0], pick.player, pick.picks[0], resTime])
                            else:
                                cur.execute("INSERT INTO ASIPicks (reserve, player, tag1, tag2, tag3, time) VALUES (%s, %s, %s, %s, %s, %s)", [
                                            res[0], pick.player, pick.picks[0], pick.picks[1], pick.picks[2], resTime])
                            addInt = 1
                        # Nobody else has priority reserved this, but player has another reservation
                        elif tagres is None and playerres is not None:
                            cur.execute("DELETE FROM ASIPicks WHERE reserve=%s AND player=%s", [
                                        res[0], pick.player])
                            if pick.time is None:
                                resTime = int(time.time())
                            else:
                                resTime = pick.time
                            if pick.priority:
                                cur.execute("INSERT INTO ASIPicks (reserve, player, tag1, tag2, tag3, time) VALUES (%s, %s, %s, 'NULL', 'NULL', %s)", [
                                            res[0], pick.player, pick.picks[0], resTime])
                            else:
                                cur.execute("INSERT INTO ASIPicks (reserve, player, tag1, tag2, tag3, time) VALUES (%s, %s, %s, %s, %s, %s)", [
                                            res[0], pick.player, pick.picks[0], pick.picks[1], pick.picks[2], resTime])
                            addInt = 2
                        # Another player has priority reserved this. (tagres is not None and tagres != playerres)
                        else:
                            addInt = 3
                    except psycopg2.Error:
                        cur.execute(
                            "CREATE TABLE ASIPicks (reserve varchar, player varchar, tag1 varchar, tag2 varchar, tag3 varchar, time bigint)")
    return addInt


def addBan(reserve: Union[str, AbstractReserve], bans: List[str], conn: Optional[psycopg2.extensions.connection] = None):
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                for tag in bans:
                    if hasattr(x, "bans") and tag not in x.bans:
                        x.bans.append(tag)
                break
        save(resList)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        else:
            res = cur.fetchone()
            banlist = res[2]
            for tag in bans:
                if tag not in banlist:
                    banlist.append(tag)
            cur.execute("DELETE FROM Reserves WHERE name=%s", [name])
            cur.execute("INSERT INTO Reserves (name, kind, ban, specData) VALUES (%s, %s, %s, %s)", [
                        res[0], res[1], banlist, res[3]])
        cur.close()


def deleteBan(reserve: Union[str, AbstractReserve], bans: List[str], conn: Optional[psycopg2.extensions.connection] = None):
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                for tag in bans:
                    if hasattr(x, "bans") and tag in x.bans:
                        x.bans.remove(tag)
                break
        save(resList)
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        else:
            res = cur.fetchone()
            banlist = res[2]
            for tag in bans:
                if tag in banlist:
                    banlist.remove(tag)
            cur.execute("DELETE FROM Reserves WHERE name=%s", [name])
            cur.execute("INSERT INTO Reserves (name, kind, ban, specData) VALUES (%s, %s, %s, %s)", [
                        res[0], res[1], banlist, res[3]])
        cur.close()


def isBanned(reserve: Union[str, AbstractReserve], tag: str, conn: Optional[psycopg2.extensions.connection] = None) -> bool:
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    # File
    if conn is None:
        resList = load()
        for x in resList:
            if x.name == name:
                return hasattr(x, "bans") and tag in x.bans
    # SQL
    else:
        cur: psycopg2.extensions.cursor = conn.cursor()
        try:
            cur.execute("SELECT * FROM Reserves WHERE name=%s", [name])
        except psycopg2.Error:
            cur.execute(
                "CREATE TABLE Reserves (name varchar, kind varchar, ban varchar[], specData varchar[])")
        else:
            res = cur.fetchone()
            cur.close()
            banlist = res[2]
            return tag in banlist


def createMap(reserve: Reserve) -> Image:
    """Creates a map based on a Reserve object with x's on all the capitals of reserved reservePicks.
    Returns an Image object.
    """
    countries: List[reservePick] = reserve.players
    mapFinal = Image.open("src/map_1444.png")
    srcFile = open("src/save_1444.eu4", "r", encoding="cp1252")
    lines = srcFile.readlines()
    brackets = []
    linenum = 0
    for line in lines:
        linenum += 1

        if "{" in line:
            if line.count("{") == line.count("}"):
                continue
            elif line.count("}") == 0 and line.count("{") == 1:
                brackets.append(line.rstrip("\n "))
            elif line.count("}") == 0 and line.count("{") > 1:
                for x in range(line.count("{")):
                    brackets.append("{")  # TODO: fix this so it has more
            else:
                print("Unexpected brackets at line #" +
                      str(linenum) + ": " + line)
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:  # This shouldn't happen.
                print("No brackets to delete.")
                print("Line", linenum, ":", line)
        # Get rid of long, useless sections
        elif len(brackets) < 0 and ("trade={" == brackets[1] or "provinces={" == brackets[0] or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
            continue
        elif len(brackets) > 1 and brackets[0] == "countries={":
            for x in countries:
                if x.tag in brackets[1]:
                    # Here we have all the stats for country x on the players list
                    if len(brackets) == 2 and "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                        x.capitalID = int(line.strip("\tcapitl=\n"))
    srcFile.close()
    imgX = Image.open("src/xIcon.png")
    for x in countries:
        loc = EU4Lib.province(x.capitalID)
        mapFinal.paste(
            imgX, (int(loc[0]-imgX.size[0]/2), int(loc[1]-imgX.size[1]/2)), imgX)
        # I hope this doesn't break if a capital is too close to the edge
    return mapFinal
