#!/usr/bin/env bash
# 교재 판독물 읽기 (http://localhost:8091)
#
#   _scripts/dossier-read.sh          번들 생성 + 읽기 서버
#   _scripts/dossier-read.sh --build  번들만 생성
#
# source/N장/_dossier.md 와 같은 폴더의 스캔 jpg 를 묶어, 쪽마다
# 왼쪽 스캔 원본 · 오른쪽 판독 텍스트로 나란히 보여준다.
#
# 번들은 Drive 밖(시스템 임시 디렉터리)에 만든다 — 스캔 사본이 동기화 대상이 되면 안 된다.
# 교재 저작권 때문에 이 산출물은 배포하지 않는다. build-site.sh 는 화이트리스트라
# source/ 를 애초에 담지 않으므로 실수로 새어 나가지 않는다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-${TMPDIR:-/tmp}}/lecture-dossier"
PORT="${PORT:-8091}"

rm -rf "$OUT"
mkdir -p "$OUT"
python3 "$ROOT/_scripts/dossier-read.py" "$ROOT" "$OUT"

echo "번들 생성 완료: $OUT"
du -sh "$OUT" | awk '{print "  크기 " $1}'

if [ "${1:-}" = "--build" ]; then
  exit 0
fi

echo
echo "읽기: http://localhost:${PORT}/  (Ctrl+C 로 중지)"
cd "$OUT"
exec python3 -m http.server "$PORT" --bind 127.0.0.1
