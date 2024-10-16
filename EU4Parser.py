import time
from typing import List, Union

import cppimport.import_hook

import EU4cppparser

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


def formatFix(text: str) -> str:
    return text.replace("map_area_data{", "map_area_data={").replace("EU4txt", "")


starttime = time.time()
file = open("resources/save_1444.eu4", "r", encoding="cp1252")
text = formatFix(file.read())
file.close()
totaltime = time.time() - starttime
print(f"File load: {totaltime}s. | {totaltime/len(text)}s/char")

starttime = time.time()
count = 10
for i in range(count):
    EU4cppparser.parseValue("{"+text+"}")
    print(f"Finished {i + 1}/{count}")
totaltime = time.time() - starttime
print(f"Parsing: {totaltime/count}s. | {totaltime/len(text)/count}s/char")
