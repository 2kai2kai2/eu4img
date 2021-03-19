from typing import List
from os import path, listdir
import unicodedata

language = "english"
invalidTags = ["---", "ADM", "AGE", "AND", "ART", "CAV", "DIP", "INF", "PIR", "PTI", "REQ", "REX", "TAX", "THE", "YES", "ZEN"]

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

# Find the files we need
allFiles = listdir(directory)
specFiles: List[str] = [f for f in allFiles if path.isfile(f"{directory}\\{f}") and language in f]

# Compile all the lines from all the files
allLines: List[str] = []
for f in specFiles:
    fileObj = open(f"{directory}\\{f}", "r", encoding="utf8")
    allLines.extend(fileObj.readlines())
    fileObj.close()
    del(fileObj)
print(f"Loaded files for language {language}.")

# Find only the ones that are nation tags
tagLines: List[str] = [line for line in allLines if len(line) > 5 and line[0] == " " and line[4] == ":" and line[:5] == line[:5].upper() and line[1:4] not in invalidTags]
tagLines.sort()
print("Found tags.")


def deaccent(string: str) -> str:
    return str(unicodedata.normalize('NFKD', string)).encode('ASCII', 'ignore').decode('ASCII')

writeString = ""
for line in tagLines:
    line = line.rstrip()
    name = line[line.index('"')+1:line.rindex('"')]
    if name != deaccent(name):
        line += f' "{deaccent(name)}"'
    if name.startswith("The "):
        line += f' "{deaccent(name)[4:]}"'
    writeString += f"{line}\n"

open("resources/countries_l_english.yml", "w", encoding="cp1252").write(writeString)
print("Written to file.")
