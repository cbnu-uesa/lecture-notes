#!/usr/bin/env bash
# 배포용 정적 사이트 생성 → dist/
#
# 화이트리스트 방식이다. 여기 명시된 것만 복사한다.
# source/ 와 private/ (원본 pptx, 시험지, 성적)는 절대 담기지 않는다 — CLAUDE.md 참조.
#
# dist/ 는 Drive 동기화 대상 밖(시스템 임시 디렉터리)에 만들고 심볼릭 링크만 남긴다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-${TMPDIR:-/tmp}}/lecture-site"

cd "$ROOT"
rm -rf "$OUT"
mkdir -p "$OUT"

# ── 공용 자산 ────────────────────────────────────────────────
mkdir -p "$OUT/_shared"
cp -R _shared/theme _shared/js _shared/fonts _shared/img _shared/vendor "$OUT/_shared/"

# ── 루트 허브 ────────────────────────────────────────────────
[ -f index.html ] && cp index.html "$OUT/"

# ── 학기 폴더: slides/ pdf/ assets/ index.html course.json 만 ──
# 폴더 이름(한글)으로 glob하지 않는다. macOS는 파일명을 NFD로 저장하는데
# 스크립트 안의 한글 리터럴은 NFC라서 패턴이 영영 안 맞는다.
# 대신 course.json이 있는 디렉터리를 학기 폴더로 본다.
COURSES=0
while IFS= read -r meta; do
  name="$(basename "$(dirname "$meta")")"
  case "$name" in _*) continue;; esac
  mkdir -p "$OUT/$name"
  for sub in slides pdf assets; do
    [ -d "$name/$sub" ] && cp -R "$name/$sub" "$OUT/$name/"
  done
  [ -f "$name/index.html" ] && cp "$name/index.html" "$OUT/$name/"
  cp "$meta" "$OUT/$name/"
  COURSES=$((COURSES + 1))
done < <(find . -mindepth 2 -maxdepth 2 -name course.json -not -path './_*')

if [ "$COURSES" -eq 0 ]; then
  echo "경고: course.json을 가진 학기 폴더를 찾지 못했습니다." >&2
fi

# ── GitHub Pages 대비 ────────────────────────────────────────
# Jekyll 은 밑줄로 시작하는 최상위 폴더를 무시한다. _shared/ 가 통째로 빠지면
# 모든 슬라이드의 CSS·폰트·JS 가 404 가 된다. 빈 .nojekyll 하나로 막는다.
touch "$OUT/.nojekyll"

# ── Cloudflare Workers 대비 ──────────────────────────────────
# 깃 연동 배포는 저장소 폴더를 통째로 자산으로 올린다. 파일 하나당 25MiB 제한이
# 있는데 .git/objects 의 팩 파일이 이를 넘어 배포가 실패한다 (2026-09-04).
# .assetsignore 는 업로드되지 않으며 여기 적힌 것을 자산에서 뺀다.
printf '.git\n.git/**\n' > "$OUT/.assetsignore"

# ── 안전 점검 ────────────────────────────────────────────────
LEAK="$(find "$OUT" \( -name '*.hwp' -o -name '*.xlsx' -o -name '*.pptx' \) -print)"
if [ -n "$LEAK" ]; then
  echo "중단: 비공개 파일이 배포 대상에 섞였습니다." >&2
  echo "$LEAK" >&2
  exit 1
fi

echo "생성 완료: $OUT"
find "$OUT" -maxdepth 2 -mindepth 1 -not -path '*/_shared/*' | sed "s|$OUT|  dist|"
echo
echo "미리보기:  (cd '$OUT' && python3 -m http.server 8081)"
