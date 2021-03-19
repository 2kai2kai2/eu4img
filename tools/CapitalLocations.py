from typing import List, Dict, Tuple
import os
import sys
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import EU4Lib

start = time.time()
tagCapitals: Dict[str, int] = {}

saveFile = open("resources/save_1444.eu4", "r", encoding="cp1252")

brackets: List[str] = []
linenum = 0
inCountries = False
done = False
for line in saveFile:
    linenum += 1
    if inCountries:
        if "{" in line:
            opencount = line.count("{")
            closecount = line.count("}")
            if opencount == closecount:
                continue
            elif closecount == 0 and opencount == 1:
                brackets.append(line.rstrip())
            elif closecount == 0 and opencount > 1:
                for x in range(opencount):
                    brackets.append("{")  # TODO: fix this so it has more
            else:
                print(f"Unexpected brackets at line {linenum}: {line}")
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:  # This shouldn't happen.
                print(f"Unexpected close brackets at line {linenum}: {line}")
        elif len(brackets) == 2 and brackets[0] == "countries={":
            if "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                tagCapitals[brackets[1].strip("\n\t ={")] = int(
                    line.strip("\tcapitl=\n"))
    elif "countries={" in line and not "players_countries={" in line and not "interesting_countries={" in line:
        inCountries = True
        brackets.append(line.rstrip())
    elif done:
        break
print("Found all capital province ids.")

locations: Dict[int, Tuple[float, float]
                ] = EU4Lib.provinces(tagCapitals.values())
capitalLocs: Dict[str, Tuple[float, float]] = {}
for x in tagCapitals:
    if tagCapitals[x] in locations:
        capitalLocs[x] = locations[tagCapitals[x]]
print("Found all capital locations.")

writeFile = open("resources/tagCapitals.txt", "w", encoding="cp1252")
writeString = ""
for x in capitalLocs:
    try:
        writeString += f"{x}={capitalLocs[x][0]},{capitalLocs[x][1]}\n"
    except TypeError:
        # Tags like colonial nations, rebels, etc. have None as their capital
        pass
writeFile.write(writeString)
print("Data written to file.")
print(f"Total time taken: {time.time() - start}s.")
