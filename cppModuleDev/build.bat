mkdir buildwin
cd buildwin
cmake ..
cmake --build . --config Release
cd ..
mkdir buildarm
cd buildarm
cmake .. -G "MinGW Makefiles"
cmake --build . --config Release
pause