@echo off
setlocal DisableDelayedExpansion
set "COIN_API_ROOT=%~dp0.."
if defined COIN_API_PYTHON goto explicit
if exist "%COIN_API_ROOT%\.venv\Scripts\python.exe" goto dotvenv
if exist "%COIN_API_ROOT%\venv\Scripts\python.exe" goto venv
py -3 -I -c "import sys,sqlite3,ssl,ctypes; sys.exit(0 if sys.version_info >= (3,11) and sys.platform == 'win32' else 2)" >nul 2>&1
if not errorlevel 1 goto use_py
python -I -c "import sys,sqlite3,ssl,ctypes; sys.exit(0 if sys.version_info >= (3,11) and sys.platform == 'win32' else 2)" >nul 2>&1
if not errorlevel 1 goto use_python
echo Status : BLOCKED
echo Reason : Windows Python 3.11+ with sqlite3, ssl and ctypes was not found.
echo Action : Install/fix Python, or set COIN_API_PYTHON to its full executable path.
exit /b 2
:dotvenv
set "COIN_API_PYTHON=%COIN_API_ROOT%\.venv\Scripts\python.exe"
goto explicit
:venv
set "COIN_API_PYTHON=%COIN_API_ROOT%\venv\Scripts\python.exe"
:explicit
if not exist "%COIN_API_PYTHON%" goto invalid
"%COIN_API_PYTHON%" -I -c "import sys,sqlite3,ssl,ctypes; sys.exit(0 if sys.version_info >= (3,11) and sys.platform == 'win32' else 2)" >nul 2>&1
if errorlevel 1 goto invalid
"%COIN_API_PYTHON%" -I "%COIN_API_ROOT%\scripts\coin_api_entry.py" %*
exit /b %ERRORLEVEL%
:invalid
echo Status : BLOCKED
echo Reason : Selected Python is missing, broken or older than 3.11.
echo Action : Fix COIN_API_PYTHON or the local .venv/venv. No LIVE was started.
exit /b 2
:use_py
py -3 -I "%COIN_API_ROOT%\scripts\coin_api_entry.py" %*
exit /b %ERRORLEVEL%
:use_python
python -I "%COIN_API_ROOT%\scripts\coin_api_entry.py" %*
exit /b %ERRORLEVEL%
