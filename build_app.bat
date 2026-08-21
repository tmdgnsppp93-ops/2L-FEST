@echo off
REM =============================================================
REM GEDO  -  standalone app builder for WINDOWS (PyInstaller)
REM 결과물: dist\GEDO\GEDO.exe  (파이썬 불필요)
REM
REM 사전 준비(1회, Windows에서):
REM   pip install numpy scipy matplotlib customtkinter ezdxf pyinstaller
REM (macOS .app 는 build_app.command 로, macOS 에서 빌드)
REM =============================================================
cd /d "%~dp0"

python -m PyInstaller --noconfirm --windowed ^
    --name "GEDO" ^
    --collect-all customtkinter ^
    --collect-all ezdxf ^
    2L_FEST.py

echo.
echo Done. Output in:  dist\GEDO\
echo 처음 실행 시 SmartScreen 이 뜨면: "추가 정보" - "실행"
pause
