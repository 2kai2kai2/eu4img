from PIL import Image, ImageDraw, ImageFont
import os
import EU4Lib
srcFile = open(input(".EU4 file name: ").strip('"\n'), "r")
imgPolitical = Image.open(input(".png political mapmode name: ").strip('"\n'))
imgPlayers = Image.open(input(".png players mapmode name: ").strip('"\n'))

imgFinal = Image.open("src//finalTemplate.png")
mapFinal = imgPolitical.copy()

#Clears terminal
def clear():
    #print(chr(27) + "[2J")
    os.system('cls' if os.name == 'nt' else 'clear')

class Nation:
    def __init__(self, player):
        self.player = player
        self.tag = None
        self.development = None
        self.prestige = None
        self.stability = None
        #self.manpower = None
        #self.maxManpower = None
        self.army = 0.0
        self.navy = 0
        self.debt = 0
        self.treasury = 0.0
        self.totalIncome = 0.0
        self.totalExpense = 0.0
        self.scorePlace = None

#Start Data Selection
countries = []
playertags = []
dlc = []
GP = []
lines = srcFile.readlines()
brackets = []
playersEditReady = False #so that we can tell if we have scanned through all the players yet or not
print("Reading save file...")
for line in lines:
    #Separately:
    if playersEditReady == True and not brackets == ["players_countries={"]:
        #Data corrections
        playersEditReady = False #don't do it over and over again
        lastcommand = "null" #set this to "null" so it will go through the first loop
        print("Current players list:")
        for x in countries:
            print("\n"+x.tag+ ": "+ x.player)
        print("Do you want to make any changes?")
        print("Press enter without any entries to finish. Commands:")
        print("add TAG playername")
        print("remove TAG")
        print("")

        while lastcommand != "":
            lastcommand = input().strip("\n ")
            if lastcommand.startswith("add "):
                tag = lastcommand.partition(" ")[2].partition(" ")[0].strip("\t\n ")
                name = lastcommand.partition(" ")[2].partition(" ")[2].strip("\t\n ")
                if len(tag) != 3:
                    print("Tag length is incorrect. Canceling action.")
                    continue
                for x in countries:
                    if x.tag == tag: #Players are added later to the list as they join, so we remove all previous players
                        countries.remove(x)
                countries.append(Nation(name))
                countries[len(countries)-1].tag = tag.upper().strip("\t \n")
                playertags.append(tag.upper().strip("\t \n"))
                print("Added " + countries[len(countries)-1].tag + ": " + countries[len(countries)-1].player)
                
            elif lastcommand.startswith("remove "):
                tag = lastcommand.partition(" ")[2].strip("\t\n ")
                if len(tag) != 3:
                    print("Tag length is incorrect. Canceling action.")
                    continue
                for nat in countries:
                    if nat.tag.upper().strip("\t \n") == tag.upper().strip("\t \n"):
                        countries.remove(nat)
                        playertags.remove(nat.tag)
                        print("Removed " + tag.upper())
                        break
                    elif countries[len(countries)-1] == nat: #This means we are on the last one and elif- it's still not on the list.
                        print("Did not recognize " + tag.upper() + " as a played nation.")
    #Now the actual stuff

    if "{" in line:
        if line.strip("\n ").endswith("}"):
            continue
        else:
            brackets.append(line.rstrip("\n "))
        #print("{")
    elif "}" in line:
        brackets.pop()
        #print("}")
    #Get rid of long, useless sections
    #Possible to use sections:
    #Provinces
    elif len(brackets) < 0 and ("trade={" == brackets[1] or "provinces={" == brackets[0] or "rebel_faction={" == brackets[0] or (len(brackets) < 1 and "\tledger_data={" == brackets[1]) or "_area={" in brackets[0] or "change_price={" == brackets[0]):
        continue
    #Ignoring all but player / GP 
    #Possible to use: HRE / pope / crusade / china
    
    #elif len(brackets) < 0 and ("countries={" == brackets[0] and not (line.strip("\t={\n") in GP or line.strip("\t={\n") in playertags)):
        #print("HI" + line.strip("\t={\n"))
        #continue
    
    else:
        #This is where we do stuff
        #Get current gamedate
        if line.startswith("date=") and brackets == []:
            date = line.strip('date=\n')
        #Get save DLC (not sure if we use this...)
        elif brackets == ["dlc_enabled={"]:
            dlc.append(line.strip('\t"\n'))
        #Check if game is mp
        elif "multi_player=" in line and brackets == []:
            if "yes" in line:
                mp = True
            else:
                mp = False
        #Get player names and country tags
        elif brackets == ["players_countries={"]:
            playersEditReady = True
            #In the file, the format is like this:
            #players_countries={
            #   "playername"
            #   "SWE"
            #
            #Where "   " is a tab
            #This v adds a new country object and player name if there is none open.
            #print("Found a line in players_countries")
            if len(countries) == 0 or countries[len(countries)-1].tag is not None:
                print("Adding: ", line.strip('\t"\n'))
                countries.append(Nation(line.strip('\t"\n')))
            #Add country code to most recent country (which, because of ^ cannot have a tag)
            else:
                for x in countries:
                    if x.tag == line.strip('\t"\n'): #Players are added later to the list as they join, so we remove all previous players
                        countries.remove(x)
                countries[len(countries)-1].tag = line.strip('\t"\n')
                playertags.append(line.strip('\t"\n'))
                print("Country: ", line.strip('\t"\n'))
        #Get current age
        elif "current_age=" in line and brackets == []:
            age = line[12:].strip('"\n')
            print("\nAge: " + age)
        #Get top 8
        elif "country=" in line and brackets == ["great_powers={", "\toriginal={"]:
            if len(GP) < 8: #Make sure to not include leaving GPs
                GP.append(line.strip('\tcountry="\n'))
                print("Found GP: " + line.strip('\tcountry="\n'))
        #Get HRE emperor tag
        elif "\temperor=" in line and brackets == ["empire={"]:
            HRETag = line.strip('\temperor="\n')
            print("Found HRE Emperor: " + HRETag)
        #Get Celestial emperor tag
        elif "emperor=" in line and brackets == ["celestial_empire={"]:
            chinaTag = line.strip('\temperor="\n')
            print("Found Celestial Empire: " + chinaTag)
        #Get target of crusade ('---' if none)
        elif "crusade_target=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
            crusade = line.strip('\tcrusade_target="\n')
            print("Found crusade target: " + crusade)
        #Get papal controller
        elif "previous_controller=" in line and brackets == ["religion_instance_data={", "\tcatholic={", "\t\tpapacy={"]:
            continue
        #Country-specific for players
        #TODO: Not sure if this need optimization
        elif len(brackets) > 1 and brackets[0] == "countries={" and brackets[1].strip("\t={\n") in playertags:
            for x in countries:
                if x.tag in brackets[1]:
                    #Here we have all the stats for country x on the players list
                    if len(brackets) == 2:
                        if "raw_development=" in line:
                            x.development = round(float(line.strip("\traw_devlopmnt=\n")))
                        elif "score_place=" in line:
                            x.scorePlace = round(float(line.strip("\tscore_place=\n")))
                        elif "prestige=" in line:
                            x.prestige = round(float(line.strip("\tprestige=\n")))
                        elif "stability=" in line:
                            x.stability = round(float(line.strip("\tstability=\n")))
                        elif "treasury=" in line:
                            x.treasury = round(float(line.strip("\ttreasury=\n")))
                        #elif "\tmanpower=" in line:
                            #x.manpower = round(float(line.strip("\tmanpower=\n")))
                        #elif "max_manpower=" in line:
                            #x.maxManpower = round(float(line.strip("\tmax_manpower=\n")))
                        else: continue
                    elif len(brackets) == 3:
                        #Get size of each loan
                        if brackets[2] == "\t\tloan={" and "amount=" in line:
                            x.debt += round(float(line.strip("\tamount=\n")))
                        elif brackets[2] == "\t\tledger={" and "\tlastmonthincome=" in line:
                            x.totalIncome = round(float(line.strip("\tlastmonthincome=\n")), 2)
                        elif brackets[2] == "\t\tledger={" and "\tlastmonthexpense=" in line:
                            x.totalExpense = round(float(line.strip("\tlastmonthexpense=\n")), 2)
                    elif len(brackets) == 4:
                        #Add 1 to army size for each regiment
                        if brackets[2] == "\t\tarmy={" and "regiment={" in brackets[3] and "morale=" in line:
                            x.army = x.army + 1000
                        #Subtract damage done to units from army size
                        #This needs to be separate from ^ because for full regiments there is no "strength=" tag
                        elif brackets[2] == "\t\tarmy={" and "regiment={" in brackets[3] and "strength=" in line:
                            try:
                                x.army = round(x.army - 1000 + 1000*float(line.strip("\tstrength=\n")))
                            except ValueError:
                                continue
                        elif brackets[2] == "\t\tnavy={" and brackets[3] == "\t\t\tship={" and "\thome=" in line:
                            x.navy += 1

for x in countries: #Remove dead countries
    if x.development is None or x.development == None or x.development == 0:
        countries.remove(x)
#Sort Data:
countries.sort(key=lambda x: x.development, reverse=True)


print("Finished extracting save data.")
print("\nPlayer nations: "+ str(len(countries)))
print("Multiplayer:", mp)
print(date)
print(dlc)
for x in countries:
    print("\n"+x.tag+ ": "+ x.player)
    print("Army:", x.army)
    print("Navy:", x.navy)
    print("Dev:", x.development)
    print("Stab:", x.stability)
    print("Treasury:", x.treasury)
    print("Debt:", x.debt)
    #print("Manpower: "+ x.manpower)
    #print("Max Manpower: "+ x.maxManpower)
    print("Prestige:", x.prestige)

#End Data Selection
print("")
#Start Map Creation
#print("Showing political mapmode...")
#totalPixels = mapFinal.size[0] * mapFinal.size[1]
#mapFinal.show()
print("Preparing map editing...")
mapDraw = ImageDraw.Draw(mapFinal)
print("Drawing player country borders...")
for x in range(mapFinal.size[0]):
    for y in range(mapFinal.size[1]):
        #Get color for each pixel
        #In EU4 player mapmode screenshots,
        #Water: (68, 107, 163)
        #AI: (127, 127, 127)
        #Wasteland: (94, 94, 94)
        color = imgPlayers.getpixel((x, y))
        if color == (68, 107, 163) or color == (127, 127, 127) or color == (94, 94, 94):
            #print(round(100*x*y/totalPixels, 2), "% Done (", x, ", ", y, ")")
            continue
        else:
            #All pixels on the edge should be water and wasteland so not get past ^ if, although custom games may break this by not being real pixels
            #TODO: Make no borders for wasteland
            if color != imgPlayers.getpixel((x - 1, y - 1)) or color != imgPlayers.getpixel((x - 1, y)) or color != imgPlayers.getpixel((x - 1, y + 1)) or color != imgPlayers.getpixel((x, y - 1)) or color != imgPlayers.getpixel((x, y + 1)) or color != imgPlayers.getpixel((x + 1, y - 1)) or color != imgPlayers.getpixel((x + 1, y)) or color != imgPlayers.getpixel((x + 1, y + 1)):
                #Black for player borders
                mapDraw.point((x, y), (255-color[0], 255-color[1], 255-color[2]))
        #print(round(100*x*y/totalPixels, 2), "% Done (", x, ", ", y, ")")
print("Map editing done.")
#End Map Creation
#mapFinal.show()
#print("Saving map in 'map.png'...")
#mapFinal.save("map.png", "PNG")

#Start Final Img Creation
print("Copying map into final image...")
imgFinal.paste(mapFinal, (0, imgFinal.size[1]-mapFinal.size[1])) #Copy map into bottom of final image
print("Preparing final image editing...")
#The top has 5632x1119
fontsmall = ImageFont.load_default()
font = ImageFont.load_default()
fontbig = ImageFont.load_default()
try:
    fontsmall = ImageFont.truetype("FONT.TTF", 50)
    font = ImageFont.truetype("FONT.TTF", 100)
    fontbig = ImageFont.truetype("FONT.TTF", 180)
    print("Found font.")
except(FileNotFoundError, IOError):
    try:
        fontsmall = ImageFont.truetype("GARA.TTF", 50)
        font = ImageFont.truetype("GARA.TTF", 100)
        fontbig = ImageFont.truetype("GARA.TTF",180)
        print("Found EU4 font.")
    except(FileNotFoundError, IOError):
        fontsmall = ImageFont.load_default()
        font = ImageFont.load_default()
        fontbig = ImageFont.load_default()
        print("Could not find font. Using default.")

imgDraw = ImageDraw.Draw(imgFinal)
#================MULTIPLAYER================#
if mp == True:
    #Players section from (20,30) to (4710, 1100) half way is x=2345
    #So start with yborder = 38, yheight = 128 for each player row. x just make it half or maybe thirds depending on how it goes
    for nat in countries:
        natnum = countries.index(nat)
        x = 38 + 2335*int(natnum/8) #We have 2335 pixels to work with maximum for each player column
        y = 38 + 128*(natnum%8)
        if (natnum < 16):
            print(nat.tag + " adding")
            #x: Country
            imgFinal.paste(EU4Lib.flag(nat.tag), (x, y))
            #x+128: Player
            imgDraw.text((x+128, y), nat.player, (255, 255, 255), font)
            #x+760: Army
            imgFinal.paste(Image.open("src//army.png"), (x+760, y))
            armydisplay = str(round(nat.army/1000, 1))
            if armydisplay.endswith(".0") or ("." in armydisplay and len(armydisplay) > 4):
                armydisplay = armydisplay.partition(".")[0]
            armydisplay = armydisplay + "k"
            imgDraw.text((x+760+128, y), armydisplay, (255, 255, 255), font)
            #x+1100: Navy
            imgFinal.paste(Image.open("src//navy.png"), (x+1100, y))
            imgDraw.text((x+1100+128, y), str(nat.navy), (255, 255, 255), font)
            #x+1440: Development
            imgFinal.paste(Image.open("src//development.png"), (x+1440, y))
            imgDraw.text((x+1440+128, y), str(nat.development), (255, 255, 255), font)
            #x+1780: Income/Expense
            monthlyProfit = nat.totalIncome-nat.totalExpense
            imgIncome = Image.open("src//income.png")
            if monthlyProfit < 0:
                imgIncome = imgIncome.crop((128, 0, 255, 127))
                imgFinal.paste(imgIncome, (x+1780, y))
                imgDraw.text((x+1780+128, y), str(round(nat.totalIncome - nat.totalExpense)), (247, 16, 16), font)
            else:
                imgIncome = imgIncome.crop((0, 0, 127, 127))
                imgFinal.paste(imgIncome, (x+1780, y))
                imgDraw.text((x+1780+128, y), str(round(nat.totalIncome - nat.totalExpense)), (49, 190, 66), font)
            imgDraw.text((x+2130, y), "+" + str(round(nat.totalIncome, 2)), (49, 190, 66), fontsmall)
            imgDraw.text((x+2130, y+64), "-" + str(round(nat.totalExpense, 2)), (247, 16, 16), fontsmall)
            #navy_strength
            #manpower
            #max_manpower
            #max_sailors
        else:
            print(nat.tag + " does not fit!")
#================SINGLEPLAYER================#
elif mp == False:
    pass #TODO
#================END  SECTION================#
#Date
imgDraw.text((4800,85), date, (255, 255, 255), fontbig)


print("Final image editing done.")
imgFinal.show()
print("Saving final image...")
imgFinal.save("final.png", "PNG")
#End Final Img Creation

end = input("Done!") #Press enter to end
