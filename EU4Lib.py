from typing import Dict, Optional, Tuple, Union
import yaml

from PIL import Image, ImageDraw
from os import listdir, path


def country(text: str, mod: str = "vanilla") -> Optional[str]:
    """
    Returns the tag of a nation from the name of the nation.

    Some nations may have multiple valid names.
    If the nation is not recognized, returns None.
    """
    text = text.upper()
    # Read out the countries file
    srcFile = open(
        f"resources/{mod}/countries_l_english.yml", encoding="cp1252")
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


def tagToName(tag: str, mod: str = "vanilla") -> Optional[str]:
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
        srcFile = open(
            f"resources/{mod}/countries_l_english.yml", encoding="cp1252")
        for line in srcFile:
            if line[1:4] == tag:
                firstQuote = line.index('"')
                return line[firstQuote+1:line.index('"', firstQuote+1)]
    # Tag was not found or is not valid 3-character str
    return None


# LOAD PROVINCE LOCATION DATA
# Even if not __main__
province_locations: Dict[str, Dict[int, Tuple[float, float]]] = {}
for p in listdir("resources"):
    filepath = path.join("resources", p, "positions.yml")
    if path.isfile(filepath):
        province_locations_file = open(filepath, "r")
        province_locations[p] = yaml.load(
            province_locations_file, yaml.CLoader)
        province_locations_file.close()


def province(id: Union[str, int], mod: str = "vanilla") -> Tuple[float, float]:
    """
    Gets the location of a province on a screenshot map.

    Returns a tuple of floats, (x, y).
    """
    return province_locations[mod][int(id)]


# LOAD INITIAL TAG CAPITAL DATA
# Even if not __main__
tag_capitals: Dict[str, Dict[str, int]] = {}
for p in listdir("resources"):
    filepath = path.join("resources", p, "tagCapitals.yml")
    if path.isfile(filepath):
        tag_capitals_file = open(filepath, "r")
        tag_capitals[p] = yaml.load(tag_capitals_file, yaml.CLoader)
        tag_capitals_file.close()


def tagCapital(tag: str, mod: str = "vanilla") -> int:
    return tag_capitals[mod][tag]


def flag(tag: str, mod: str = "vanilla") -> Image.Image:
    """
    Gets an Image of the flag of the specified nation.

    Returns Image of size (128, 128).
    """
    # Read file
    srcFile = open(f"resources/{mod}/flagfiles.txt", "r", encoding="cp1252")
    line = srcFile.read()
    srcFile.close()
    # Get the number for the order of the flag; starts at 0
    flagnum = line[:line.index(tag)].count(".tga")
    # Get the file based on 256 flags per
    flagfile = Image.open(f"resources/{mod}/flagfiles_{int(flagnum/256)}.tga")
    # Get the location of the flag within the file
    x = 128*((flagnum % 256) % 16)
    y = 128*int((flagnum % 256)/16)
    # Get the actual flag image and return it
    flagimg = flagfile.crop((x, y, x+127, y+127))
    flagimg.load()
    return flagimg


def provinceArea(provinceID: Union[str, int], mod: str = "vanilla") -> str:
    """
    Returns the area (state) name of a specified province's id.

    Raises an error if the province is not found.
    """
    provinceID = str(provinceID)
    # Read file
    srcFile = open(f"resources/{mod}/area.txt", "r", encoding="cp1252")
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


def region(areaName: str, mod: str = "vanilla") -> str:
    """
    Returns the region name of a specified area.

    The argument may be the string returned by the provinceArea() method.
    Raises an error if the area is not found.
    """
    # Read file
    srcFile = open(f"resources/{mod}/region.txt", "r", encoding="cp1252")
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


def superregion(regionName: str, mod: str = "vanilla") -> str:
    """
    Returns the superregion name of a specified region.

    The argument may be the string returned by the region() method.
    Raises an error if the region is not found.
    """
    # Read file
    srcFile = open(f"resources/{mod}/superregion.txt", "r", encoding="cp1252")
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


def continent(provinceID: Union[str, int], mod: str = "vanilla") -> str:
    """
    Returns the continent name from a specified province's id.

    Raises an error if the province is not found.
    """
    provinceID = str(provinceID)
    # Read file
    srcFile = open(f"resources/{mod}/continent.txt", "r", encoding="cp1252")
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


def isIn(provinceID: Union[str, int], group: str, mod: str = "vanilla") -> bool:
    """
    Checks if the province is within the given area, region, superregion, or continent.
    """
    # Because area, region, and superregion has the suffix with _area, etc. each can't be confused with the other.
    provarea = provinceArea(provinceID, mod)
    if provarea == group:
        return True
    provregion = region(provarea, mod)
    if provregion == group:
        return True
    provsuperregion = superregion(provregion, mod)
    if provsuperregion == group:
        return True
    provcontinent = continent(provinceID, mod)
    if provcontinent == group:
        return True
    return False


def colonialRegion(provinceID: Union[str, int], mod: str = "vanilla") -> str:
    """
    Returns the colonial region from a specified province's id.

    Raises an error if the province is not found in a colonial region.
    """
    provinceID = str(provinceID)
    # Read file
    srcFile = open(
        f"resources/{mod}/00_colonial_regions.txt", "r", encoding="cp1252")
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


def colonialFlag(overlordTag: str, colReg: str, mod: str = "vanilla") -> Image.Image:
    """
    Generates a colonial nation flag for the given motherland and colonial region.
    """
    # First find the correct colonial region color
    color: Tuple[int, int, int] = None
    # Read file
    srcFile = open(
        f"resources/{mod}/00_colonial_regions.txt", "r", encoding="cp1252")
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
