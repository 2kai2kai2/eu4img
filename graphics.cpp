// cppimport
// ^ That needs to be the first line for cppimport to work
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <cstdlib>

std::map<std::tuple<int, int, int>, std::list<std::tuple<int, int>>> drawBorders(std::map<std::tuple<int, int, int>, std::tuple<int, int, int>> playerColors, std::vector<std::tuple<int, int, int>> pixels, int width, int yOffset) {
    std::map<std::tuple<int, int, int>, std::list<std::tuple<int, int>>> out;
    for (int i = width + 1; i < pixels.size() - width - 1; i++) {
        // If it's ever less than three times width, it'll never even enter the for loop.
        // We don't run the first and last lines so that they don't try to refer to out of bounds neighbors.
        if (playerColors.count(pixels.at(i)) == 1) {
            // Check it's a player or subject
            std::tuple<int, int, int>& playerColor = playerColors[pixels.at(i)];
            if (playerColor != playerColors[pixels.at(i-1-width)] || playerColor != playerColors[pixels.at(i-width)] || playerColor != playerColors[pixels.at(i+1-width)] || playerColor != playerColors[pixels.at(i-1)] || playerColor != playerColors[pixels.at(i+1)] || playerColor != playerColors[pixels.at(i-1+width)] || playerColor != playerColors[pixels.at(i+width)] || playerColor != playerColors[pixels.at(i+1+width)]) {
                if (out.count(playerColor) == 0) {
                    // We need to create a new entry for this playerColor
                    std::list<std::tuple<int, int>> entry;
                    out[playerColor] = entry;
                }
                out[playerColor].push_back(std::make_tuple(i % width, yOffset + i / width));
            }
        }
    }
    return out;
};


int add(int i, int j) {
    return i + j;
    new std::list<int>();
}

namespace py = pybind11;

PYBIND11_MODULE(EU4cpplib, m) {
    m.doc() = "Libraries for eu4img written in C++ to improve speed and resource-consumption.";

    m.def("drawBorders", &drawBorders, py::arg("playerColors"), py::arg("pixels"), py::arg("width"), py::arg("yOffset") = 0);
    m.def("add", &add, "A function which adds two numbers", py::arg("a"), py::arg("b"));
}