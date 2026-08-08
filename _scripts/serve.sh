#!/usr/bin/env bash
# 로컬 미리보기 서버. 프로젝트 루트를 http://localhost:8080 으로 연다.
#
# file:// 로 열면 course.json fetch가 CORS에 막혀 푸터바·표지 라벨이 비어 있다.
# 반드시 이 스크립트로 연다.
set -euo pipefail

PORT="${PORT:-8080}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
echo "강의노트 서버: http://localhost:${PORT}/"
echo "  루트  : $ROOT"
echo "  중지  : Ctrl+C"
echo
exec python3 -m http.server "$PORT" --bind 127.0.0.1
