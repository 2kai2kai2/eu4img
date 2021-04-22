import datetime
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
import dotenv

import psycopg2
from PIL import Image
import pymongo
from pymongo.collection import Collection
from pymongo.database import Database

dotenv.load_dotenv()
client = pymongo.MongoClient(
    f"mongodb+srv://{os.environ['MONGODB_USERNAME']}:{os.environ['MONGODB_PASSWORD']}@{os.environ['MONGODB_CLUSTERURL']}/reservations?retryWrites=true&w=majority")
database: Database = client.reservations

"""
Data Structure - Python side
AbstractReserve ("Reserve")
    players: List[AbstractPick ("Pick")]
        player: str; user mention
    name: str; Channel ID as a str
    textmsg: int; the msg ID in the channel
"""

"""
Data Structure - JSON Formatting
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

"""
Data Structure - SQL Database
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

"""
Data Structure
Database: reservations
Collection: index
{
    reserveType: "<reserve|asi>",
    channelID: int,
    guildID: int,
    messages: {
        textID: int,
        imgID: int # Reserve only
    }
    ban: [
        "TAG",
        "TAG"
    ]
}

Collection: <channelID>
{ # reserve
    userID: int,
    tag: "TAG",
    time: timestamp
}
Or,
{ # asi
    userID: int,
    tag1: "TAG",
    tag2: <"TAG"|Null>,
    tag3: <"TAG"|Null>,
    time: timestamp
}
"""


class Eastern(datetime.tzinfo):
    def __init__(self):
        pass

    def dst(self, dt: datetime.datetime) -> datetime.timedelta:
        if dt.month < 3 or 11 < dt.month:
            return datetime.timedelta(0)
        elif 3 < dt.month and dt.month < 11:
            return datetime.timedelta(hours=1)
        elif dt.month == 3:  # DST starts second Sunday of March
            week2Day = dt.day - 7
            if week2Day > 0 and (dt.weekday() == 6 or week2Day < dt.weekday() + 1):
                return datetime.timedelta(0)
            else:
                return datetime.timedelta(hours=1)
        elif dt.month == 11:  # DST ends first Sunday of November
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
    """
    An abstract class containing all the data for a player's pick in a reservations-type channel.
    Immutable.
    """

    def __init__(self, userID: int):
        self.userID = userID
        self.time: int = None

    def timeStr(self) -> str:
        date = datetime.datetime.fromtimestamp(self.time, Eastern())
        return date.strftime("%m/%d/%y %I:%M:%S %p %Z")


class reservePick(AbstractPick):
    """
    A Nation for the nation reserve channel interaction.
    """

    def __init__(self, userID: int, tag: str, time: int = time.time()):
        self.userID = userID
        self.tag = tag.upper()
        self.capitalID: int = 0
        self.time: int = time

    def toDict(self) -> Dict[str, Any]:
        return {
            "userID": self.userID,
            "tag": self.tag,
            "time": self.time
        }


class asiPick(AbstractPick):
    """
    A user's reservation for an ASI game.
    """

    def __init__(self, userID: int, priority: bool = False, time: int = time.time()):
        self.userID = userID
        self.picks: List[str] = None
        self.priority = priority
        self.time: int = time

    def toDict(self) -> Dict[str, Any]:
        return {
            "userID": self.userID,
            "tag1": self.picks[0].upper(),
            "tag2": self.picks[1].upper(),
            "tag3": self.picks[2].upper(),
            "time": self.time
        }


class AbstractReserve(ABC):
    @abstractmethod
    def __init__(self, channelID: int):
        self.channelID = channelID

    @abstractmethod
    def add(self, pick: AbstractPick) -> int:
        """
        Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other
        4 = Failed; Nation taken by self
        """
        pass

    @abstractmethod
    def removePlayer(self, name: str) -> bool:
        pass

    @abstractmethod
    def delete(self):
        pass


class Reserve(AbstractReserve):
    """
    Represents a reservation list for a specific game. The name should be the id of the channel it represents.
    """

    def __init__(self, channelID: int):
        self.channelID = channelID
        self._docfilter = {"channelID": channelID}
        # Check to see if we should create a new database entry
        count = database.index.count_documents({"channelID": self.channelID})
        if count == 0:
            # The entry is not present in the database. Create new.
            database.index.insert_one({
                "reserveType": "reserve",
                "channelID": channelID,
                "guildID": None,  # TODO: Make this work
                "messages": {
                    "textID": None,
                    "imgID": None
                },
                "ban": []
            })
            database.create_collection(str(channelID))

    def _document(self) -> Dict["str", Any]:
        out = database.index.find_one(self._docfilter)
        if out is None:
            raise LookupError(
                f"Could not find document for reserve channel {self.channelID} in database reservations>index.")
        else:
            return out

    def _collection(self) -> Collection:
        database.validate_collection(str(self.channelID))
        return database[str(self.channelID)]

    def add(self, nation: reservePick) -> int:
        """
        Does not check if the tag is banned.
        Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other
        4 = Failed; Nation taken by self
        """
        reserves = self._collection()
        tagTaken = reserves.find_one({"tag": nation.tag.upper()})
        # Check if it's taken
        if tagTaken is not None:
            # Check whether it's taken by this user or by another
            if tagTaken["userID"] == nation.userID:
                return 4
            else:
                return 3
        # Replace the user's old pick and return it if it existed
        playerpick = reserves.find_one_and_replace(
            {"userID": nation.userID}, nation.toDict(), upsert=True)
        if playerpick is not None:
            return 2
        else:
            return 1

    def remove(self, tag: str) -> bool:
        reserves = self._collection()
        result = reserves.delete_many({"tag": tag.upper()})
        return result.deleted_count > 0

    def removePlayer(self, userID: int) -> bool:
        reserves = self._collection()
        result = reserves.delete_many({"userID": userID})
        return result.deleted_count > 0

    def getPlayers(self) -> List[reservePick]:
        reserves = self._collection()
        players: List[reservePick] = []
        for pick in reserves.find():
            players.append(reservePick(pick["userID"], pick["tag"], pick["time"]))
        return players

    def countPlayers(self) -> int:
        return self._collection().count_documents({})

    @property
    def textID(self) -> int:
        return self._document()["messages"]["textID"]

    @textID.setter
    def textID(self, value: int):
        database.index.update_one(self._docfilter, {"$set": {"messages.textID": value}})

    @property
    def imgID(self) -> int:
        return self._document()["messages"]["imgID"]

    @imgID.setter
    def imgID(self, value: int):
        database.index.update_one(self._docfilter, {"$set": {"messages.imgID": value}})

    def isBan(self, tag: str) -> bool:
        return database.index.count_documents({"channelID": self.channelID, "ban": tag.upper()}) != 0

    def allBans(self) -> List[str]:
        return self._document()["ban"]

    def addBan(self, tag: str):
        database.index.update_one(self._docfilter, {
            "$addToSet": {"ban": tag.upper()}
        })

    def delBan(self, tag: str):
        database.index.update_one(self._docfilter, {
            "$pull": {"ban": tag.upper()}
        })

    def delete(self):
        """
        Delete this Reservations controlled channel from the database.
        """
        database.index.delete_many(self._docfilter)
        database.drop_collection(str(self.channelID))
        del(self.channelID)
        # Now there will be errors whenever anything is called because channelID does not exist


class ASIReserve(AbstractReserve):
    def __init__(self, name: str):
        self.players: List[asiPick] = []
        self.name = name  # Should be channelID
        self.textmsg: Optional[int] = None
        self.bans: List[str] = []

    def add(self, pick: asiPick) -> int:
        """
        Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other (ONLY for priority)
        4 = Failed; Nation taken by self (ONLY for priority)
        """
        addInt = 1
        for player in self.players:
            if pick.priority and player.priority and pick.picks[0] == player.picks[0]:
                if pick.userID == player.userID:
                    return 4
                else:
                    return 3
            elif pick.userID == player.userID:
                addInt = 2
                self.players.remove(pick)
        if pick.time is None:
            pick.time = int(time.time())
        self.players.append(pick)
        return addInt

    def removePlayer(self, name: str) -> bool:
        for pick in self.players:
            if pick.userID == name:
                self.players.remove(pick)
                return True
        return False

    def delete(self):
        pass


def load() -> List[Union[Reserve, ASIReserve]]:
    """
    Loads the full list of reserves.
    """
    data = database.index.find()
    out = []
    for res in data:
        if res["reserveType"] == "reserve":
            out.append(Reserve(res["channelID"]))
        elif res["reserveType"] == "asi":
            out.append(ASIReserve(res["channelID"]))
    return out


def createMap(reserve: Reserve) -> Image.Image:
    """
    Creates a map based on a Reserve object with x's on the capitals of all reserved reservePicks.
    Returns an Image object.
    """
    countries: List[reservePick] = reserve.getPlayers()
    capitalLocs: Dict[str, Tuple[float, float]] = {}

    srcFile = open("resources/tagCapitals.txt", "r", encoding="cp1252")
    lines = srcFile.readlines()
    srcFile.close()
    for line in lines:
        for natnum in range(len(countries)):
            if line.startswith(countries[natnum].tag):
                capitalLocs[countries[natnum].tag] = (
                    float(line[4:line.index(",", 4)]), float(line[line.index(",", 4) + 1:]))
                countries.pop(natnum)
                break
        if len(countries) == 0:
            break
    del(lines)

    mapFinal: Image.Image = Image.open("resources/map_1444.png")
    imgX: Image.Image = Image.open("resources/xIcon.png")
    for x in capitalLocs:
        mapFinal.paste(
            imgX, (int(capitalLocs[x][0]-imgX.size[0]/2), int(capitalLocs[x][1]-imgX.size[1]/2)), imgX)
        # I hope this doesn't break if a capital is too close to the edge
    return mapFinal
