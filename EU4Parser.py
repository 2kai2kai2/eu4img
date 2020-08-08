from typing import List, Optional, Union, Tuple
import re
import time

"""
My idea for how to start going about this is to go through each item on the first level and get the key and value.
If the value has brackets, then we go through each element in that and so on.
However, differentiating between lists of value-key pairs and lists of just values could be an issue.

Groups seem to be defined by the {} brackets, with dividers being any whitespace. This excludes whitespace within quotes or sub-groups.
Groups can either have just values like a list, or key-value pairs like a dict. I am assuming but not certain that a group can't have both.

So, the best way to split it up might be to go through and divide by whitespace but whenever a {} or "" is found, ignore whitespace until it is closed.
Then if the elements are key-value pairs, make it a dict, or if just values, a list
Then go through each value and if it's a group do the same.
"""

testtext = """EU4txt
date=1444.11.11
save_game=".eu4"
player="SWE"
displayed_country_name="Sweden"
savegame_version={
	first=1
	second=30
	third=1
	forth=0
	name="Austria"
}
savegame_versions={
	"1.30.1.0"
}
dlc_enabled={
	"Conquest of Paradise"
	"Wealth of Nations"
	"Res Publica"
	"Art of War"
	"El Dorado"
	"Common Sense"
	"The Cossacks"
	"Mare Nostrum"
	"Rights of Man"
	"Mandate of Heaven"
	"Third Rome"
	"Cradle of Civilization"
	"Rule Britannia"
	"Dharma"
	"Golden Century"
	"Emperor"
}
multi_player=no
not_observer=yes
campaign_id="f335dae5-e5e8-4a1c-aa48-7214d41fe460"
campaign_length=0
campaign_stats={
{
		id=0
		comparison=1
		key="game_country"
		selector="SWE"
		localization="Sweden"
	}
{
		id=1
		comparison=2
		key="longest_reign"
		localization="Christopher III"
	}
{
		id=2
		comparison=2
		key="wars_won"
	}
{
		id=3
		comparison=2
		key="wars_lost"
	}
{
		id=4
		comparison=2
		key="army_kills"
	}
{
		id=5
		comparison=2
		key="army_losses"
	}
{
		id=6
		comparison=2
		key="navy_kills"
	}
{
		id=7
		comparison=2
		key="navy_losses"
	}
{
		id=8
		comparison=2
		key="countries_removed"
	}
{
		id=9
		comparison=2
		key="provs_taken"
	}
{
		id=10
		comparison=2
		key="provs_lost"
	}
{
		id=11
		comparison=0
		key="leader_count"
	}
{
		id=12
		comparison=0
		key="best_leader"
	}
{
		id=13
		comparison=1
		key="religion"
		selector="catholic"
		localization="Catholic"
	}
{
		id=14
		comparison=2
		key="best_prov"
		localization="Stockholm"
		value=13.000
	}
{
		id=15
		comparison=2
		key="disasters"
	}
}
players_countries={
	"2kai2kai2"
	"SWE"
}
gameplaysettings={
	setgameplayoptions={
		1 1 0 1 0 0 0 0 0 1 0 1 2 0 0 0 0 1 1 1 1 0 3 0 0 1 0 1 0 0 0 1 
	}
}
"""


class eu4Date:
    def __init__(self, datestr: str):
        yearstr, monthstr, daystr = datestr.strip().split(".")
        self.year = int(yearstr)
        self.month = int(monthstr)
        self.day = int(daystr)

    @property
    def fancyStr(self):
        monthnames = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
                      7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
        return str(self.day) + " " + monthnames[self.month] + " " + str(self.year)

    def __str__(self):
        return str(self.year) + "." + str(self.month) + "." + str(self.day)

    def __eq__(self, other) -> bool:
        if not isinstance(other, eu4Date):
            return False
        return self.year == other.year and self.month == other.month and self.day == other.day

    def __ne__(self, other) -> bool:
        if not isinstance(other, eu4Date):
            return True
        return self.year != other.year or self.month != other.month or self.day != other.day

    def __lt__(self, other) -> bool:
        if not isinstance(other, eu4Date):
            raise TypeError("eu4Date can only be compared with eu4Date.")
        return self.year < other.year or (self.year == other.year and (self.month < other.month or (self.month == other.month and self.day < other.day)))

    def __le__(self, other) -> bool:
        if not isinstance(other, eu4Date):
            raise TypeError("eu4Date can only be compared with eu4Date.")
        return self == other or self < other

    def __gt__(self, other) -> bool:
        if not isinstance(other, eu4Date):
            raise TypeError("eu4Date can only be compared with eu4Date.")
        return self.year > other.year or (self.year == other.year and (self.month > other.month or (self.month == other.month and self.day > other.day)))

    def __ge__(self, other) -> bool:
        if not isinstance(other, eu4Date):
            raise TypeError("eu4Date can only be compared with eu4Date.")
        return self == other or self > other


intregex = re.compile(r"\d+")
floatregex = re.compile(r"\d+\.\d+")
dateregex = re.compile(r"\d{1,4}\.\d{1,2}\.\d{1,2}")
groupregex = re.compile(r"\{(.|\n)*\}")


def splitStrings(text: str) -> List[str]:
    """
    Splits along all whitespace not within "{" brackets or quotes.

    When splitting groups, exclude the start and end brackets.
    """
    items: List[str] = []
    # This will only contain "{" and "\"" and whenever we run into something to close the last one, it is removed.
    # However, brackets can never be within quotes.
    bracketOrder: List[str] = []
    lastsplit = 0
    for i in range(len(text)):
        char = text[i]
        if len(bracketOrder) == 0 and char.isspace():
            split = text[lastsplit:i]
            lastsplit = i
            if not split.isspace() and not split == "":
                items.append(split.strip())
        elif char == "{" and not (len(bracketOrder) > 0 and bracketOrder[-1] == "\""):
            bracketOrder.append(char)
        elif char == "}" and not (len(bracketOrder) > 0 and bracketOrder[-1] == "\""):
            if bracketOrder[-1] == "{":
                bracketOrder.pop()
        elif char == "\"":
            if len(bracketOrder) > 0 and bracketOrder[-1] == "\"":
                bracketOrder.pop()
            else:
                bracketOrder.append(char)
    # At the end, if there isn't whitespace then we need to just add whatever the last thing was.
    split = text[lastsplit:]
    if not split.isspace():
        items.append(split.strip())
    return items


def parseGroup(group: List[str]) -> Union[List[str], dict]:
    if len(group) == 0:
        return []
    elif "=" in group[0] and ("{" not in group[0] or (group[0].index("=") < group[0].index("{"))):
        # It's a dict.
        dictGroup = {}
        for item in group:
            key, value = item.split("=", maxsplit=1)
            dictGroup[key] = parseType(value)
        return dictGroup
    else:
        # It's a list.
        listGroup = []
        for item in group:
            listGroup.append(parseType(item))
        return listGroup


def parseType(text: str) -> Union[str, int, float, eu4Date, List[str], dict]:
    text = text.strip()
    if re.fullmatch(intregex, text) is not None:
        return int(text)
    elif re.fullmatch(floatregex, text) is not None:
        return float(text)
    elif re.fullmatch(dateregex, text) is not None:
        return eu4Date(text)
    elif re.fullmatch(groupregex, text) is not None:
        # The string starts and ends with {} so we need to remove that for splitting
        return parseGroup(splitStrings(text[1:-1]))
    else:  # str
        return text.strip("\"")


def formatFix(text: str) -> str:
    return text.replace("map_area_data{", "map_area_data={").replace("EU4txt", "")


starttime = time.time()
file = open("src/save_1444.eu4", "r", encoding="cp1252")
text = formatFix(file.read())
file.close()
totaltime = time.time() - starttime
print("File load: " + str(totaltime) + "s. | " +
      str(totaltime/len(text)) + "s/char")

data = {}
starttime = time.time()
g = parseGroup(splitStrings(testtext)[1:])
# print(g)
totaltime = time.time() - starttime
print("Parsing: " + str(totaltime) + "s. | " +
      str(totaltime/len(text)) + "s/char")
