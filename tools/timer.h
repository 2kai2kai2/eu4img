#pragma once
#include <chrono>
#include <iostream>
#include <string>

namespace eu4tool {
struct timer {
    std::chrono::steady_clock::time_point start;
    timer() {
        this->start = std::chrono::high_resolution_clock::now();
    }

    std::chrono::milliseconds getTime() {
        auto end = std::chrono::high_resolution_clock::now();
        return std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    }

    void printTime(const std::string &title = "") {
        auto duration = getTime();
        std::cout << title << " Duration: " << duration.count() << "ms." << std::endl;
    }
};
}