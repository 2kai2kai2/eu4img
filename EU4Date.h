#pragma once
#include <string>

struct EU4Date {
    unsigned int year;
    unsigned char month;
    unsigned char day;

    EU4Date(const std::string &text) {
        size_t sep1 = text.find('.');
        size_t sep2 = text.rfind('.');
        this->year = std::stoi(text.substr(0, sep1));
        this->month = std::stoi(text.substr(sep1 + 1, sep2 - sep1));
        this->day = std::stoi(text.substr(sep2 + 1));
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