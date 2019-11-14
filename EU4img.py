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
    print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")

class Nation:
    #def __init__(self, player, tag):
    def __init__(self, tag):
        #self.player = player
        self.tag = tag
        self.capitalID = 0

#Get reservations
countries = []
#Separately:
lastcommand = "null" #set this to "null" so it will go through the first loop

while lastcommand != "":
    print("Current players list:")
    if countries.__len__ == 0:
        print("EMPTY")
    else:
        for x in countries:
            #print("\n"+x.tag+ ": "+ x.player)
            print(x.tag)
    print("Do you want to make any changes?")
    print("Press enter without any entries to finish. Commands:")
    #print("add TAG playername")
    print("add COUNTRY/TAG")
    print("remove COUNTRY/TAG")
    print("")

    lastcommand = input().strip("\n ")
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
        print("Added " + tag)
            
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
