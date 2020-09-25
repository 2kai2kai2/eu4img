/*
<%
import pybind11
import sysconfig
setup_pybind11(cfg)
cfg['include_dirs'] = [pybind11.get_include(), sysconfig.get_path("include")]
%>
*/

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <list>
#include <map>
#include <string>
#include <tuple>

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

PYBIND11_MODULE(EU4cpplib, m) {
    m.doc() = "Libraries for eu4img written in C++ to improve speed and resource-consumption.";

    m.def("drawBorders", &drawBorders, py::arg("playerColors"), py::arg("pixels"), py::arg("width"), py::arg("height"));
}