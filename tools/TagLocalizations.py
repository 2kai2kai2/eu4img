from typing import List, Optional, Union, Tuple
from os import path, listdir
import unicodedata

language = "english"
directory = input("Directory: ")

# Fix directory when dragging file from explorer into VS code terminal
if directory.startswith("&"):
	directory = directory.strip("& '")

# Check if directory exists
if not path.exists(directory):
	print("Path not found.")
	quit()
else:
	print("Path found. Searching...")

# Find the files we need
allFiles = listdir(directory)
specFiles: List[str] = [f for f in allFiles if path.isfile(directory+"\\"+f) and language in f]

# Compile all the lines from all the files
allLines: List[str] = []

for f in specFiles:
	fileObj = open(directory + "\\" + f, "r", encoding="utf8")
	allLines.extend(fileObj.readlines())
	fileObj.close()
	del(fileObj)

# Find only the ones that are nation tags
tagLines: List[str] = [line for line in allLines if len(line) > 5 and line[0] == " " and line[4] == ":" and line[:5] == line[:5].upper()]
tagLines.sort()

def deaccent(string: str) -> str:
	return str(unicodedata.normalize('NFKD', string)).encode('ASCII', 'ignore').decode('ASCII')

for line in tagLines:
	name = line[line.index('"')+1:-1]
	if name != deaccent(name):
		line += ' "' + deaccent(name) + '"'
	if name.startswith("The "):
		line += ' "' + deaccent(name)[4:] + '"'
	print(line)
