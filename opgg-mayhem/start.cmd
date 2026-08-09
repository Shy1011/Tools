@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYCMD="
where python >nul 2>nul
if %errorlevel%==0 set "PYCMD=python"

if not defined PYCMD (
  py -3 -c "print(1)" >nul 2>nul
  if %errorlevel%==0 set "PYCMD=py -3"
)

if not defined PYCMD (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    set "PYCMD=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  )
)

if not defined PYCMD (
  echo [错误] 未找到 Python。
  echo 请安装 Python 3，或手动指定 Python 路径后运行：
  echo   python opgg_mayhem_server.py
  pause
  exit /b 1
)

echo 正在启动 ARAM: Mayhem 出装助手...
start "" "http://localhost:8765"
%PYCMD% opgg_mayhem_server.py
