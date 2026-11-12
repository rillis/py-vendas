@echo off

:loop
cls
echo Iniciando execucao
echo.
call .\venv\Scripts\activate
python vendas.py
echo.
pause
goto loop