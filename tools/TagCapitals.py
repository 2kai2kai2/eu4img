from io import TextIOWrapper
from typing import List, Dict
import os
import yaml


def readSave(file: TextIOWrapper) -> Dict[str, int]:
    out: Dict[str, int] = {}

    brackets: List[str] = []
    linenum = 0
    inCountries = False
    done = False
    for line in file:
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
                    print(
                        f"Unexpected close brackets at line {linenum}: {line}")
            elif len(brackets) == 2 and brackets[0] == "countries={":
                if "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                    out[brackets[1].strip("\n\t ={").upper()] = int(
                        line.strip("\tcapitl=\n"))
        elif "countries={" in line and not "players_countries={" in line and not "interesting_countries={" in line:
            inCountries = True
            brackets.append(line.rstrip())
        elif done:
            break
    return out


def saveTagCapitals(file: TextIOWrapper, data: Dict[str, int]):
    yaml.dump(data, file)


if __name__ == "__main__":
    savePath = input("Save File: ").strip('"& ')
    file_dir = os.path.join("resources", input(
        "Target name: "), "tagCapitals.yml")

    saveFile = open(savePath, "r", encoding="cp1252", errors="replace")
    destFile = open(file_dir, "w")
    saveTagCapitals(destFile, readSave(saveFile))
