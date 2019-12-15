import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Union

import psycopg2
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

import EU4Lib


""" Data Structure - Python side
AbstractReserve ("Reserve")
    players: List[AbstractPick ("Pick")]
        player: str; user mention
    name: str; Channel ID as a str
"""

""" Data Structure - JSON Formatting
In Python, this becomes a dict.


{
    "<ChannelID>": {
        "kind": "reserve",
        "reserves": [
        {
            "player": "<PlayerMention>",
            "tag": "<TAG>"
        },
        {...}
        ]
    },
    "<ChannelID>": {
        "kind": "asi",
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
                ]
            }
        ]
    }
}
"""

class AbstractPick(ABC):
    def __init__(self, player: str):
        pass
    @abstractmethod
    def toDict(self) -> dict:
        pass

class reservePick(AbstractPick):
    """A Nation for the nation reserve channel interaction."""
    def __init__(self, player: str, tag: str):
        self.player: str = player
        self.tag = tag
        self.capitalID: int = 0
    def toDict(self) -> dict:
        return {"player": self.player, "tag": self.tag}

class asiPick(AbstractPick):
    """A user's reservation for an ASI game."""
    def __init__(self, player: str, priority: bool = False):
        self.player: str = player
        self.picks: List[str] = None
        self.priority = priority
    def toDict(self) -> dict:
        return {"player": self.player, "priority": self.priority, "picks": self.picks}

class AbstractReserve(ABC):
    @abstractmethod
    def __init__(self, name: str):
        self.players: list = []
        self.name = name # Should be channelID
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
        self.players: List[reservePick] = [] # list of reservePick objects
        self.name = name
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
        pickDictList = []
        for pick in self.players:
            pickDictList.append(pick.toDict())
        return {"kind": "reserve", "reserves": pickDictList}

class ASIReserve(AbstractReserve):
    def __init__(self, name: str):
        self.players: List[asiPick] = []
        self.name = name # Should be channelID
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
        pickDictList = []
        for pick in self.players:
            pickDictList.append(pick.toDict())
        return {"kind": "asi", "reserves": pickDictList}

def load(conn = None) -> List[AbstractReserve]:
    try:
        if conn is None:
            with open("ressave.json", "r") as x:
                jsonLoad: dict = json.load(x)
        else:
            cur = conn.cursor()
            try:
                cur.execute("SELECT * FROM data")
            except:
                cur.execute("CREATE TABLE data (jsonstr varchar)")
                return []
            else:
                inobj = cur.fetchone()
                if inobj is None:
                    return []
                else:
                    jsonLoad: dict = json.loads(inobj[0])
            cur.close()
        if len(jsonLoad) == 0:
            return []
    except FileNotFoundError: # There are no reserves.
        return []
    except json.decoder.JSONDecodeError:
        print("Something is wrong with the save json formatting. You can try to delete the file to reset.")
        return []
    resList = []
    for res in jsonLoad:
        if jsonLoad[res]["kind"] == "reserve":
            r = Reserve(res)
            for pick in jsonLoad[res]["reserves"]:
                r.add(reservePick(pick["player"], pick["tag"]))
            resList.append(r)
        elif jsonLoad[res]["kind"] == "asi":
            r = ASIReserve(res)
            for pick in jsonLoad[res]["reserves"]:
                asirespick = asiPick(pick["player"], pick["priority"])
                asirespick.picks = pick["picks"]
                r.add(asirespick)
            resList.append(r)
    return resList

def save(reserves: List[AbstractReserve], conn = None):
    jsonSave = {}
    for res in reserves:
        jsonSave[res.name] = res.toDict()
    if conn is None:
        with open("ressave.json", "w") as x:
            json.dump(jsonSave, x)
    else:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM data")
        except:
            cur.execute("CREATE TABLE data (jsonstr varchar)")
        finally:
            cur.execute("INSERT INTO data (jsonstr) VALUES (%s)", [json.dumps(jsonSave)])
        cur.close()

def getReserve(name: str, conn = None) -> AbstractReserve:
    resList = load(conn = conn)
    for res in resList:
        if res.name == str(name):
            return res
    return None

def deleteReserve(reserve: Union[str, AbstractReserve], conn = None):
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    resList = load(conn = conn)
    for x in resList:
        if x.name == name:
            resList.remove(x)
            break
    save(resList, conn = conn)

def deletePick(reserve: Union[str, AbstractReserve], player: str, conn = None) -> bool:
    name = ""
    if isinstance(reserve, str):
        name = reserve
    elif isinstance(reserve, AbstractReserve):
        name = reserve.name
    resList = load(conn = conn)
    didStuff = False
    for x in resList:
        if x.name == name:
            didStuff = x.removePlayer(player)
            break
    save(resList, conn = conn)
    return didStuff

def addReserve(reserve: AbstractReserve, conn = None):
    resList = load(conn = conn)
    resList.append(reserve)
    save(resList, conn = conn)

def addPick(reserve: Union[str, AbstractReserve], pick: AbstractPick, conn = None):
    """Codes:
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
    resList = load(conn = conn)
    addInt = 0
    for x in resList:
        if x.name == name:
            # We have the reserve here. Now different things for each 
            addInt = x.add(pick)
            break
    save(resList, conn = conn)
    return addInt

def createMap(reserve: Reserve) -> Image:
    """Creates a map based on a Reserve object with x's on all the capitals of reserved reservePicks.
    Returns an Image object.
    """
    countries: List[reservePick] = reserve.players
    mapFinal = Image.open("src/map_1444.png")
    srcFile = open("src/save_1444.eu4", "r", encoding = "cp1252")
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
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError: # This shouldn't happen.
                print("No brackets to delete.")
                print("Line", linenum, ":", line)
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
    imgX = Image.open("src/xIcon.png")
    for x in countries:
        loc = EU4Lib.province(x.capitalID)
        mapFinal.paste(imgX, (int(loc[0]-imgX.size[0]/2), int(loc[1]-imgX.size[1]/2)), imgX)
        # I hope this doesn't break if a capital is too close to the edge
    return mapFinal
