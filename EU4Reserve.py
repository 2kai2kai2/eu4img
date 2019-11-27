from PIL import Image, ImageDraw, ImageFont
import os
import EU4Lib
from dotenv import load_dotenv

class Nation:
    def __init__(self, player, tag):
        self.player = player
        self.tag = tag
        self.capitalID = 0

class Reserve:
    def __init__(self, name):
        self.nations = [] # list of Nation objects
        self.name = name #str
    def add(self, nation):
        self.nations.append(nation)
    def remove(self, tag):
        for i in self.nations:
            if i.tag == tag:
                self.nations.remove(i)
    def removePlayer(self, name):
        for i in self.nations:
            if i.player == name:
                self.nations.remove(i)
    def getSaveText(self):
        string = str(self.name) + "\n"
        for nation in self.nations:
            string += "\t" + nation.tag + " " + nation.player + "\n"
        return string


def getSavedReserves():
    reserves = []
    f = open("savedreservationgames.txt", "r")
    currentReserve = None
    while True:
        line = f.readline()
        if line is None or line == "": #--File has ended.
            if currentReserve is not None:
                reserves.append(currentReserve)
            return reserves
        elif line.startswith("\t"): #--This line is a new nation entry
            things = line.strip("\n\t ").split(" ", 1)
            currentReserve.add(Nation(things[1], things[0]))
            del(things)
        elif not line.startswith("\t") and not line.startswith(" ") and not line == "\n": #-- This line is a new reservation entry`
            if currentReserve is not None:
                reserves.append(currentReserve)
            currentReserve = Reserve(line.strip("\n\t "))
        else:
            pass # Uh this shouldn't happen unless the file is formatted incorrectly.
    f.close()
    return reserves

def getReserve(id):
    for r in getSavedReserves():
        if r.name == id:
            return r
    return None

def writeNewReservation(id):
    if not os.path.isfile("savedreservationgames.txt"):
        f = open("savedreservationgames.txt", "w")
        f.write(Reserve(id).getSaveText())
        f.close()
    else:
        reservations = getSavedReserves()
        for r in reservations:
            if r.name == str(id):
                reservations.remove(r)
        reservations.append(Reserve(id))
        
        text = ""
        for r in reservations:
            text += r.getSaveText()
        f = open("savedreservationgames.txt", "w")
        f.write(text)
        f.close()

def saveAdd(id, nation):
    reserves = getSavedReserves()
    for r in reserves:
        if r.name == str(id):
            r.add(nation)
    text = ""
    for r in reserves:
        text += r.getSaveText()
    f = open("savedreservationgames.txt", "w")
    f.write(text)
    f.close()

def saveRemove(id, user):
    reserves = getSavedReserves()
    for r in reserves:
        if r.name == str(id):
            r.removePlayer(user)
    text = ""
    for r in reserves:
        text += r.getSaveText()
    f = open("savedreservationgames.txt", "w")
    f.write(text)
    f.close()


#Start Data Selection
def createMap(reserve): #input a Reserve object
    countries = reserve.nations # List of Nation objects
    mapFinal = Image.open("src//map_1444.png")
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
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:
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
    imgX = Image.open("src//xIcon.png")
    for x in countries:
        loc = EU4Lib.province(x.capitalID)
        mapFinal.paste(imgX, (int(loc[0]-imgX.size[0]/2), int(loc[1]-imgX.size[1]/2)), imgX)
        # I hope this doesn't break if a capital is too close to the edge
    return mapFinal