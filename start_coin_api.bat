@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "COIN_API_EXIT=2"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto path_error
call "%~dp0scripts\coin_api_python.cmd" start %*
set "COIN_API_EXIT=%ERRORLEVEL%"
popd
goto finish
:path_error
echo Status : BLOCKED
echo Reason : Cannot open the project folder.
:finish
if not "%COIN_API_NO_PAUSE%"=="1" pause
exit /b %COIN_API_EXIT%
