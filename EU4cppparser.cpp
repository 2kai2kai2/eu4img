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

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/operators.h>
#include <string>
#include <variant>


namespace py = pybind11;


struct EU4Date {
    unsigned int year;
    unsigned char month;
    unsigned char day;

    EU4Date(const std::string &text) {
        size_t sep1 = text.find('.');
        size_t sep2 = text.rfind('.');
        year = std::stoi(text.substr(0, sep1));
        month = std::stoi(text.substr(sep1 + 1, sep2 - sep1));
        day = std::stoi(text.substr(sep2 + 1));
    }

    EU4Date(const unsigned int &year, const unsigned char &month, const unsigned char &day) : year(year), month(month), day(day) {}

    static bool stringValid(const std::string &text) {
        // This does not mean that the date is valid. It could be March 45th, 1345
        unsigned char dots = 0;
        unsigned char digits[3] = {0, 0, 0};
        for (size_t i = 0; i < text.size(); ++i) {
            if (text[i] == '.') {
                if (++dots > 2)
                    return false;
            } else if (std::isdigit(text[i])) {
                ++digits[dots];
            } else {
                return false;
            }
        }
        return 0 < digits[0] && digits[0] <= 4 && 0 < digits[1] && digits[1] <= 2 && 0 < digits[2] && digits[2] <= 2;
    }

    std::string toString() const {
        return std::to_string(this->year) + "." + std::to_string(this->month) + "." + std::to_string(this->day);
    }

    std::string fancyString() const {
        static const std::string monthNames[12] = {"January", "Febuary", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"};
        return std::to_string(this->day) + " " + monthNames[this->month - 1] + " " + std::to_string(this->year);
    }

    bool operator==(const EU4Date &other) const {
        return this->year == other.year && this->month == other.month && this->day == other.day;
    }

    bool operator!=(const EU4Date &other) const {
        return !(*this == other);
    }

    bool operator<(const EU4Date &other) const {
        return this->year < other.year || (this->year == other.year && (this->month < other.month || (this->month == other.month && this->day < other.day)));
    }

    bool operator>(const EU4Date &other) const {
        return this->year > other.year || (this->year == other.year && (this->month > other.month || (this->month == other.month && this->day > other.day)));
    }

    bool operator<=(const EU4Date &other) const {
        return *this < other || *this == other;
    }

    bool operator>=(const EU4Date &other) const {
        return *this > other || *this == other;
    }

    bool isValidDate() const {
        // Ignores leap days as invalid.
        static const unsigned char monthLengths[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
        return this->month >= 1 && this->month <= 12 && this->day >= 1 && this->day <= monthLengths[this->month - 1];
    }

    bool isEU4Date() const {
        return this->isValidDate() && EU4Date(1444, 11, 11) <= *this && *this <= EU4Date(1821, 1, 3);
    }
};

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