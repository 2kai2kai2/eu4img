/*
<%
import pybind11
import sysconfig
setup_pybind11(cfg)
cfg['include_dirs'] = [pybind11.get_include(), sysconfig.get_path("include")]
%>
*/

#include <pybind11/operators.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <fstream>
#include <list>
#include <map>
#include <set>
#include <string>
#include <tuple>

#include "EU4Date.h"

namespace py = pybind11;

std::map<std::tuple<uint8_t, uint8_t, uint8_t>, std::list<std::tuple<size_t, size_t>>> drawBorders(std::map<std::tuple<uint8_t, uint8_t, uint8_t>, std::tuple<uint8_t, uint8_t, uint8_t>> playerColors, std::string pixels, size_t width, size_t height) {
    std::map<std::tuple<uint8_t, uint8_t, uint8_t>, std::list<std::tuple<size_t, size_t>>> out;
    // Go through and find borders
    for (size_t i = width + 1; i < width * height - width - 1; ++i) {
        std::tuple<uint8_t, uint8_t, uint8_t> pcols[9];
        // Get the colors
        for (char dy = 0; dy <= 2; ++dy) {
            for (char dx = 0; dx <= 2; ++dx) {
                size_t dIndex = 3 * (i + width * (dy - 1) + (dx - 1));
                std::tuple<uint8_t, uint8_t, uint8_t> rawColor = std::tuple<uint8_t, uint8_t, uint8_t>(pixels[dIndex], pixels[dIndex + 1], pixels[dIndex + 2]);
                if (playerColors.count(rawColor) > 0) {
                    // Add the player color
                    pcols[dy * 3 + dx] = playerColors[rawColor];
                } else {
                    // It's not on the player list so just add (0, 0, 0)
                    pcols[dy * 3 + dx] = std::tuple<uint8_t, uint8_t, uint8_t>(0, 0, 0);
                }
            }
        }
        // Check if any are different
        if (pcols[0] != pcols[1] || pcols[1] != pcols[2] || pcols[2] != pcols[3] || pcols[3] != pcols[4] || pcols[4] != pcols[5] || pcols[5] != pcols[6] || pcols[6] != pcols[7] || pcols[7] != pcols[8]) {
            if (out.count(pcols[4]) == 0) {
                // We need to create a new entry for this playerColor
                out[pcols[4]] = std::list<std::tuple<size_t, size_t>>();
            }
            out[pcols[4]].push_back(std::tuple<size_t, size_t>(i % width, i / width));
        }
    }
    return out;
};

/**
 * Reads the next 4 bytes and returns them as an int.
 * This will move the stream.
 */
int readifstreamint(std::ifstream &stream) {
    char bytes[4];
    stream.read(bytes, 4);
    int data;
    std::memcpy(&data, bytes, 4);
    return data;
}

/**
 * Reads the next 2 bytes and returns them as an int. This means 12 34 will become 00 00 12 34.
 * This will move the stream.
 */
int readifstream2b(std::ifstream &stream) {
    char bytes[2];
    stream.read(bytes, 2);
    return (bytes[1] << 8) | bytes[0];
}

std::string loadProvinceMap() {
    std::ifstream mapfile("resources/provinces.bmp", std::ios_base::binary | std::ios_base::in);

    /* ===== Bitmap File Header ===== */
    /*  ---  offset 0; 14 bytes  ---  */

    // Verify first two bytes for bitmap file are BM
    // offset 0; length 2
    char bm[2];
    mapfile.read(bm, 2);
    if (bm[0] != 'B' || bm[1] != 'M') {
        Py_FatalError("provinces.bmp is not a valid BM bitmap file. First two bytes must be 'BM'");
        return "";
    }

    // byte size of BMP file
    // offset 2; length 4
    int filesize = readifstreamint(mapfile);

    // reserved for image editor applications
    // offset 6; length 2*2
    mapfile.ignore(4);

    // pixel array start address
    // offset 10; length 4
    int arrayaddress = readifstreamint(mapfile);

    /* ===== DIB Header ===== */
    /*  ---  offset 14  ---  */
    // DIB header size. I think we use this to determine which type of header it is.
    int DIBlength = readifstreamint(mapfile);

    // The map is using a 40-byte DIB header, which is the type BITMAPINFOHEADER
    if (DIBlength != 40) {
        Py_FatalError("We only support BITMAPINFOHEADER DIB header for bitmap images.");
        return "";
    }

    #pragma GCC diagnostic push
    #pragma GCC diagnostic ignored "-Wunused-parameter"

    // width (signed int)
    // offset 18; length 4
    int width = readifstreamint(mapfile);
    // height (signed int)
    // offset 22; length 4
    int height = readifstreamint(mapfile);

    // number of color planes (apparently always 1???)
    // offset 26; length 2
    int colorplanes = readifstream2b(mapfile);

    // color depth (bits per pixel; typically: 1=B/W, 8=grayscale 0-255, 24=RGB 0-255, 32=RGBA 0-255)
    // offset 28; length 2
    int colordepth = readifstream2b(mapfile);

    // compression (refer to table)
    // offset 30; length 4
    int compression = readifstreamint(mapfile);

    // image size (raw data; 0 for some compression)
    // offset 34; length 4
    int imgsize = readifstreamint(mapfile);

    // horizontal resolution (pixels/meter; signed int)
    // offset 38; length 4
    int horizontalres = readifstreamint(mapfile);

    // vertical resolution (pixels/meter; signed int)
    // offset 42; length 4
    int verticalres = readifstreamint(mapfile);

    // color palette size (0 means 2^n)
    // offset 46; length 4
    int palettesize = readifstreamint(mapfile);

    // number of important colors (0 if all important; generally ignored)
    // offset 50; length 4
    int importantcolors = readifstreamint(mapfile);
    
    #pragma GCC diagnostic pop

    // Well most of this will be useless, but whatever.
    // Verify data
    assert(width == 5632 && height == 2048 /*Loaded image must be the correct size*/);
    assert(colorplanes == 1 /*Apparently all valid bitmap files have 1 color plane*/);
    assert(colordepth == 24 /*Provinces map must have 24 bit color depth (3 bytes)*/);
    assert(compression == 0 /*Provinces map is uncompressed and I didn't write decompression code.*/);

    /* ===== Bit masks ===== */
    /* Only present with BITMAPINFOHEADER compression BI_BITFIELDS (3) or BI_ALPHABITFIELDS (6) */
    /* length 12/16 */
    // BITMAPV2INFOHEADER and BITMAPV3INFOHEADER seem to be similar???
    if (compression == 3) {
        mapfile.ignore(12);
    } else if (compression == 6) {
        mapfile.ignore(16);
    }

    /* ===== Color table ===== */
    // ???

    /* ===== Pixel Array ===== */
    /*  header-defined offset  */
    // Jump to our array address, skipping any potential gaps an other stuff in between.
    mapfile.seekg(arrayaddress);

    // Read data
    const size_t pixlength = 5632 * 2048;
    const size_t bytelength = pixlength * 3;
    char *pdt = new char[bytelength];
    mapfile.read(pdt, bytelength);
    // Correct color from little endian
    char temp;
    for (size_t pixindex = 0; pixindex < bytelength; pixindex += 3) {
        temp = pdt[pixindex];
        pdt[pixindex] = pdt[pixindex + 2];
        pdt[pixindex + 2] = temp;
    }
    // Move to string and finalize
    std::string imgdata(pdt, bytelength);
    delete[] pdt;
    return imgdata;
};

py::bytes pyProvMap() {
    return loadProvinceMap();
}

static const auto maxGet = std::numeric_limits<std::streamsize>::max();

void skipToLineEnd(std::ifstream &file) {
    char skip;
    while (file.get(skip)) {
        if (skip == '\n' || skip == file.eofbit) {
            break;
        }
    }
}

typedef uint32_t intColor;

inline intColor packColor(const uint8_t red, const uint8_t green, uint8_t blue) {
    return (blue << 16) | (green << 8) | red;
}
inline intColor packColor(const char color[3]) {
    return packColor(color[0], color[1], color[2]);
}
inline intColor packColor(const std::tuple<uint8_t, uint8_t, uint8_t> &color) {
    return packColor(std::get<0>(color), std::get<1>(color), std::get<2>(color));
}

inline bool isColor(const intColor *color, const char check[3]) {
    const unsigned char *pointer = reinterpret_cast<const unsigned char *>(color);
    return !std::memcmp(pointer + 1, check, 3);
}

inline void putColor(const intColor *color, char *location) {
    const unsigned char *pointer = reinterpret_cast<const unsigned char *>(color);
    std::memcpy(location, pointer, 3);
}

std::map<uint32_t, intColor> loadMapDef() {
    std::map<uint32_t, intColor> out;
    std::ifstream file("resources/definition.csv");
    // skip first line: province;red;green;blue;name;x
    file.ignore(maxGet, '\n');

    char tempstr[16]; // 16 characters should be enough for the province IDs, and for the 0-255 colors. DO NOT USE FOR OTHER CSV FILES
    while (!file.eof()) {
        // This loop is only going to go once per line.

        file.get(tempstr, maxGet, ';');
        uint32_t provinceID = std::stoi(tempstr);
        file.ignore(); // Skip the ';'

        file.get(tempstr, maxGet, ';');
        uint8_t red = std::stoi(tempstr);
        file.ignore(); // Skip the ';'

        file.get(tempstr, maxGet, ';');
        uint8_t green = std::stoi(tempstr);
        file.ignore(); // Skip the ';'

        file.get(tempstr, maxGet, ';');
        uint8_t blue = std::stoi(tempstr);
        file.ignore(); // Skip the ';'
        out[provinceID] = packColor(red, green, blue);

        skipToLineEnd(file);
    }

    return out;
}

std::vector<uint32_t> loadIntList(std::ifstream &file, const std::set<std::string> &keys) {
    std::vector<uint32_t> out;
    std::string key = "";
    char temp;
    while (!file.eof()) {
        file.get(temp);
        if (temp == '=' || (temp == ' ' && file.peek() == '=')) {
            // Next we have the value.
            // Go through, and if \n comes before { it is just a value, but if { comes first then we can start searching.
            while (temp != '{' && temp != '\n' && temp != file.eofbit) {
                file.get(temp);
            }
            // Now we have either reached the end of the line or an open bracket.
            // If it is an { we get the data inside, otherwise we just let it go.
            if (temp == '{') {
                // Start off with the first item after the {
                std::vector<std::string> items;
                std::string current = "";
                file.get(temp);
                while (temp != '}' && temp != file.eofbit) {
                    if (temp == '#') { // If it's a comment, save any current item and skip to next line
                        if (current.size() != 0) {
                            items.push_back(current);
                            current = "";
                        }
                        skipToLineEnd(file);
                    } else if (std::isspace(temp)) { // If it's a space, save any current item and prepare for the next one
                        if (current.size() != 0) {
                            items.push_back(current);
                            current = "";
                        }
                    } else { // Otherwise, we are just adding to the current item
                        current.push_back(temp);
                    }
                    // We do this at the end so we can start by checking whether the list has ended
                    file.get(temp);
                }
                // Now we have a full list of items. Check that the key is correct and if so, convert to int and add.
                if (keys.find(key) != keys.end()) {
                    for (size_t i = 0; i < items.size(); ++i) {
                        out.push_back(std::stoi(items[i]));
                    }
                }
            }
            key = "";
        } else if (temp == '#') {
            // We have a comment. Skip to next line.
            skipToLineEnd(file);
            key = "";
        } else if (temp == '\n' || temp == file.eofbit) {
            // New line without reaching an =. Ignore key.
            key = "";
        } else {
            // Just another character.
            key.push_back(temp);
        }
    }
    return out;
}

/**
 * Loads data from resources/default.map to get the IDs of all lake and sea provinces.
 * @returns Sorted vector of all lake and sea province IDs.
 */
std::vector<uint32_t> loadWaterProvinces() {
    std::ifstream file("resources/default.map");
    std::vector<uint32_t> waterProvs = loadIntList(file, std::set<std::string>({"sea_starts", "lakes"}));

    std::sort(waterProvs.begin(), waterProvs.end());
    return waterProvs;
}

/**
 * Loads data from resources/climate.txt to get the IDs of all wasteland provinces.
 * @returns Sorted vector of all impassable province IDs.
 */
std::vector<uint32_t> loadWastelandProvinces() {
    std::ifstream file("resources/climate.txt");
    std::vector<uint32_t> wasteProvs = loadIntList(file, std::set<std::string>({"impassable"}));

    std::sort(wasteProvs.begin(), wasteProvs.end());
    return wasteProvs;
}

template <class K, class V>
std::map<V, K> flipMap(const std::map<K, V> &original) {
    std::map<V, K> flipped;
    for (auto iter = original.begin(); iter != original.end(); ++iter) {
        flipped[iter->second] = iter->first;
    }
    return flipped;
}

std::map<uint32_t, std::set<uint32_t>> generateLandAdjacency(const std::string &mapimg, const std::map<uint32_t, intColor> &provinceColors, const std::vector<uint32_t> &ignoreWater, size_t width = 5632, size_t height = 2048) {
    std::map<intColor, uint32_t> colorProvs = flipMap(provinceColors);
    std::map<uint32_t, std::set<uint32_t>> adjacencies;

    // Get the province colors so we can easily check that before getting the province ID.
    std::vector<intColor> waterProvs(ignoreWater.size());
    for (size_t i = 0; i < ignoreWater.size(); ++i) {
        waterProvs[i] = provinceColors.at(ignoreWater[i]);
    }
    std::sort(waterProvs.begin(), waterProvs.end());
    // Iterate through pixels
    for (size_t row = 0; row < height; ++row) {
        for (size_t col = 0; col < width; ++col) {
            size_t index = (row * width + col) * 3;
            intColor pix = packColor(mapimg.data() + index);
            // Check to skip water
            if (std::binary_search(waterProvs.begin(), waterProvs.end(), pix)) {
                continue;
            }
            // Now look at adjecent pixels. We only need to look at the next x and next y because the previous will have already been checked.
            for (uint8_t offset = 0; offset <= 1; ++offset) {
                // This is kinda like a mini sin/cos function, finding -1 and +1 for each
                size_t orow = row + (offset == 1);
                size_t ocol = col + (offset == 0);
                if (orow >= height || ocol >= width) {
                    continue;
                }
                size_t oindex = (orow * width + ocol) * 3;
                intColor opix = packColor(mapimg.data() + oindex);
                // If they are different colors, get the province
                if (pix != opix) {
                    // Check to skip water
                    if (std::binary_search(waterProvs.begin(), waterProvs.end(), opix)) {
                        continue;
                    }
                    uint32_t provinceID = colorProvs.at(pix);
                    uint32_t oprov = colorProvs.at(opix);
                    // So we have a different adjacent land province, only reversing if the forward direction worked.
                    if (adjacencies[provinceID].insert(oprov).second)
                        adjacencies[oprov].insert(provinceID);
                }
            }
        }
    }
    return adjacencies;
}

std::map<uint32_t, std::set<uint32_t>> pyGenerateLandAdjacency() {
    return generateLandAdjacency(loadProvinceMap(), loadMapDef(), loadWaterProvinces());
}

std::string drawMap(const std::map<std::string, std::tuple<uint8_t, uint8_t, uint8_t>> &tagColors, const std::map<uint32_t, std::string> &provinceOwners) {
    // First, construct a more direct map of province color to tag color

    /*
    [ loadMapDef() ]    [provinceOwners]    [  tagColors  ]    | [   colorMap   ]
    [ province id  ] -> [     tag      ] -> [country color] -v | [prov map color]
    [prov map color] ----------------------------------------^ | [ nation color ]

    [ loadMapDef() ]    [  waterProvs  ]    [             ]    | [   colorMap   ]
    [ province id  ] -> [     bool     ] -> [ water color ] -v | [prov map color]
    [prov map color] ----------------------------------------^ | [ nation color ]
    */

    // Store the intColor version of the tag colros here
    std::map<std::string, intColor> pTagColors;
    for (auto iter = tagColors.begin(); iter != tagColors.end(); ++iter) {
        pTagColors[iter->first] = packColor(iter->second);
    }

    static const intColor waterColor = packColor(68, 107, 163);
    static const intColor unclaimedColor = packColor(94, 94, 94);
    static const intColor wastelandColor = packColor(150, 150, 150);

    const std::string provinceMap = loadProvinceMap();
    std::map<intColor, intColor> colorMap;

    {
        // A scope so that the mapDef will get freed
        const std::map<uint32_t, intColor> mapDef = loadMapDef();
        const std::vector<uint32_t> waterProvs = loadWaterProvinces();
        const std::vector<uint32_t> wasteProvs = loadWastelandProvinces();
        const std::map<uint32_t, std::set<uint32_t>> landAdjacency = generateLandAdjacency(provinceMap, mapDef, waterProvs);
        for (auto iter = mapDef.begin(); iter != mapDef.end(); ++iter) {

            if (std::binary_search(waterProvs.begin(), waterProvs.end(), iter->first)) {
                colorMap[iter->second] = waterColor;
            } else if (std::binary_search(wasteProvs.begin(), wasteProvs.end(), iter->first)) {
                // It's a wasteland province.
                // Check the neighbors to figure out if there is a tag with >50% to give them the wasteland on the map

                auto neighbors = landAdjacency.find(iter->first);
                if (neighbors == landAdjacency.end()) {
                    // This is if there are no neighbors
                    colorMap[iter->second] = unclaimedColor;
                    continue;
                }
                // Store the number of adjacent provinces each tag owns
                std::map<std::string, size_t> tagAdjs;

                for (auto adjit = neighbors->second.begin(); adjit != neighbors->second.end(); ++adjit) {
                    // Get an iterator to the owner of the province so we can search only once while still being able to check if it is unclaimed before adding
                    auto adjowner = provinceOwners.find(*adjit);
                    // Check if it is unclaimed
                    if (adjowner == provinceOwners.end()) {
                        continue;
                    }
                    // Otherwise increment the owner's province count
                    ++tagAdjs[adjowner->second];
                }

                // Go through and see if there is a tag with more than half
                // default
                colorMap[iter->second] = unclaimedColor;

                for (auto tagit = tagAdjs.begin(); tagit != tagAdjs.end(); ++tagit) {
                    if (2 * tagit->second > neighbors->second.size()) {
                        colorMap[iter->second] = pTagColors.at(tagit->first);
                        break;
                    }
                }
            } else {
                auto owner = provinceOwners.find(iter->first);
                if (owner != provinceOwners.end()) {
                    auto color = pTagColors.find(owner->second);
                    if (color != pTagColors.end()) {
                        colorMap[iter->second] = color->second;
                        continue;
                    } else {
                        // Something went wrong. Return black.
                        colorMap[iter->second] = 0;
                    }
                } else {
                    // The province is probably uncolonized.
                    colorMap[iter->second] = wastelandColor;
                }
            }
        }
    }

    static const size_t pixelCount = 5632 * 2048;
    char *img = new char[pixelCount * 3];

    for (size_t i = 0; i < pixelCount; ++i) {
        intColor *tempPixColor = &colorMap[packColor(provinceMap.data() + i * 3)];
        putColor(tempPixColor, img + i * 3);
    }
    std::string imgStr(img, pixelCount * 3);
    delete[] img;
    return imgStr;
}

py::bytes pyDrawMap(const std::map<std::string, std::tuple<uint8_t, uint8_t, uint8_t>> &tagColors, const std::map<uint32_t, std::string> &provinceOwners) {
    return drawMap(tagColors, provinceOwners);
}

std::pair<float, float> provinceLocation(const size_t &id) {
    std::string idstr = std::to_string(id);
    std::ifstream file;
    file.open("resources/positions.txt");

    std::string line;
    while (std::getline(file, line)) {
        // While items such as "11={" will catch "1={", that is fine because the smaller number will come first, meaning the larger number should not be reached.
        if (line.find(idstr + "={") != std::string::npos) {

            std::getline(file, line); // position={
            std::getline(file, line); // Line with position data. We want the first two.

            std::pair<float, float> out;
            bool second = false;
            size_t start = std::string::npos;

            // Go through each character to get the first two numbers
            for (size_t i = 0; i < line.size(); ++i) {
                if (start == std::string::npos && !std::isspace(line[i])) {
                    // The first character of the number
                    start = i;
                } else if (start != std::string::npos && std::isspace(line[i])) {
                    // The first whitespace after the number
                    if (second) {
                        out.second = std::stof(line.substr(start, i - start));
                        return out;
                    } else {
                        out.first = std::stof(line.substr(start, i - start));
                        start = std::string::npos;
                        second = true;
                    }
                }
            }
        }
    }
    return std::pair<float, float>(-1.0f, -1.0f);
}

PYBIND11_MODULE(EU4cpplib, m) {
    m.doc() = "Libraries for eu4img written in C++ to improve speed and resource-consumption.";

    py::class_<EU4Date>(m, "EU4Date")
        .def(py::init<const std::string &>(), py::arg("text"))
        .def_readwrite("year", &EU4Date::year)
        .def_readwrite("month", &EU4Date::month)
        .def_readwrite("day", &EU4Date::day)
        .def("__repr__", &EU4Date::toString)
        .def("fancyStr", &EU4Date::fancyString)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def(py::self > py::self)
        .def(py::self <= py::self)
        .def(py::self >= py::self)
        .def("isValidDate", &EU4Date::isValidDate)
        .def("isEU4Date", &EU4Date::isEU4Date)
        .def_static("stringValid", &EU4Date::stringValid, py::arg("text"));

    m.def("provinceLocation", &provinceLocation, py::arg("id"));
    m.def("drawBorders", &drawBorders, py::arg("playerColors"), py::arg("pixels"), py::arg("width"), py::arg("height"));
    m.def("loadProvinceMap", &pyProvMap);
    m.def("loadMapDef", &loadMapDef);
    m.def("drawMap", &pyDrawMap, py::arg("tagColors"), py::arg("provinceOwners"));
    m.def("loadWaterProvinces", &loadWaterProvinces);
    m.def("generateLandAdjacency", &pyGenerateLandAdjacency);
}