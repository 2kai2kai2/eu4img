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

#include <fstream>
#include <list>
#include <map>
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

    // Well most of this will be useless, but whatever.

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
    // And after all this we just return like a string of the rest or smth
    if (compression != 0) {
        // idk??
        return "";
    }
    int pixlength = width * height;
    std::string imgdata = "";

    while (!mapfile.eof()) {
        char pdata[3];
        mapfile.read(pdata, 3);
        // Reverse the numbers to deal with endianness
        char temp = pdata[0];
        pdata[0] = pdata[2];
        pdata[2] = temp;
        imgdata.append(pdata, 3);
    }

    return imgdata;
};

py::bytes pyProvMap() {
    return loadProvinceMap();
}

static const auto maxGet = std::numeric_limits<std::streamsize>::max();

std::map<uint32_t, std::tuple<uint8_t, uint8_t, uint8_t>> loadMapDef() {
    std::map<uint32_t, std::tuple<uint8_t, uint8_t, uint8_t>> out;
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
        out[provinceID] = std::make_tuple(red, green, blue);

        // Go to end of line
        char skip;
        while (file.get(skip)) {
            if (skip == '\n' || skip == file.eofbit) {
                break;
            }
        }
    }
    
    return out;
}

std::string drawMap(const std::map<std::string, std::tuple<uint8_t, uint8_t, uint8_t>> &tagColors, const std::map<uint32_t, std::string> &provinceOwners) {
    // First, construct a more direct map of province color to tag color

    /*
    [&provinceOwners]                    [     colorMap     ]
    [  province id  ] -> loadMapDef() -> [province map color]
    [      tag      ] -> &tagColors   -> [   country color  ]
     */

    std::map<std::tuple<uint8_t, uint8_t, uint8_t>, std::tuple<uint8_t, uint8_t, uint8_t>> colorMap;

    {
        // A scope so that the mapDef will get freed
        const std::map<uint32_t, std::tuple<uint8_t, uint8_t, uint8_t>> mapDef = loadMapDef();
        for (auto iter = provinceOwners.begin(); iter != provinceOwners.end(); ++iter) {
            // Check province ID and tag, if not found skip.
            if (mapDef.count(iter->first) == 0 || tagColors.count(iter->second) == 0) {
                py::print(iter->first);
                continue;
            }
            colorMap[mapDef.at(iter->first)] = tagColors.at(iter->second);
        }
    }

    static const size_t pixelCount = 5632*2048;
    std::string img;
    img.resize(pixelCount * 3); // Preset the size so we don't have to constantly resize
    
    const std::string provinceMap = loadProvinceMap();

    std::tuple<uint8_t, uint8_t, uint8_t> tempPixColor;
    std::tuple<uint8_t, uint8_t, uint8_t> tempMapColor;
    for (size_t i = 0; i < pixelCount; ++i) {
        tempMapColor = std::make_tuple((uint8_t)provinceMap[3*i], (uint8_t)provinceMap[3*i+1], (uint8_t)provinceMap[3*i+2]);
        tempPixColor = colorMap[tempMapColor];
        img[3*i] = std::get<0>(tempPixColor);
        img[3*i+1] = std::get<1>(tempPixColor);
        img[3*i+2] = std::get<2>(tempPixColor);
    }
    return img;
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
}