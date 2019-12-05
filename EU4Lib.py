#This will need to be updated. Currently for 1.28
from PIL import Image, ImageDraw
from typing import Union, Tuple, List, Optional

def country(text: str) -> Optional[str]:
    """Returns the tag of a nation from the name of the nation.
    Some nations may have multiple valid names.
    If the nation is not recognized, returns None.
    """

    srcFile = open("src\\countries_l_english.yml")
    lines = srcFile.readlines()
    srcFile.close
    if len(text) == 3:
        for line in lines:
            if line[1:4] == text.upper():
                return text
    # text is not just a tag
    for line in lines:
       if ('"' + text.lower() + '"') in line.lower():
           return line[1:4]
    # text is unknown
    return None

def tagToName(tag: str) -> Optional[str]:
    """Returns the name of a nation based on its tag.
    If the tag is not recognized, returns None.
    """
    
    srcFile = open("src\\countries_l_english.yml")
    lines = srcFile.readlines()
    srcFile.close
    if len(tag) == 3:
        for line in lines:
            if line[1:4] == tag.upper():
                return line[8:].split("\"", 1)[0].strip("\" \t\n")
    return None

def province(id: Union[str, int]) -> Optional[Tuple[float, float]]:
    """Gets the location of a province on a screenshot map.
    Returns a tuple of floats, (x, y).
    """
    
    srcFile = open("src\\positions.txt", "r")
    lines = srcFile.readlines()
    beyond = 0
    for line in lines:
        if beyond == 2:
            vals = line.strip("\t\n ").split(" ")
            return (float(vals[0]), 2048-float(vals[1]))
        if beyond == 1:
            beyond = 2
            continue
        if line.strip("\n ") == (str(id)+"={"):
            beyond = 1
            continue
        
def flag(tag: str) -> Image:
    """Gets an Image of the flag of the specified nation.
    Returns Image of size (128, 128).
    """
    
    index = open("src\\flagfiles.txt", "r")
    line = index.read()
    a = line.partition(tag) #Separate into a 3-tuple around tag
    flagnum = a[0].count(".tga") #Get image number starting at 0
    #Each flag file is 16x16 so a total of 256 each
    #Each flag icon is 128x128 pixels
    flagfile = Image.open("src\\flagfiles_" + str(int(flagnum/256)) + ".tga")
    x = 128*((flagnum%256)%16)
    y = 128*int((flagnum%256)/16)
    flagimg = flagfile.crop((x, y, x+127, y+127))
    flagimg.load()
    return flagimg

def provinceArea(provinceID: Union[str, int]) -> str:
    """Returns the area (state) name of a specified province's id.
    Raises an error if the province is not found.
    """
    
    srcFile = open("src\\area.txt", "r")
    lines = srcFile.readlines()
    currentArea = None
    for line in lines:
        if " = {" in line:
            currentArea = line.split(" ")[0].strip("\t ={\n")
        else:
            if str(provinceID) in line.split():
                return currentArea
    # Was not found
    raise ValueError(str(provinceID) + " was not a valid province.")

def region(areaName: str) -> str:
    """Returns the region name of a specified area.
    The argument may be the string returned by the provinceArea() method.
    Raises an error if the area is not found.
    """
    
    srcFile = open("src\\region.txt", "r")
    lines = srcFile.readlines()
    currentRegion = None
    for line in lines:
        if " = {" in line and not line.startswith("\t"):
            currentRegion = line.split(" ")[0].strip("\t ={\n")
        else:
            if line.strip("\n\t ") == areaName:
                return currentRegion
    # Was not found
    raise ValueError(str(areaName) + " was not a valid area.")

def superregion(regionName: str) -> str:
    """Returns the superregion name of a specified region.
    The argument may be the string returned by the region() method.
    Raises an error if the region is not found.
    """
    
    srcFile = open("src\\superregion.txt", "r")
    lines = srcFile.readlines()
    currentSuperregion = None
    for line in lines:
        if " = {" in line and not line.startswith("\t"):
            currentSuperregion = line.split(" ")[0].strip("\t ={\n")
        else:
            if line.strip("\n\t ") == regionName:
                return currentSuperregion
    # Was not found
    raise ValueError(str(regionName) + " was not a valid region.")

def continent(provinceID: Union[str, int]) -> str:
    """Returns the continent name from a specified province's id.
    Raises an error if the province is not found.
    """
    
    srcFile = open("src\\continent.txt", "r")
    lines = srcFile.readlines()
    currentContinent = None
    for line in lines:
        if " = {" in line:
            currentContinent = line.split(" ")[0].strip("\t ={\n")
        else:
            if str(provinceID) in line.split():
                return currentContinent
    # Was not found
    raise ValueError(str(provinceID) + " was not a valid province.")

class dataReq:
    DATATYPE_PROVINCEDAT = 0
    REQUEST_PROVINCE_NAME = 0
    REQUEST_PROVINCE_TRADE = 1
    REQUEST_PROVINCE_CULTURE_ORIGINAL = 2
    REQUEST_PROVINCE_RELIGION_ORIGINAL = 3
    def __init__(self, datatype: int, key: str, request: int):
        self.datatype = datatype
        self.key = key
        self.request = request
        self.response = None
    def respond(self, r):
        if self.datatype == self.DATATYPE_PROVINCEDAT:
            if self.request == self.REQUEST_PROVINCE_NAME:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError("PROVINCE NAME request for " + self.key + " was the wrong type.")
            elif self.request == self.REQUEST_PROVINCE_TRADE:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError("PROVINCE TRADE request for " + self.key + " was the wrong type.")
            elif self.request == self.REQUEST_PROVINCE_CULTURE_ORIGINAL:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError("PROVINCE CULTURE ORIGINAL request for " + self.key + " was the wrong type.")
            elif self.request == self.REQUEST_PROVINCE_RELIGION_ORIGINAL:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError("PROVINCE RELIGION ORIGINAL request for " + self.key + " was the wrong type.")
            # More things
        # More datatypes
def provinceData(*requests: dataReq) -> List[dataReq]:
    data = requests
    lines = open("src\\save_1444.eu4").readlines()
    brackets = []
    
    #Reading save file...
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
                #print("Unexpected brackets at line #" + str(linenum) + ": " + line)
                pass
            #print("{")
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:
                #print("No brackets to delete.")
                #print("Line", linenum, ":", line)
                pass
            #print("}")
        #Get rid of long, useless sections
        elif len(brackets) == 2 and "provinces={" == brackets[0]:
            for request in data:
                if request.response is None and request.datatype == dataReq.DATATYPE_PROVINCEDAT and ("-" + str(request.key) + "={") == brackets[1]:
                    if request.request == dataReq.REQUEST_PROVINCE_NAME and line.startswith("\t\tname="):
                        request.respond(line.split("\"", 2)[1].strip("\n\t "))
                    elif request.request == dataReq.REQUEST_PROVINCE_TRADE and line.startswith("\t\ttrade="):
                        request.respond(line.split("\"", 2)[1].strip("\n\t "))
                    elif request.request == dataReq.REQUEST_PROVINCE_CULTURE_ORIGINAL and line.startswith("\t\toriginal_culture="):
                        request.respond(line.split("=", 1)[1].strip("\n\t "))
                    elif request.request == dataReq.REQUEST_PROVINCE_RELIGION_ORIGINAL and line.startswith("\t\toriginal_religion="):
                        request.respond(line.split("=", 1)[1].strip("\n\t "))
        elif len(brackets) < 0 and ("trade={" == brackets[1]  or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
            continue
        else:
            pass
    return data