#This will need to be updated. Currently for 1.28
from PIL import Image, ImageDraw

def country(text):
    srcFile = open("src\\countries_l_english.yml")
    lines = srcFile.readlines()
    srcFile.close
    if len(text) == 3:
        for line in lines:
            if line[1:4] == text.upper():
                return text
    # text is not just a tag
    for line in lines:
       if ('"' + text.lower() + '"') in line.lower():
           return line[1:4]
    # text is unknown
    return None

def tagToName(tag):
    srcFile = open("src\\countries_l_english.yml")
    lines = srcFile.readlines()
    srcFile.close
    if len(tag) == 3:
        for line in lines:
            if line[1:4] == tag.upper():
                return line[8:].split("\"", 1)[0].strip("\" \t\n")
    return None

def province(id):
    srcFile = open("src\\positions.txt", "r")
    lines = srcFile.readlines()
    beyond = 0
    for line in lines:
        if beyond == 2:
            vals = line.strip("\t\n ").split(" ")
            return (float(vals[0]), 2048-float(vals[1]))
        if beyond == 1:
            beyond = 2
            continue
        if line.strip("\n ") == (str(id)+"={"):
            beyond = 1
            continue
        
def flag(tag):
    index = open("src\\flagfiles.txt", "r")
    line = index.read()
    a = line.partition(tag) #Separate into a 3-tuple around tag
    flagnum = a[0].count(".tga") #Get image number starting at 0
    #Each flag file is 16x16 so a total of 256 each
    #Each flag icon is 128x128 pixels
    flagfile = Image.open("src\\flagfiles_" + str(int(flagnum/256)) + ".tga")
    x = 128*((flagnum%256)%16)
    y = 128*int((flagnum%256)/16)
    flagimg = flagfile.crop((x, y, x+127, y+127))
    flagimg.load()
    return flagimg