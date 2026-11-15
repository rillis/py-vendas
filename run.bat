@echo off
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Criando venv e instalando dependencias...
    python -m venv venv || goto erro_venv
    venv\Scripts\pip install -r requirements.txt || goto erro_venv
)

:loop
cls
echo Iniciando execucao
echo.
call .\venv\Scripts\activate
python vendas.py
echo.
pause
goto loop

:erro_venv
echo Erro: falha ao criar o venv.
rmdir /s /q venv 2>nul
pause
exit /b 1
