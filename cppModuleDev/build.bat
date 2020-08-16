mkdir buildwin
cd buildwin
cmake ..
cmake --build . --config Release
cd ..
mkdir buildlin
cd buildlin
cmake .. -G "MinGW Makefiles"
cmake --build . --config Release
pause