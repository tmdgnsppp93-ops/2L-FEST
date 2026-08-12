#!/bin/bash
# =============================================================
# 2L-FEST PRO launcher
# 이 폴더의 최신 빌드를 Python 3.10+(우선 3.12)로 항상 실행합니다.
# Finder에서 더블클릭하거나 터미널에서 ./run.command 로 실행하세요.
# =============================================================
cd "$(dirname "$0")" || exit 1

APP="2L_FEST.py"
if [ ! -f "$APP" ]; then
    echo "ERROR: $APP 가 이 폴더에 없습니다: $(pwd)"
    read -n1 -r -p "Press any key to close..."; exit 1
fi

# Python 3.10+ 인터프리터 탐색 (3.9는 임포트 실패하므로 제외)
for PY in python3.12 python3.13 python3.11 python3.10; do
    if command -v "$PY" >/dev/null 2>&1; then
        echo "Launching 2L-FEST with $PY ..."
        echo "(창 제목/콘솔의 build 라벨로 버전을 확인하세요)"
        exec "$PY" "$APP"
    fi
done

echo "ERROR: Python 3.10+ 를 찾지 못했습니다. (기본 python3=3.9 는 이 앱을 못 돌립니다)"
echo "  -> brew install python@3.12  설치 후 다시 실행하세요."
read -n1 -r -p "Press any key to close..."
exit 1
