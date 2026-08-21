#!/bin/bash
# =============================================================
# GEDOS  -  standalone app builder (PyInstaller)
# macOS   -> dist/GEDOS.app        (더블클릭 실행, 파이썬 불필요)
# Windows -> dist/GEDOS/GEDOS.exe     (이 스크립트를 Windows에서 실행)
#
# 사전 준비(1회): python3.12 -m pip install --break-system-packages pyinstaller
#   (런타임 의존성 numpy/scipy/matplotlib/customtkinter/ezdxf 는 이미 설치돼 있어야 함)
# =============================================================
cd "$(dirname "$0")" || exit 1

PY=python3.12
command -v "$PY" >/dev/null 2>&1 || PY=python3

echo "Building GEDOS with $PY ..."
"$PY" -m PyInstaller --noconfirm --windowed \
    --name "GEDOS" \
    --collect-all customtkinter \
    --collect-all ezdxf \
    2L_FEST.py

echo
echo "Done. Output in:  dist/"
echo "  macOS:   open 'dist/GEDOS.app'"
echo "  Windows: dist/GEDOS/GEDOS.exe"
echo "(서명 안 된 빌드라 처음엔 우클릭->열기 / SmartScreen 허용 필요)"
