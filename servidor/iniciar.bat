@echo off
chcp 65001 >nul
cd /d %~dp0
if not exist .venv (
  echo Criando ambiente Python...
  py -3 -m venv .venv || python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
if not exist .env copy .env.exemplo .env >nul
python -m app.main
pause
