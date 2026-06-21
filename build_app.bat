@echo off
REM =============================================================
REM 2L-FEST PRO  -  standalone app builder for WINDOWS (PyInstaller)
REM 결과물: dist\"2L-FEST PRO"\"2L-FEST PRO.exe"  (파이썬 불필요)
REM
REM 사전 준비(1회, Windows에서):
REM   pip install numpy scipy matplotlib customtkinter ezdxf pyinstaller
REM (macOS .app 는 build_app.command 로, macOS 에서 빌드)
REM =============================================================
cd /d "%~dp0"

python -m PyInstaller --noconfirm --windowed ^
    --name "2L-FEST PRO" ^
    --collect-all customtkinter ^
    --collect-all ezdxf ^
    2L_FEST_v28_18_wf_wired.py

echo.
echo Done. Output in:  dist\"2L-FEST PRO"\
echo 처음 실행 시 SmartScreen 이 뜨면: "추가 정보" - "실행"
pause
