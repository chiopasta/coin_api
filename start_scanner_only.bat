@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
title CHIO COIN SCANNER - Scanner only
set "COIN_API_EXIT=2"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto path_error
echo Scanner only - no web dashboard.
echo Limit: 600 seconds / 180 HTTP requests.
echo Stop safely with Ctrl+C or stop_coin_api.bat.
call "%~dp0scripts\coin_api_python.cmd" _scanner --seconds 600 --max-requests 180 %*
set "COIN_API_EXIT=%ERRORLEVEL%"
popd
goto finish
:path_error
echo Status : BLOCKED
echo Reason : Cannot open the project folder.
:finish
if not "%COIN_API_NO_PAUSE%"=="1" pause
exit /b %COIN_API_EXIT%
