#!/usr/bin/env bash
# 그래프 자동 검사 — 좌표점이 곡선을 벗어났는지, 글자가 캔버스를 넘었는지
#
#   _scripts/check-figures.sh                                   전체 슬라이드
#   _scripts/check-figures.sh 2026-1학기_.../slides/02-x.html    지정한 것만
#
# PDF를 뽑기 전에 돌린다. decktape이 쓰는 헤드리스 Chrome을 그대로 재사용하므로
# 이 폴더에 node_modules가 생기지 않는다 (CLAUDE.md 환경 제약).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8098}"
cd "$ROOT"

# decktape을 한 번이라도 돌렸으면 npx 캐시에 puppeteer가 있다
PUP="$(find "$HOME/.npm/_npx" -maxdepth 4 -type d -name puppeteer 2>/dev/null | head -1)"
if [ -z "$PUP" ]; then
  echo "puppeteer를 찾지 못했습니다. _scripts/build-pdf.sh 를 한 번 실행해 받으십시오." >&2
  exit 2
fi

LOG="$(mktemp -t figserve)"
python3 -m http.server "$PORT" --bind 127.0.0.1 >"$LOG" 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; rm -f "$LOG"' EXIT
for _ in $(seq 1 40); do
  curl -sf -o /dev/null "http://127.0.0.1:${PORT}/" && break || sleep 0.25
done

if [ "$#" -gt 0 ]; then TARGETS=("$@"); else
  TARGETS=()
  while IFS= read -r f; do TARGETS+=("$f"); done \
    < <(find . -path './_*' -prune -o -path '*/slides/*.html' -print | sed 's|^\./||' | sort)
fi

URLS=()
for src in "${TARGETS[@]}"; do
  enc="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "${src#./}")"
  URLS+=("http://127.0.0.1:${PORT}/${enc}")
done

PUPPETEER_PATH="$PUP" node "$ROOT/_scripts/check-figures.mjs" "${URLS[@]}"
