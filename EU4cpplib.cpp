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
#include <cstdlib>


namespace py = pybind11;


std::map<std::tuple<int, int, int>, std::list<std::tuple<int, int>>> drawBorders(std::map<std::tuple<int, int, int>, std::tuple<int, int, int>> playerColors, std::string pixels, int width, int height) {
    std::map<std::tuple<int, int, int>, std::list<std::tuple<int, int>>> out;
    // Setup iterators
    std::string::iterator iters[9];
    // Remember that 3 steps of the iterator is equal to one pixel
    for (int dy = 0; dy <= 2; dy++) {
        for (int dx = 0; dx <= 2; dx++) {
            int iterArrayIndex = dy * 3 + dx;
            iters[iterArrayIndex] = pixels.begin();
            std::advance(iters[iterArrayIndex], (dy * width + dx) * 3);
        }
    }
    // Go through and find borders
    for (int i = width + 1; i < width * height - width - 1; i++) {
        std::tuple<int, int, int> pcols[9];
        // Get the colors
        for (int iterNum = 0; iterNum < 9; iterNum++) {
            unsigned char red = *iters[iterNum];
            iters[iterNum]++;
            unsigned char green = *iters[iterNum];
            iters[iterNum]++;
            unsigned char blue = *iters[iterNum];
            iters[iterNum]++;
            std::tuple<int, int, int> rawColor = std::make_tuple((int) red, (int) green, (int) blue);
            if (playerColors.count(rawColor) > 0) {
                // Add the player color
                pcols[iterNum] = playerColors[rawColor];
            } else {
                // It's not on the player list so just add (0, 0, 0)
                pcols[iterNum] = std::make_tuple(0, 0, 0);
            }
        }
        // Check if any are different
        if (pcols[0] != pcols[1] || pcols[1] != pcols[2] || pcols[2] != pcols[3] || pcols[3] != pcols[4] || pcols[4] != pcols[5] || pcols[5] != pcols[6] || pcols[6] != pcols[7] || pcols[7] != pcols[8]) {
            if (out.count(pcols[4]) == 0) {
                // We need to create a new entry for this playerColor
                std::list<std::tuple<int, int>> entry;
                out[pcols[4]] = entry;
            }
            out[pcols[4]].push_back(std::make_tuple(i % width, i / width));
        }
    }
    return out;
};


PYBIND11_MODULE(EU4cpplib, m) {
    m.doc() = "Libraries for eu4img written in C++ to improve speed and resource-consumption.";

    m.def("drawBorders", &drawBorders, py::arg("playerColors"), py::arg("pixels"), py::arg("width"), py::arg("height"));
}