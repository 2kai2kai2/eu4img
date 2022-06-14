from os import path, listdir
from typing import List
import shutil
import re
import TagLocalizations


destination_dir = path.join("resources", input("Target name: ").strip('" ?'))

steam_dir = input("Steam files directory: ").strip('" ?')
if not path.exists(steam_dir):
    print("Invalid steam files directory.")
    quit()

docs_dir = input("EU4 documents directory: ").strip('" ?')
if not path.exists(docs_dir):
    print("Invalid EU4 documents files directory.")
    quit()

# Europa Universalis IV/maps/
steam_map_files: List[str] = ["continent.txt", "superregion.txt", "region.txt", "area.txt",
                              "definition.csv", "provinces.bmp", "default.map", "positions.txt", "climate.txt"]
for file in steam_map_files:
    shutil.copy(path.join(steam_dir, "map", file),
                path.join(destination_dir, file))

# Europa Universalis IV/localisation/
allLines = TagLocalizations.loadLanguage(
    "english", path.join(steam_dir, "localisation"))
tagLines = TagLocalizations.filterTags(allLines)
TagLocalizations.writeOutput(tagLines, path.join(
    destination_dir, "countries_l_english.yml"))


# Europa Universalis IV/common/colonial_regions/00_colonial_regions.txt
shutil.copy(path.join(steam_dir, "common", "colonial_regions", "00_colonial_regions.txt"),
            path.join(destination_dir, "00_colonial_regions.txt"))

# Documents/Paradox Interactive/Europa Universalis IV/gfx/flags/
flag_files: List[str] = ["flagfiles.txt"]
flag_tga_regex = re.compile("\Aflagfiles_\d.tga\Z")
flag_files.extend(filter(flag_tga_regex.match, listdir(
    path.join(docs_dir, "gfx", "flags"))))
for file in flag_files:
    shutil.copy(path.join(docs_dir, "gfx", "flags", file),
                path.join(destination_dir, file))
