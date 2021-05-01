# This will need to be updated. Currently for 1.30.2
from typing import Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw


def country(text: str) -> Optional[str]:
    """
    Returns the tag of a nation from the name of the nation.

    Some nations may have multiple valid names.
    If the nation is not recognized, returns None.
    """
    text = text.upper()
    # Read out the countries file
    srcFile = open("resources/countries_l_english.yml", encoding="cp1252")
    # If it could be a tag, check for that.
    if len(text) == 3:
        # Check dynamic tags
        if text[1:].isdigit():
            firstchar = text[0]
            if firstchar == "C" or firstchar == "D" or firstchar == "E" or firstchar == "K" or firstchar == "T":
                return text
        # Check raw tags
        for line in srcFile:
            if line[1:4] == text:
                return text
    # text is not a recognized tag, search names
    for line in srcFile:
        if f'"{text}"' in line.upper():
            return line[1:4]
    # text is unknown
    return None


def tagToName(tag: str) -> Optional[str]:
    """
    Returns the name of a nation based on its tag.

    If the tag is not recognized, returns None.
    """
    tag = tag.upper()
    # If it could be a valid tag
    if len(tag) == 3:
        if tag[1:].isdigit():
            # Dynamic tag
            if tag[0] == "C":
                # Colonial Nation
                return f"Colonial Nation C{tag[1:]}"
            elif tag[0] == "D":
                # Custom Nation
                return f"Custom Nation D{tag[1:]}"
            elif tag[0] == "E":
                # Estate Disaster-Released Nation
                return f"Estate Nation E{tag[1:]}"
            elif tag[0] == "K":
                # Client State
                return f"Client State K{tag[1:]}"
            elif tag[0] == "T":
                # Trading City
                return f"Trading City T{tag[1:]}"
        # Then search for it and return the first thing in quotes on that line
        # Read out the countries file
        srcFile = open("resources/countries_l_english.yml", encoding="cp1252")
        for line in srcFile:
            if line[1:4] == tag:
                firstQuote = line.index('"')
                return line[firstQuote+1:line.index('"', firstQuote+1)]
    # Tag was not found or is not valid 3-character str
    return None


def province(id: Union[str, int]) -> Optional[Tuple[float, float]]:
    """
    Gets the location of a province on a screenshot map.

    Returns a tuple of floats, (x, y).
    """
    # Read file
    srcFile = open("resources/positions.txt", "r", encoding="cp1252")
    """
    Format of the file:
    1={
        position={
            3085.000 1723.000 3086.000 1730.000 3084.500 1729.000 3095.000 1724.500 3082.000 1730.000 3080.000 1736.000 0.000 0.000 
        }
        rotation={
            0.000 0.000 0.087 -0.698 0.000 0.000 0.000 
        }
        height={
            0.000 0.000 1.000 0.000 0.000 0.000 0.000 
        }
    }
    
    So we want the 3085.000 1723.000 from the 1={ because the first two are the location of the city in the province
    """
    beyond = 0
    for line in srcFile:
        if beyond == 2:  # Two after the province, this is the line with the position.
            vals = line.split()
            # Need to subtract the y value because the position starts from the bottom rather than the top like images
            return (float(vals[0]), 2048-float(vals[1]))
        elif beyond == 1:  # One after the province, wait one more line for the position
            beyond = 2
        elif line.strip() == str(id)+"={":
            # So we have the province... Wait two lines for the position
            beyond = 1
    return None


def provinces(ids: List[Union[str, int]]) -> Dict[int, Tuple[float, float]]:
    """
    Gets the location of multiple provinces on a screenshot map.
    Similar to province() except that it will only go through the file once to find all provinces.
    """
    out: Dict[int, Optional[Tuple[float, float]]] = {}
    idsprocessed = [int(x) for x in ids]
    srcFile = open("resources/positions.txt", "r", encoding="cp1252")
    currentID: int = None
    beyond = 0
    for line in srcFile:
        if beyond == 2:  # Two after the province, this is the line with the position.
            vals = line.split()
            # Need to subtract the y value because the position starts from the bottom rather than the top like images
            out[currentID] = (float(vals[0]), 2048-float(vals[1]))
            currentID = None
            beyond = 0
        elif beyond == 1:  # One after the province, wait one more line for the position
            beyond = 2
        elif line.strip("\t ={\n").isdigit():  # Province top-level bracket
            id = int(line[:line.index("={")])
            if id in idsprocessed:
                currentID = id
                beyond = 1
    return out


def flag(tag: str) -> Image.Image:
    """
    Gets an Image of the flag of the specified nation.

    Returns Image of size (128, 128).
    """
    # Read file
    srcFile = open("resources/flagfiles.txt", "r", encoding="cp1252")
    line = srcFile.read()
    srcFile.close()
    # Get the number for the order of the flag; starts at 0
    flagnum = line[:line.index(tag)].count(".tga")
    # Get the file based on 256 flags per
    flagfile = Image.open(f"resources/flagfiles_{int(flagnum/256)}.tga")
    # Get the location of the flag within the file
    x = 128*((flagnum % 256) % 16)
    y = 128*int((flagnum % 256)/16)
    # Get the actual flag image and return it
    flagimg = flagfile.crop((x, y, x+127, y+127))
    flagimg.load()
    return flagimg


def provinceArea(provinceID: Union[str, int]) -> str:
    """
    Returns the area (state) name of a specified province's id.

    Raises an error if the province is not found.
    """
    provinceID = str(provinceID)
    # Read file
    srcFile = open("resources/area.txt", "r", encoding="cp1252")
    # Search file
    currentArea = None
    for line in srcFile:
        # Set the current area for when it goes again and has the provinces
        if " = {" in line and not line[0].isspace():
            currentArea = line[:line.index(" = {")]
        # If it's the right province, return the area
        else:
            if provinceID in line.split():
                return currentArea
    # Was not found
    raise ValueError(f"{provinceID} was not a valid province.")


def region(areaName: str) -> str:
    """
    Returns the region name of a specified area.

    The argument may be the string returned by the provinceArea() method.
    Raises an error if the area is not found.
    """
    # Read file
    srcFile = open("resources/region.txt", "r", encoding="cp1252")
    # Search File
    currentRegion = None
    for line in srcFile:
        # Get the region for the next lines
        if " = {" in line and not line[0].isspace():
            currentRegion = line[:line.index(" = {")]
        # If it's the right area, return the region
        elif line.strip() == areaName:
            return currentRegion
    # Was not found
    raise ValueError(f"{areaName} was not a valid area.")


def superregion(regionName: str) -> str:
    """
    Returns the superregion name of a specified region.

    The argument may be the string returned by the region() method.
    Raises an error if the region is not found.
    """
    # Read file
    srcFile = open("resources/superregion.txt", "r", encoding="cp1252")
    # Search file
    currentSuperregion = None
    for line in srcFile:
        # Get the superregion for the next lines
        if " = {" in line and not line[0].isspace():
            currentSuperregion = line[:line.index(" = {")]
        # If it's the right region, return the superregion
        elif line.strip() == regionName:
            return currentSuperregion
    # Was not found
    raise ValueError(f"{regionName} was not a valid region.")


def continent(provinceID: Union[str, int]) -> str:
    """
    Returns the continent name from a specified province's id.

    Raises an error if the province is not found.
    """
    provinceID = str(provinceID)
    # Read file
    srcFile = open("resources/continent.txt", "r", encoding="cp1252")
    # Search file
    currentContinent = None
    for line in srcFile:
        # Get the continent for the following lines
        if " = {" in line:
            currentContinent = line[:line.index(" = {")]
        # If it's the right province, return the continent
        elif provinceID in line.split():
            return currentContinent
    # Was not found
    raise ValueError(f"{provinceID} was not a valid province.")


def isIn(provinceID: Union[str, int], group: str) -> bool:
    """
    Checks if the province is within the given area, region, superregion, or continent.
    """
    # Because area, region, and superregion has the suffix with _area, etc. each can't be confused with the other.
    provarea = provinceArea(provinceID)
    if provarea == group:
        return True
    provregion = region(provarea)
    if provregion == group:
        return True
    provsuperregion = superregion(provregion)
    if provsuperregion == group:
        return True
    provcontinent = continent(provinceID)
    if provcontinent == group:
        return True
    return False


def colonialRegion(provinceID: Union[str, int]) -> str:
    """
    Returns the colonial region from a specified province's id.

    Raises an error if the province is not found in a colonial region.
    """
    provinceID = str(provinceID)
    # Read file
    srcFile = open("resources/00_colonial_regions.txt", "r", encoding="cp1252")
    # Search file
    currentColReg: Optional[str] = None
    provsOpen = False
    for line in srcFile:
        # First get the colonial region. No indent.
        if " = {" in line and not line[0].isspace():
            currentColReg = line[:line.index(" = {")]
        elif currentColReg is not None and "\tprovinces = {" in line:
            provsOpen = True
        elif provsOpen is True:
            if "}" in line:
                provsOpen = False
            elif provinceID in line.split():
                return currentColReg
    # Was not found
    raise ValueError(
        f"{provinceID} was not a valid province in a colonial region.")


def colonialFlag(overlordTag: str, colReg: str) -> Image.Image:
    """
    Generates a colonial nation flag for the given motherland and colonial region.
    """
    # First find the correct colonial region color
    color: Tuple[int, int, int] = None
    # Read file
    srcFile = open("resources/00_colonial_regions.txt", "r", encoding="cp1252")
    # Search file
    currentColReg: Optional[str] = None
    for line in srcFile:
        # First get the colonial region. No indent.
        if " = {" in line and not line[0].isspace():
            currentColReg = line[:line.index(" = {")]
        elif currentColReg == colReg and "\tcolor = {" in line:
            colorR, colorG, colorB = line[line.index(
                "{")+1:line.rindex("}")].split()
            color = (int(colorR), int(colorG), int(colorB))
    # Raise error if the colonial region or color was invalid
    if currentColReg is None:
        raise ValueError(f"Colonial Region \"{colReg}\" was not found.")
    elif colorR is None or colorG is None or colorB is None:
        raise ValueError(
            f"Something went very wrong. No color was found in the source file for the Colonial Region \"{colReg}\".")
    # Image editing
    flagimg: Image.Image = flag(overlordTag)
    flagDraw = ImageDraw.Draw(flagimg)
    flagDraw.rectangle([64, 0, 127, 127], color)
    return flagimg


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
                    raise ValueError(
                        f"PROVINCE NAME request for {self.key} was the wrong type.")
            elif self.request == self.REQUEST_PROVINCE_TRADE:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError(
                        f"PROVINCE TRADE request for {self.key} was the wrong type.")
            elif self.request == self.REQUEST_PROVINCE_CULTURE_ORIGINAL:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError(
                        f"PROVINCE CULTURE ORIGINAL request for {self.key} was the wrong type.")
            elif self.request == self.REQUEST_PROVINCE_RELIGION_ORIGINAL:
                if isinstance(r, str):
                    self.response = r
                else:
                    raise ValueError(
                        f"PROVINCE RELIGION ORIGINAL request for {self.key} was the wrong type.")
            # More things
        # More datatypes


def provinceData(*requests: dataReq) -> List[dataReq]:
    data = requests
    srcFile = open("resources/save_1444.eu4", encoding="cp1252")
    brackets: List[str] = []

    # Reading save file...
    linenum = 0
    for line in srcFile:
        linenum += 1
        if "{" in line:
            if line.count("{") == line.count("}"):
                continue
            elif line.count("}") == 0 and line.count("{") == 1:
                brackets.append(line.rstrip("\n "))
            elif line.count("}") == 0 and line.count("{") > 1:
                # TODO: fix this so it has more stuff
                brackets.append("{" * line.count("{"))
            else:
                pass
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:
                pass
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
        # elif len(brackets) < 0 and ("trade={" == brackets[1]  or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
        #    continue
        else:
            pass
    return data
