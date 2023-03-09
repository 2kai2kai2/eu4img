import datetime
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Union

import dotenv
import pymongo
from PIL import Image
from pymongo.collection import Collection
from pymongo.database import Database
import EU4Lib

dotenv.load_dotenv()
client = pymongo.MongoClient(
    f"mongodb+srv://{os.environ['MONGODB_USERNAME']}:{os.environ['MONGODB_PASSWORD']}@{os.environ['MONGODB_CLUSTERURL']}/reservations?retryWrites=true&w=majority")
database: Database = client.reservations

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


class AbstractPick(ABC):
    """
    An abstract class containing all the data for a player's pick in a reservations-type channel.
    Immutable.
    """

    def __init__(self, userID: int):
        self.userID = userID
        self.time: int = None

    def timeStr(self) -> str:
        return f"<t:{round(self.time)}>"


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

    def __init__(self, userID: int, priority: bool = False, time: int = time.time(), picks: List[str] = None):
        self.userID = userID
        self.picks: List[str] = picks
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

    def delete(self):
        """
        Delete this ASI Reservations controlled channel from the database.
        """
        database.index.delete_many(self._docfilter)
        database.drop_collection(str(self.channelID))
        del(self.channelID)
        # Now there will be errors whenever anything is called because channelID does not exist


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
            players.append(reservePick(
                pick["userID"], pick["tag"], pick["time"]))
        return players

    def countPlayers(self) -> int:
        return self._collection().count_documents({})

    @property
    def textID(self) -> int:
        return self._document()["messages"]["textID"]

    @textID.setter
    def textID(self, value: int):
        database.index.update_one(
            self._docfilter, {"$set": {"messages.textID": value}})

    @property
    def imgID(self) -> int:
        return self._document()["messages"]["imgID"]

    @imgID.setter
    def imgID(self, value: int):
        database.index.update_one(
            self._docfilter, {"$set": {"messages.imgID": value}})

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
    def __init__(self, channelID: int):
        self.channelID = channelID
        self._docfilter = {"channelID": channelID}
        # Check to see if we should create a new database entry
        count = database.index.count_documents({"channelID": self.channelID})
        if count == 0:
            # The entry is not present in the database. Create new.
            database.index.insert_one({
                "reserveType": "asi",
                "channelID": channelID,
                "guildID": None,  # TODO: Make this work
                "messages": {
                    "textID": None,
                    "imgID": None
                },
                "ban": []
            })
            database.create_collection(str(channelID))

    @property
    def textID(self) -> int:
        return self._document()["messages"]["textID"]

    @textID.setter
    def textID(self, value: int):
        database.index.update_one(
            self._docfilter, {"$set": {"messages.textID": value}})

    def add(self, pick: asiPick) -> int:
        """
        Codes:
        1 = Success; New Reservation
        2 = Success; Replaced old reservation
        3 = Failed; Nation taken by other (ONLY for priority)
        4 = Failed; Nation taken by self (ONLY for priority)
        """
        reserves = self._collection()
        if pick.priority:
            # Only search for other priority picks with this tag
            tagTaken = reserves.find_one(
                {"tag1": pick.tag.upper(), "tag2": None, "tag3": None})
            if tagTaken is not None:
                # Check whether it's taken by this user or by another
                if tagTaken["userID"] == pick.userID:
                    return 4
                else:
                    return 3
        # Replace the user's old pick and return it if it existed
        playerpick = reserves.find_one_and_replace(
            {"userID": pick.userID}, pick.toDict(), upsert=True)
        if playerpick is not None:
            return 2
        else:
            return 1

    def removePlayer(self, userID: int) -> bool:
        reserves = self._collection()
        result = reserves.delete_many({"userID": userID})
        return result.deleted_count > 0

    def getPlayers(self) -> List[asiPick]:
        reserves = self._collection()
        players: List[asiPick] = []
        for pick in reserves.find():
            players.append(asiPick(pick["userID"], pick["tag2"] is None, pick["time"], [
                           pick["tag1"], pick["tag2"], pick["tag3"]]))
        return players

    def countPlayers(self) -> int:
        return self._collection().count_documents({})

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

    for country in countries:
        capitalLocs[country.tag] = EU4Lib.province(
            EU4Lib.tagCapital(country.tag))

    mapFinal: Image.Image = Image.open("resources/vanilla/map_1444.png")
    imgX: Image.Image = Image.open("resources/xIcon.png")
    for x in capitalLocs:
        mapFinal.paste(
            imgX, (int(capitalLocs[x][0]-imgX.size[0]/2), int(capitalLocs[x][1]-imgX.size[1]/2)), imgX)
        # I hope this doesn't break if a capital is too close to the edge
    return mapFinal
