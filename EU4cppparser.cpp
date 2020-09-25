// cppimport
/*
<%
import pybind11
import sysconfig
setup_pybind11(cfg)
cfg['include_dirs'] = [pybind11.get_include(), sysconfig.get_path("include")]
cfg['compiler_args'] = ['-std=c++20', '/std:c++latest']
%>
*/

#include <pybind11/operators.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <variant>

#include "EU4Date.h"

namespace py = pybind11;

bool isEmpty(const std::string &text) {
    for (size_t i = 0; i < text.size(); ++i) {
        if (!std::isspace(text[i]))
            return false;
    }
    return true;
}

std::string trim(const std::string &text) {
    size_t start = 0;
    for (size_t i = 0; i < text.size(); ++i) {
        if (!std::isspace(text[i])) {
            start = i;
            break;
        }
    }
    for (size_t i = text.size() - 1; i >= 0; --i) {
        if (!std::isspace(text[i])) {
            return text.substr(start, (i - start + 1));
        }
    }
    // This means it's all whitespace
    return "";
}

std::list<std::string> splitStrings(const std::string &text) {
    std::list<std::string> out;
    unsigned char bracketCount = 0;
    bool quotes = false;
    size_t lastsplit = 0;
    for (size_t i = 0; i < text.size(); ++i) {
        if (bracketCount == 0 && !quotes && std::isspace(text[i])) {
            std::string split = trim(text.substr(lastsplit, i - lastsplit));
            if (split != "")
                out.push_back(split);
            lastsplit = i;
        } else if (text[i] == '{' && !quotes) {
            bracketCount++;
        } else if (text[i] == '}' && !quotes) {
            if (bracketCount > 0)
                bracketCount--;
        } else if (text[i] == '"') {
            quotes = !quotes;
        }
    }
    std::string split = trim(text.substr(lastsplit));
    if (split != "")
        out.push_back(split);
    return out;
}

PYBIND11_MODULE(EU4cppparser, m) {
    m.doc() = "EU4 parser C++ library.";

    py::class_<EU4Date>(m, "EU4Date")
        .def(py::init<const std::string &>(), py::arg("text"))
        .def_readwrite("year", &EU4Date::year)
        .def_readwrite("month", &EU4Date::month)
        .def_readwrite("day", &EU4Date::day)
        .def("__repr__", &EU4Date::toString)
        .def("fancyString", &EU4Date::fancyString)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def(py::self > py::self)
        .def(py::self <= py::self)
        .def(py::self >= py::self)
        .def("isValidDate", &EU4Date::isValidDate)
        .def("isEU4Date", &EU4Date::isEU4Date)
        .def_static("stringValid", &EU4Date::stringValid, py::arg("text"));

    m.def("isEmpty", &isEmpty, "Returns true if this string does not contain characters other than whitespace.", py::arg("text"));
    m.def("splitStrings", &splitStrings, py::arg("text"));
}