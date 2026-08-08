#!/usr/bin/env bash
# 디자인 시스템 카탈로그 번들 만들기
#
#   _scripts/stage-design.sh          번들 생성 + 미리보기 서버(포트 8090)
#   _scripts/stage-design.sh --build  번들만 생성
#
# _design/ 의 미리보기 카드와 _shared/ 의 실제 테마를 한 폴더로 합쳐
# Drive 밖(시스템 임시 디렉터리)에 번들을 만든다. 여기서 만든 번들을
# Claude가 DesignSync로 claude.ai/design 프로젝트에 올린다.
#
# 카드가 실제 테마 파일을 그대로 참조하므로, _shared/theme 를 고치면
# 카탈로그도 자동으로 따라온다 — 색·치수를 두 곳에 적어두지 않는다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-${TMPDIR:-/tmp}}/lecture-design"
PORT="${PORT:-8090}"

rm -rf "$OUT"
mkdir -p "$OUT/theme" "$OUT/fonts" "$OUT/js"

# 실제 테마 — 사본이 아니라 매번 새로 복사한다
cp "$ROOT/_shared/theme/tokens.css"     "$OUT/theme/"
cp "$ROOT/_shared/theme/cbnu.css"       "$OUT/theme/"
cp "$ROOT/_shared/theme/components.css" "$OUT/theme/"
cp "$ROOT/_shared/fonts/"*.woff2        "$OUT/fonts/"
cp "$ROOT/_shared/js/charts.js"         "$OUT/js/"
cp "$ROOT/_shared/vendor/mathjax-tex-svg.js" "$OUT/js/"
cp "$ROOT/_shared/img/cbnu-logo.jpg"    "$OUT/"

# 미리보기 카드
cp "$ROOT/_design/preview.css" "$OUT/theme/"
cp -R "$ROOT/_design/foundations" "$ROOT/_design/slides" "$ROOT/_design/charts" "$OUT/"

# 참조 검사 — 깨진 경로가 있으면 올리기 전에 잡는다
python3 - "$OUT" <<'PY'
import sys, os, re, glob
out = sys.argv[1]; bad = 0
for f in glob.glob(os.path.join(out, '*', '*.html')):
    s = open(f, encoding='utf-8').read()
    for ref in re.findall(r'(?:src|href)="([^"]+)"', s):
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), ref))):
            print(f'  누락: {os.path.relpath(f, out)} -> {ref}'); bad += 1
    if not s.startswith('<!-- @dsCard'):
        print(f'  @dsCard 마커 없음: {os.path.relpath(f, out)}'); bad += 1
print(f'참조 검사: 문제 {bad}건')
sys.exit(1 if bad else 0)
PY

echo "번들 생성 완료: $OUT"
echo "카드 $(find "$OUT" -name '*.html' | wc -l | tr -d ' ')장"

if [ "${1:-}" = "--build" ]; then
  exit 0
fi

echo
echo "미리보기: http://localhost:${PORT}/foundations/colors.html  (Ctrl+C 로 중지)"
cd "$OUT"
exec python3 -m http.server "$PORT" --bind 127.0.0.1
