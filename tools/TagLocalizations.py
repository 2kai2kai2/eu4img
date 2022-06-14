from typing import List
from os import path, listdir
import unicodedata


def loadLanguage(language: str, directory: str) -> List[str]:
    """Compile all the lines from all the files"""
    # Find the files we need
    allFiles = listdir(directory)
    specFiles: List[str] = [f for f in allFiles if path.isfile(
        f"{directory}\\{f}") and language in f]
    allLines: List[str] = []
    for f in specFiles:
        fileObj = open(f"{directory}\\{f}", "r", encoding="utf8")
        allLines.extend(fileObj.readlines())
        fileObj.close()
        del(fileObj)
    return allLines


def filterTags(allLines: List[str]) -> List[str]:
    """Find only the ones that are nation tags"""
    invalidTags = ["---", "ADM", "AGE", "AND", "ART", "CAV", "DIP",
                   "INF", "PIR", "PTI", "REQ", "REX", "TAX", "THE", "YES", "ZEN"]
    tagLines: List[str] = [line for line in allLines if len(
        line) > 5 and line[0] == " " and line[4] == ":" and line[:5] == line[:5].upper() and line[1:4] not in invalidTags]
    return sorted(tagLines)


def deaccent(string: str) -> str:
    return str(unicodedata.normalize('NFKD', string)).encode('ASCII', 'ignore').decode('ASCII')


def writeOutput(tagLines: List[str], target: str):
    writeString = ""
    for line in tagLines:
        line = line.rstrip()
        name = line[line.index('"')+1:line.rindex('"')]
        if name != deaccent(name):
            line += f' "{deaccent(name)}"'
        if name.startswith("The "):
            line += f' "{deaccent(name)[4:]}"'
        writeString += f"{line}\n"

    open(target, "w", encoding="cp1252", errors="replace").write(writeString)


if __name__ == "__main__":
    language = "english"
    directory = None
    while directory is None:
        directory = input("Please enter directory: ")

        # Fix directory when dragging file from explorer into VS code terminal
        if directory.startswith("&"):
            directory = directory.strip("& '")

        # Check if directory exists
        if not path.exists(directory):
            print("Path not found.")
            directory = None
        else:
            print("Path found.")
    allLines = loadLanguage(language, directory)
    print(f"Loaded files for language {language}.")
    allTags = filterTags(allLines)
    print("Found tags.")
    writeOutput(allTags, "resources/countries_l_english.yml")
    print("Written to file.")
