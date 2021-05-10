#pragma once
#include <chrono>
#include <iostream>
#include <string>

namespace eu4tool {
struct timer {
    std::chrono::steady_clock::time_point start;
    timer() : start(std::chrono::high_resolution_clock::now()){
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

template <size_t N, class T = std::chrono::microseconds>
struct partTimer {
    T times[N];
    std::chrono::steady_clock::time_point starts[N];
    std::string timernames[N];
    std::string unit;

    partTimer() {
        this(std::string[N]);
    }

    partTimer(const std::string names[N]) {
        if (std::is_same<T, std::chrono::seconds>::value) {
            unit = "seconds";
        } else if (std::is_same<T, std::chrono::milliseconds>::value) {
            unit = "milliseconds";
        } else if (std::is_same<T, std::chrono::microseconds>::value) {
            unit = "microseconds";
        } else if (std::is_same<T, std::chrono::nanoseconds>::value) {
            unit = "nanoseconds";
        } else {
            unit = "unknown units";
        }
        std::chrono::steady_clock::time_point start = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < N; ++i) {
            starts[i] = start;
            times[i] = T::zero();
            timernames[i] = names[i];
        }
    }

    void start(const size_t &timernum) {
        starts[timernum] = std::chrono::high_resolution_clock::now();
    }

    T getLatestTime(const size_t &timernum) {
        auto end = std::chrono::high_resolution_clock::now();
        if (starts[timernum] == std::chrono::steady_clock::time_point::min()) {
            return T::zero();
        }
        return std::chrono::duration_cast<T>(end - starts[timernum]);
    }

    void stop(const size_t &timernum) {
        times[timernum] += getLatestTime(timernum);
        starts[timernum] = std::chrono::steady_clock::time_point::min();
    }

    T getTime(const size_t &timernum) {
        return std::chrono::duration_cast<T>(times[timernum]);
    }

    /**
     * This does not affect the object in any way. It simply prints the total time for a specified timer.
     */
    void printTime(const size_t &timernum) {
        auto duration = times[timernum];
        
        std::cout << timernames[timernum] << " Duration: " << duration.count() << unit << std::endl;
    }

    void reset(const size_t &timernum) {
        starts[timernum] = std::chrono::high_resolution_clock::now();
        times[timernum] = T::zero();
    }
};
}