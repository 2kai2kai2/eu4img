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

typedef std::variant<std::string, long long, float, EU4Date> EU4Key;
class EU4Dict;
typedef std::variant<std::string, long long, float, EU4Date, py::list, EU4Dict> EU4Value;

typedef std::pair<EU4Key, EU4Value> VKPair;
/**
 * This is like a dict that can have multiple of the same key, since EU4 save files can do so.
 * https://docs.python.org/3/library/stdtypes.html#typesmapping
 */
class EU4Dict {
    std::vector<VKPair> data;

public:
    EU4Dict() : data(std::vector<VKPair>()) {}

    EU4Dict(const std::map<EU4Key, EU4Value> dict) : data(std::vector<VKPair>()) {
        for (const std::pair<EU4Key, EU4Value> &pair : dict) {
            data.emplace_back(pair);
        }
    }

    std::vector<VKPair> allPairs() const {
        return data;
    }

    VKPair getPair(size_t &index) const {
        return data[index];
    }

    void setPair(size_t &index, VKPair pair) {
        data[index] = pair;
    }
    /* Comment out so there is no overloading to mess up pybind11
        void setPair(size_t &index, EU4Key key, EU4Value value) {
            data[index] = VKPair(key, value);
        }
        */

    std::vector<EU4Value> getAll(const EU4Key &key) const {
        std::vector<EU4Value> values = std::vector<EU4Value>();
        for (size_t i = 0; i < data.size(); ++i) {
            if (data[i].first == key)
                values.emplace_back(data[i].second);
        }
        return values;
    }
    EU4Value getFirst(const EU4Key &key) const {
        for (size_t i = 0; i < data.size(); ++i) {
            if (data[i].first == key)
                return data[i].second;
        }
        return nullptr;
    }
    EU4Value getLast(const EU4Key &key) const {
        for (size_t i = data.size() - 1; i > 0; --i) {
            if (data[i].first == key)
                return data[i].second;
        }
        return nullptr;
    }

    size_t length() const {
        return data.size();
    }

    void add(EU4Key key, EU4Value value) {
        data.emplace_back(VKPair(key, value));
    }

    // Kinda inefficient because it copies before deleting
    VKPair popBack() {
        VKPair out = data.back();
        data.pop_back();
        return out;
    }

    std::string toString() {
        std::string s = "{";
        for (size_t i = 0; i < data.size(); ++i) {
            // TODO: All this casting is bad. Not sure if there's a better way to do this.
            s += std::string(py::str(py::cast(data[i].first))) + ": " + std::string(py::str(py::cast(data[i].second)));
            if (i != data.size() - 1)
                s += ", ";
        }
        return s + "}";
    }

    bool operator==(const EU4Dict &other) const {
        return data == other.data;
    }
    bool operator!=(const EU4Dict &other) const {
        return !(*this == other);
    }

    VKPair operator[](size_t index) const {
        return data[index];
    }
    VKPair &operator[](size_t index) {
        return data[index];
    }
};

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
            ++bracketCount;
        } else if (text[i] == '}' && !quotes) {
            if (bracketCount > 0)
                --bracketCount;
        } else if (text[i] == '"') {
            quotes = !quotes;
        }
    }
    std::string split = trim(text.substr(lastsplit));
    if (split != "")
        out.push_back(split);
    return out;
}

EU4Key parseKey(const std::string &text) {
    const std::string &trimmed(trim(text));
    unsigned char dots = 0;
    for (size_t i = 0; i < text.size(); ++i) {
        if (text[i] == '.') {
            if (++dots > 2)
                return trimmed; // STRING
        } else if (!std::isdigit(text[i])) {
            return trimmed; // STRING
        }                   // If it isn't a '.' or get caught by !isdigit then it is a digit and we continue
    }
    // So at this point we have only run into 0, 1, or 2 '.' and the rest of the characters have been digits
    if (dots == 0)
        return std::stoll(trimmed); // INT
    else if (dots == 1)
        return std::stof(trimmed); // FLOAT
    else                           // (dots == 2)
        return EU4Date(trimmed);   // DATE
}

EU4Value parseValue(const std::string &text) {
    const std::string &trimmed(trim(text));
    // First check for a group
    if (text[0] == '{' && text.back() == '}') {
        std::list<std::string> items = splitStrings(trimmed.substr(1, trimmed.size() - 2));
        if (items.size() == 0) {
            return py::list();
        } else {
            std::string &first = items.front();
            bool isDict = false;
            // If we run into a '=' before a potential '{' then it's a dict, and may or may not be a dict with dict keys
            // If we run into a '{' before '=' then it's a list of groups but not a dict. The groups may be dicts.
            for (size_t i = 0; i < first.size(); i++) {
                if (first[i] == '=') {
                    isDict = true;
                    break;
                } else if (first[i] == '{') {
                    isDict = false;
                    break;
                }
            }
            if (isDict) {
                EU4Dict dict = EU4Dict();
                for (const std::string &item : items) {
                    const size_t eqIndex = item.find('=');
                    dict.add(parseKey(item.substr(0, eqIndex)), parseValue(item.substr(eqIndex + 1)));
                }
                return dict;
            } else {
                py::list list = py::list();
                for (const std::string &item : items) {
                    list.append(parseValue(item));
                }
                return list;
            }
        }
    }
    // Next check int/float/date
    unsigned char dots = 0;
    for (size_t i = 0; i < text.size(); ++i) {
        if (text[i] == '.') {
            if (++dots > 2)
                return trimmed; // STRING
        } else if (!std::isdigit(text[i])) {
            return trimmed; // STRING
        }                   // If it isn't a '.' or get caught by !isdigit then it is a digit and we continue
    }
    // So at this point we have only run into 0, 1, or 2 '.' and the rest of the characters have been digits
    if (dots == 0)
        return std::stoll(trimmed); // INT
    else if (dots == 1)
        return std::stof(trimmed); // FLOAT
    else                           // (dots == 2)
        return EU4Date(trimmed);   // DATE
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

    py::class_<EU4Dict>(m, "EU4Dict")
        .def(py::init<>())
        .def(py::init<const std::map<EU4Key, EU4Value> &>(), py::arg("map"))
        .def("allPairs", &EU4Dict::allPairs)
        .def("__getitem__", &EU4Dict::getPair, py::arg("index"))
        .def("__setitem__", &EU4Dict::setPair)
        .def("getAll", &EU4Dict::getAll, py::arg("key"))
        .def("getFirst", &EU4Dict::getFirst, py::arg("key"))
        .def("getLast", &EU4Dict::getLast, py::arg("key"))
        .def("__len__", &EU4Dict::length)
        .def("append", &EU4Dict::add, py::arg("key"), py::arg("value"))
        .def("popBack", &EU4Dict::popBack)
        .def("__repr__", &EU4Dict::toString)
        .def(py::self == py::self)
        .def(py::self != py::self);

    m.def("parseValue", &parseValue, "Parses a value.", py::arg("text"));

    m.def("isEmpty", &isEmpty, "Returns true if this string does not contain characters other than whitespace.", py::arg("text"));
    m.def("splitStrings", &splitStrings, py::arg("text"));
}