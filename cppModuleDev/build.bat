mkdir buildwin
cd buildwin
cmake ..
cmake --build . --config Release
cd ..
mkdir buildlin
cd buildlin
cmake .. -G "MinGW Makefiles" -D CMAKE_TOOLCHAIN_FILE=linuxtoolchain.cmake
cmake --build . --config Release
pause