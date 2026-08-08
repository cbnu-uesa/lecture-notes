#!/usr/bin/env bash
# 슬라이드 HTML → 슬라이드 형식 PDF (design.md §9)
#
#   _scripts/build-pdf.sh                                   전체 강의
#   _scripts/build-pdf.sh 2026-1학기_.../slides/02-x.html    지정한 강의만
#
# decktape가 헤드리스 Chrome으로 슬라이드를 한 장씩 넘기며 캡처한다.
# fragment(누적 공개)마다 페이지가 분리되므로 기존 PPT 출력과 장수가 맞는다.
#
# npx로 실행하므로 이 폴더에 node_modules가 생기지 않는다 (CLAUDE.md 참조).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8099}"
cd "$ROOT"

# ── 임시 서버 (Drive 폴더 밖에 로그를 남긴다) ──────────────────
LOG="$(mktemp -t deckserve)"
python3 -m http.server "$PORT" --bind 127.0.0.1 >"$LOG" 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; rm -f "$LOG"' EXIT

for _ in $(seq 1 40); do
  if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/"; then break; fi
  sleep 0.25
done
if ! curl -sf -o /dev/null "http://127.0.0.1:${PORT}/"; then
  echo "임시 서버를 띄우지 못했습니다:" >&2; cat "$LOG" >&2; exit 1
fi

# ── 대상 목록 ────────────────────────────────────────────────
if [ "$#" -gt 0 ]; then
  TARGETS=("$@")
else
  TARGETS=()
  while IFS= read -r f; do TARGETS+=("$f"); done \
    < <(find . -path './_*' -prune -o -path '*/slides/*.html' -print | sed 's|^\./||' | sort)
fi

if [ "${#TARGETS[@]}" -eq 0 ]; then
  echo "변환할 슬라이드가 없습니다."; exit 0
fi

FAILED=0
for src in "${TARGETS[@]}"; do
  src="${src#./}"
  [ -f "$src" ] || { echo "건너뜀 (없는 파일): $src" >&2; FAILED=1; continue; }

  course_dir="$(dirname "$(dirname "$src")")"
  base="$(basename "$src" .html)"
  out="${course_dir}/pdf/${base}.pdf"
  mkdir -p "${course_dir}/pdf"

  # 경로에 한글·공백이 있으므로 URL 인코딩한다
  url_path="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$src")"

  echo "── ${src}"
  # --fragments 없으면 decktape가 Reveal을 fragments:false로 설정해
  # 누적 공개가 통째로 한 페이지에 찍힌다 (design.md §8).
  if npx --yes decktape@3 reveal \
        --fragments \
        --size 1920x1080 \
        --pause 400 \
        --load-pause 1200 \
        "http://127.0.0.1:${PORT}/${url_path}?export=1" \
        "$out"; then
    echo "   → ${out}"
  else
    echo "   ✗ 실패: ${src}" >&2
    FAILED=1
  fi
done

exit "$FAILED"
