#!/usr/bin/env bash
# 교재 스캔 폴더를 통째로 OCR 해 폴더 안에 _ocr.txt 를 만든다.
#
#   _scripts/ocr-scan.sh "2026-2학기_도시및지역경제학/source/11장"
#
# macOS 내장 Vision 프레임워크(한국어 지원)를 쓴다 — 외부 서비스로 나가지 않는다.
# 필요 패키지: python3 -m pip install --user pyobjc-framework-Vision pyobjc-framework-Quartz
#   (~/Library 에 설치되므로 Drive 폴더에 파일이 늘지 않는다)
#
# 왜 쓰는가: 스캔 1쪽을 이미지로 읽으면 ~3.5k 토큰, OCR 텍스트로 읽으면 ~1.1k 토큰이다.
# 본문은 텍스트로 파악하고 그림·표가 있는 쪽만 이미지로 열면 판독 비용이 약 1/3이 된다.
set -euo pipefail
DIR="$1"
OUT="$DIR/_ocr.txt"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: > "$OUT"
# 파일명의 숫자 순서대로 (한글 파일명 glob 문제를 피해 find + python 정렬)
find "$DIR" -maxdepth 1 -name "*.jpg" -print0 | \
  python3 -c "
import sys, re
fs = sys.stdin.buffer.read().split(b'\0')
fs = [f.decode() for f in fs if f]
fs.sort(key=lambda s: int(re.search(r'(\d+)\.jpg$', s).group(1)))
print('\n'.join(fs))
" | while IFS= read -r f; do
  python3 "$HERE/ocr-scan.py" "$f" >> "$OUT" 2>/dev/null
done
echo "완료: $OUT ($(wc -l < "$OUT" | tr -d ' ') 줄)"
