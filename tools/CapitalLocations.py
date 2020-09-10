from typing import List, Dict, Tuple
import os
import sys
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import EU4Lib

start = time.time()
tagCapitals: Dict[str, int] = {}

saveFile = open("src/save_1444.eu4", "r", encoding="cp1252")
lines = saveFile.readlines()
saveFile.close()
del(saveFile)

brackets: List[str] = []
linenum = 0
inCountries = False
done = False
for line in lines:
    linenum += 1
    if inCountries:
        if "{" in line:
            opencount = line.count("{")
            closecount = line.count("}")
            if opencount == closecount:
                continue
            elif closecount == 0 and opencount == 1:
                brackets.append(line.rstrip("\n "))
            elif closecount == 0 and opencount > 1:
                for x in range(opencount):
                    brackets.append("{")  # TODO: fix this so it has more
            else:
                print("Unexpected brackets at line " +
                      str(linenum) + ": " + line)
        elif "}" in line:
            try:
                brackets.pop()
            except IndexError:  # This shouldn't happen.
                print("No brackets to delete.")
                print("Line " + linenum + ": " + line)
        elif len(brackets) == 2 and brackets[0] == "countries={":
            if "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                tagCapitals[brackets[1].strip("\n\t ={")] = int(
                    line.strip("\tcapitl=\n"))
    elif "countries={" in line and not "players_countries={" in line and not "interesting_countries={" in line:
        inCountries = True
        brackets.append(line.rstrip("\n "))
    elif done:
        break
del(lines)
print("Found all capitals.")

capitalLocs: Dict[str, Tuple[int, int]] = {}
for x in tagCapitals:
    capitalLocs[x] = EU4Lib.province(tagCapitals[x])
print("Found all locations.")

writeFile = open("src/tagCapitals.txt", "w", encoding="cp1252")
writeString = ""
for x in capitalLocs:
    try:
        writeString += x + "=" + \
            str(capitalLocs[x][0]) + "," + str(capitalLocs[x][1]) + "\n"
    except TypeError:
        # Tags like colonial nations, rebels, etc. have None as their capital
        pass
writeFile.write(writeString)
print("Written.")

print(time.time() - start)
