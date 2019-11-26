from PIL import Image, ImageDraw, ImageFont
import os
import EU4Lib
srcFile = open("src\\save_1444.eu4", "r")
imgPolitical = Image.open("src//map_1444.png")

#imgFinal = Image.open("src//finalTemplate.png")
mapFinal = imgPolitical.copy()

#Clears terminal
def clear():
    #print(chr(27) + "[2J")
    #os.system('cls' if os.name == 'nt' else 'clear')
    print("\n" * 1000)

class Nation:
    #def __init__(self, player, tag):
    def __init__(self, tag):
        #self.player = player
        self.tag = tag
        self.capitalID = 0

class Reserve:
    def __init__(self, name):
        self.tags = [] # list of str
        self.name = name #str
    def add(self, tag):
        self.tags.append(tag)
    def remove(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
    def getSaveText(self):
        string = self.name + "\n"
        for tag in self.tags:
            string += "\t" + tag + "\n"
        return string

def getSavedReserves():
    reserves = []
    f = open("savedreservationgames.txt", "r")
    currentReserve = None
    while True:
        line = f.readline()
        if line == "":
            if currentReserve is not None:
                reserves.append(currentReserve)
            return reserves
        elif line.startswith("\t") and len(line.strip("\n\t ")) == 3:
            currentReserve.add(line.strip("\n\t "))
        elif not line.startswith("\t") and not line.startswith(" ") and not line == "\n":
            if currentReserve is not None:
                reserves.append(currentReserve)
            currentReserve = Reserve(line.strip("\n\t "))
        else:
            pass # Uh this shouldn't happen unless the file is formatted incorrectly.
    f.close()
    return reserves



#Get reservations
countries = []

def save(name):
    res = Reserve(name)
    for tag in countries:
        res.add(tag.tag)
    if not os.path.isfile("savedreservationgames.txt"):
        f = open("savedreservationgames.txt", "w")
        f.write(res.getSaveText())
        f.close()
    else:
        reservations = getSavedReserves()
        for r in reservations:
            if r.name == res.name:
                reservations.remove(r)
        reservations.append(res)
        
        text = ""
        for r in reservations:
            text += r.getSaveText()
        f = open("savedreservationgames.txt", "w")
        f.write(text)
        f.close()

#Separately:
lastcommand = "null" #set this to "null" so it will go through the first loop

while lastcommand != "":
    print("------------------------------------------------------------------------------------------")
    print("Current players list:")
    if len(countries) == 0:
        print("EMPTY")
    else:
        for x in countries:
            #print("\n"+x.tag+ ": "+ x.player)
            print(x.tag)
    print("Do you want to make any changes?")
    print("------------------------------------------------------------------------------------------")
    print("Commands:")
    #print("add TAG playername")
    print("add COUNTRY/TAG        | Adds the given nation to the reserved list.")
    print("remove COUNTRY/TAG     | Removes the given nation from the reserved list.")
    print("load GAMENAME          | Loads a saved reservation list by name.")
    print("save GAMENAME          | Saves a reservation list by name. (WARNING: overrides same name)")
    print("list [GAMENAME]        | If a name is included, shows all tags in the saved list.")
    print("                       | Otherwise, shows all saved list names.")
    print("Press enter without any entries to finish. ")

    lastcommand = input().strip("\n ")
    clear()
    print("> " + lastcommand)
    if lastcommand.startswith("add "):
        tag = EU4Lib.country(lastcommand.partition(" ")[2].strip("\t\n "))
        #name = lastcommand.partition(" ")[2].partition(" ")[2].strip("\t\n ")
        if tag == None:
            print("Country not recognized. Please check spelling.")
            continue
        for x in countries:
            if x.tag == tag: #Players are added later to the list as they join, so we remove all previous players
                countries.remove(x)
        #countries.append(Nation(name, tag))
        countries.append(Nation(tag))
        countries[len(countries)-1].tag = tag.upper().strip("\t \n")
        #print("Added " + countries[len(countries)-1].tag + ": " + countries[len(countries)-1].player)
        print("Added " + tag.upper())
            
    elif lastcommand.startswith("remove "):
        tag = EU4Lib.country(lastcommand.partition(" ")[2].strip("\t\n "))
        if tag == None:
            print("Country not recognized. Please check spelling.")
            continue
        for nat in countries:
            if nat.tag.upper().strip("\t \n") == tag.upper().strip("\t \n"):
                countries.remove(nat)
                print("Removed " + tag.upper())
                break
            elif countries[len(countries)-1] == nat: #This means we are on the last one and elif- it's still not on the list.
                print("Did not recognize " + lastcommand + " as a reserved nation.")
    
    elif lastcommand.startswith("save "):
        save(lastcommand.partition(" ")[2].strip("\t\n "))
        print("Saved as " + lastcommand.partition(" ")[2].strip("\t\n "))

    elif lastcommand.startswith("load "):
        if not os.path.exists("savedreservationgames.txt"):
            print("No saved games.")
        else:
            reserves = getSavedReserves()
            if len(reserves) == 0:
                print("No saved games.")
            else:
                resName = lastcommand.partition(" ")[2].strip("\t\n ")
                for res in reserves:
                    if res.name == resName:
                        countries = []
                        for tag in res.tags:
                            countries.append(Nation(tag))
                        print("Loaded " + resName + ".")
                        continue
    
    elif lastcommand.strip("\t\n ") == "list": # list with no arguments
        if not os.path.exists("savedreservationgames.txt"):
            print("No saved games.")
        else:
            reserves = getSavedReserves()
            if len(reserves) == 0:
                print("No saved games.")
            else:
                print("Reservation lists:")
                for res in reserves:
                    print(res.name + " (" + str(len(res.tags)) + ")")
    elif lastcommand.startswith("list "):
        if not os.path.exists("savedreservationgames.txt"):
            print("No saved games.")
        else:
            reserves = getSavedReserves()
            if len(reserves) == 0:
                print("No saved games.")
            else:
                resName = lastcommand.partition(" ")[2].strip("\t\n ")
                found = False
                for res in reserves:
                    if res.name == resName:
                        print("Reservations:")
                        for tag in res.tags:
                            print(tag)
                        found = True
                        break
                if not found:
                    print("That reservation list does not exist.")

#Start Data Selection
lines = srcFile.readlines()
brackets = []
print("Reading default data...")
linenum = 0
for line in lines:
    linenum+=1
    
    if "{" in line:
        if line.count("{") == line.count("}"):
            continue
        elif line.count("}") == 0 and line.count("{") == 1:
            brackets.append(line.rstrip("\n "))
        elif line.count("}") == 0 and line.count("{") > 1:
            for x in range(line.count("{")):
                brackets.append("{") #TODO: fix this so it has more
        else:
            print("Unexpected brackets at line #" + str(linenum) + ": " + line)
        #print("{")
    elif "}" in line:
        try:
            brackets.pop()
        except IndexError:
            print("No brackets to delete.")
            print("Line", linenum, ":", line)
        #print("}")
    #Get rid of long, useless sections
    elif len(brackets) < 0 and ("trade={" == brackets[1] or "provinces={" == brackets[0] or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
        continue
    elif len(brackets) > 1 and brackets[0] == "countries={":
        for x in countries:
            if x.tag in brackets[1]:
                #Here we have all the stats for country x on the players list
                if len(brackets) == 2 and "capital=" in line and not "original_capital=" in line and not "fixed_capital=" in line:
                        x.capitalID = int(line.strip("\tcapitl=\n"))

print("Finished extracting game data.")
print("\nPlayer nations: "+ str(len(countries)))
for x in countries:
    #print("\n"+x.tag+ ": "+ x.player)
    print(x.tag)

#End Data Selection
print("")
#Start Map Creation
print("Locating reserved nations...")
imgX = Image.open("src//xIcon.png")
for x in countries:
    loc = EU4Lib.province(x.capitalID)
    mapFinal.paste(imgX, (int(loc[0]-imgX.size[0]/2), int(loc[1]-imgX.size[1]/2)), imgX)
    # I hope this doesn't break if a capital is too close to the edge


print("Map editing done.")
#End Map Creation
mapFinal.show()
print("Close image editor to save file... (Unfortunately this is necessary)")
mapFinal.save("final.png", "PNG")
#End Final Img Creation

end = input("Done!") #Press enter to end
