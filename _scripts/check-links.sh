#!/usr/bin/env bash
# 링크 검사 — 강의 목록이 가리키는 슬라이드·PDF 가 실제로 열리는지 본다
#
#   _scripts/check-links.sh                                   로컬 (임시 서버를 띄운다)
#
# **배포 전에 로컬로 돌린다.** 배포본은 Cloudflare Access 가 로그인 없는 요청을
# 403 으로 막아 그냥은 못 본다 (2026-09-05 확인). 그래도 배포본을 확인해야 하면
# Zero Trust 에서 서비스 토큰을 만들어 환경변수로 넘긴다.
#
#   CF_ACCESS_CLIENT_ID=... CF_ACCESS_CLIENT_SECRET=... \
#     _scripts/check-links.sh https://lecture-notes.kks1104.workers.dev
#
# 토큰을 쓰려면 Access 정책에 그 토큰을 Include 로 넣어 두어야 한다.
#
# 왜 필요한가. 2026-08-26 에 도시교통통계학 course.json 만 lectures 에 file 이
# 없어서, 과목 index 의 `l.file.replace(...)` 에서 TypeError 가 나고 렌더링 루프가
# 멈춰 강의 목록이 통째로 비었다. 슬라이드 파일은 멀쩡했고 직접 주소로는 열렸기
# 때문에 배포 후에야 드러났다. 그 종류의 결함을 기계로 잡는다.
#
# check-figures.sh 가 슬라이드 '안'을 본다면 이 스크립트는 슬라이드 '사이'를 본다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8097}"
cd "$ROOT"

if [ "$#" -gt 0 ]; then
  BASE="${1%/}"
else
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  SERVER_PID=$!
  trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    curl -sf -o /dev/null "http://127.0.0.1:${PORT}/" && break || sleep 0.25
  done
  BASE="http://127.0.0.1:${PORT}"
fi

BASE="$BASE" python3 - "$ROOT" <<'PYEOF'
import json, os, re, sys, urllib.error, urllib.parse, urllib.request

BASE = os.environ['BASE'].rstrip('/')
ROOT = sys.argv[1]
LOCAL = BASE.startswith('http://127.0.0.1')

# Cloudflare Access 서비스 토큰. 없으면 헤더를 붙이지 않는다 (로컬은 필요 없다).
CF = {}
if os.environ.get('CF_ACCESS_CLIENT_ID') and os.environ.get('CF_ACCESS_CLIENT_SECRET'):
    CF = {'CF-Access-Client-Id': os.environ['CF_ACCESS_CLIENT_ID'],
          'CF-Access-Client-Secret': os.environ['CF_ACCESS_CLIENT_SECRET']}

def request(path, method='GET'):
    url = f"{BASE}/{urllib.parse.quote(path)}"
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=CF, method=method), timeout=30)

def fetch(path):
    try:
        with request(path) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b''
    except Exception as e:
        return str(e), b''

def head(path):
    try:
        return request(path, 'HEAD').status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return str(e)

errors, warns = [], []

# ── 루트 허브의 COURSES 배열 ────────────────────────────────
status, body = fetch('index.html')
if status == 403 and not LOCAL:
    print("중단: Cloudflare Access 가 막았습니다 (403).", file=sys.stderr)
    print("      배포본은 로그인해야 열립니다. 링크 검사는 배포 전에 인자 없이 돌리세요:",
          file=sys.stderr)
    print("        _scripts/check-links.sh", file=sys.stderr)
    if not CF:
        print("      배포본을 꼭 봐야 하면 Zero Trust 서비스 토큰을",
              file=sys.stderr)
        print("      CF_ACCESS_CLIENT_ID · CF_ACCESS_CLIENT_SECRET 로 넘기세요 (스크립트 앞머리 참조).",
              file=sys.stderr)
    else:
        print("      토큰을 넘겼는데도 막혔습니다. Access 정책 Include 에 그 토큰이 있는지 확인하세요.",
              file=sys.stderr)
    sys.exit(2)
if status != 200:
    print(f"중단: 루트 index.html 을 열 수 없습니다 ({status})", file=sys.stderr)
    sys.exit(2)
m = re.search(r'const COURSES\s*=\s*\[(.*?)\]', body.decode('utf-8'), re.S)
if not m:
    print("중단: 루트 index.html 에서 COURSES 배열을 찾지 못했습니다", file=sys.stderr)
    sys.exit(2)
listed = re.findall(r"'([^']+)'", m.group(1))

# 폴더는 있는데 배열에 없으면 사이트에 아예 안 뜬다 (CLAUDE.md — 수동 등록 지점은 여기뿐)
on_disk = sorted(d for d in os.listdir(ROOT)
                 if os.path.isfile(os.path.join(ROOT, d, 'course.json')))
import unicodedata
norm = lambda s: unicodedata.normalize('NFC', s)
for d in on_disk:
    if norm(d) not in [norm(x) for x in listed]:
        warns.append(f"{d} — course.json 이 있으나 루트 index.html 의 COURSES 에 없다")

total = 0
for course in listed:
    status, body = fetch(f'{course}/course.json')
    if status != 200:
        errors.append(f"{course}/course.json → {status}")
        continue
    try:
        c = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError as e:
        errors.append(f"{course}/course.json — JSON 문법 오류: {e}")
        continue

    done = 0
    seen = set()
    for l in c.get('lectures', []):
        no = l.get('no', '?')
        if l.get('status') != 'done':
            continue
        done += 1
        total += 1
        f = l.get('file')
        if not f:
            # 바로 이 결함이 목록을 통째로 비웠다
            errors.append(f"{c.get('title', course)} {no}강 — course.json 에 file 이 없다")
            continue
        seen.add(f)
        s = head(f'{course}/slides/{f}')
        if s != 200:
            errors.append(f"{c.get('title', course)} {no}강 슬라이드 → {s}  ({f})")
        p = head(f"{course}/pdf/{f[:-5] + '.pdf' if f.endswith('.html') else f}")
        if p != 200:
            warns.append(f"{c.get('title', course)} {no}강 PDF 없음 "
                         f"({'build-pdf.sh 를 돌리면 된다' if LOCAL else '배포본에 빠졌다'})")

    # course.json 이 모르는 슬라이드 — 만들어 놓고 등록을 잊은 것
    sdir = os.path.join(ROOT, course, 'slides')
    if os.path.isdir(sdir):
        for f in sorted(os.listdir(sdir)):
            if f.endswith('.html') and norm(f) not in [norm(x) for x in seen]:
                warns.append(f"{c.get('title', course)} — slides/{f} 가 course.json 에 없다")

    print(f"  {c.get('title', course)}: 완료 {done}강")

print()
for w in warns:
    print(f"  ! {w}")
for e in errors:
    print(f"  ✗ {e}")
print()
if errors:
    print(f"총 {total}강 · 오류 {len(errors)}건 · 경고 {len(warns)}건")
    sys.exit(1)
print(f"총 {total}강 · 문제 없음" + (f" (경고 {len(warns)}건)" if warns else ""))
PYEOF
