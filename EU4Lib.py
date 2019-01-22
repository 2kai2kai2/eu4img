#This will need to be updated. Currently for 1.28
from PIL import Image, ImageDraw

def province():
    pass
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
