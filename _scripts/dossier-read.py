#!/usr/bin/env python3
"""교재 판독물(_dossier.md)을 읽기용 HTML 로 바꾼다 — dossier-read.sh 가 호출한다.

쪽마다 왼쪽에 스캔 원본, 오른쪽에 판독 텍스트를 나란히 놓는다.
원문 대조가 한눈에 되는 것이 이 도구의 존재 이유다. 그림·사진·표는
스캔 쪽 이미지가 원본 그대로이므로, 텍스트 쪽에는 캡션·축·인쇄된 숫자만 적는다.

이 산출물은 절대 배포하지 않는다 (교재 저작권). build-site.sh 의 화이트리스트가
source/ 를 담지 않으므로 구조적으로 새어 나가지 않는다.
"""
import html
import re
import sys
from pathlib import Path

# ── 아주 작은 Markdown 변환기 ────────────────────────────────
# 우리가 쓰는 문법만 다룬다: 제목·표·목록·인용·굵게·기울임·코드.
# 범용 파서를 끌어오지 않는 이유는 Drive 폴더에 의존성을 만들지 않기 위해서다.

def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    s = s.replace('[판독불가]', '<span class="unread">[판독불가]</span>')
    return s


def md_to_html(lines):
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue

        m = re.match(r'^(#{3,6})\s+(.*)$', ln)
        if m:
            lv = len(m.group(1))
            out.append(f'<h{lv}>{inline(m.group(2))}</h{lv}>')
            i += 1
            continue

        # 표: | a | b |  다음 줄이 구분선
        if ln.lstrip().startswith('|') and i + 1 < len(lines) and re.match(
                r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            cells = lambda r: [c.strip() for c in r.strip().strip('|').split('|')]
            head = cells(ln)
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                body.append(cells(lines[i]))
                i += 1
            t = ['<table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr></thead><tbody>']
            for row in body:
                t.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in row) + '</tr>')
            t.append('</tbody></table>')
            out.append(''.join(t))
            continue

        if ln.lstrip().startswith('> '):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith('> '):
                buf.append(lines[i].lstrip()[2:])
                i += 1
            out.append('<blockquote>' + ' '.join(inline(b) for b in buf) + '</blockquote>')
            continue

        if re.match(r'^\s*[-*]\s+', ln):
            buf = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                buf.append(re.sub(r'^\s*[-*]\s+', '', lines[i]))
                i += 1
            out.append('<ul>' + ''.join(f'<li>{inline(b)}</li>' for b in buf) + '</ul>')
            continue

        # 문단 — 빈 줄까지 모은다
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r'^(#{3,6}\s|\s*\||\s*>\s|\s*[-*]\s)', lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append('<p>' + inline(' '.join(buf)) + '</p>')
    return '\n'.join(out)


# ── dossier 파싱 ─────────────────────────────────────────────

# 쪽 머리: "## 스캔 3 · 책 p.183" 이 기본이고, 쪽번호가 인쇄되지 않은 속표지·백지는
# "## 스캔 1 · PART 02 속표지 (쪽번호 인쇄 없음)" 처럼 적는다. 뒤쪽은 그대로 라벨로 쓴다.
PAGE_RE = re.compile(r'^##\s+스캔\s+(\d+)\s*(?:·\s*(.+?))?\s*$')


def parse(path: Path):
    text = path.read_text(encoding='utf-8')
    meta, body = {}, text
    if text.startswith('---'):
        _, fm, body = text.split('---', 2)
        for line in fm.strip().splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()

    lines = body.splitlines()
    intro, pages, cur = [], [], None
    for ln in lines:
        m = PAGE_RE.match(ln)
        if m:
            cur = {'scan': int(m.group(1)), 'book': (m.group(2) or '').strip(), 'lines': []}
            pages.append(cur)
        elif cur is None:
            intro.append(ln)
        else:
            cur['lines'].append(ln)
    return meta, intro, pages


CSS = """
:root{--ink:#16181C;--ink2:#4A4741;--muted:#8A867E;--rule:#E2DED7;--crimson:#A02948;--bg:#FBFAF8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink2);
  font:400 15px/1.7 Pretendard,-apple-system,sans-serif;letter-spacing:-.01em}
a{color:var(--crimson)}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--rule);
  padding:14px 26px;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
header b{color:var(--ink);font-size:17px}
header .meta{color:var(--muted);font-size:13px}
nav a{margin-right:12px;font-size:13px;text-decoration:none}
.wrap{max-width:1500px;margin:0 auto;padding:22px 26px 80px}
.intro{border-left:3px solid var(--rule);padding:2px 0 2px 16px;margin:0 0 26px;color:var(--muted);font-size:14px}
.page{display:grid;grid-template-columns:minmax(280px,40%) 1fr;gap:26px;
  padding:24px 0;border-top:1px solid var(--rule);align-items:start}
.scan{position:sticky;top:70px}
.scan img{width:100%;display:block;border:1px solid var(--rule);background:#FFF}
.scan .cap{color:var(--muted);font-size:12px;padding:6px 2px;display:flex;justify-content:space-between}
.txt h3{font-size:15px;color:var(--crimson);margin:22px 0 6px;font-weight:700}
.txt h4{font-size:14px;color:var(--ink);margin:16px 0 4px;font-weight:700}
.txt p{margin:0 0 10px}
.txt table{border-collapse:collapse;margin:10px 0 14px;font-size:14px;width:100%}
.txt th{text-align:left;padding:5px 10px 7px;border-bottom:1.5px solid var(--ink);color:var(--ink)}
.txt td{padding:4px 10px;border-bottom:1px solid var(--rule)}
.txt blockquote{margin:10px 0;padding:2px 0 2px 14px;border-left:3px solid var(--rule);color:var(--muted)}
.txt ul{margin:0 0 10px;padding-left:18px}
.unread{color:var(--crimson);background:#F6E9EC;padding:0 4px;border-radius:2px;font-size:.9em}
.pno{color:var(--muted);font-size:12px;letter-spacing:.06em}
.idx{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:20px}
.idx a{display:block;padding:16px 18px;border:1px solid var(--rule);background:#FFF;
  text-decoration:none;color:var(--ink)}
.idx .n{font-size:18px;font-weight:700}
.idx .s{color:var(--muted);font-size:13px;margin-top:4px}
@media (max-width:900px){.page{grid-template-columns:1fr}.scan{position:static}}
"""


def shell(title, inner, nav=''):
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>@font-face{{font-family:Pretendard;src:url('fonts/Pretendard-Regular.woff2') format('woff2');font-weight:400}}
@font-face{{font-family:Pretendard;src:url('fonts/Pretendard-Bold.woff2') format('woff2');font-weight:700}}
{CSS}</style></head><body>{nav}<div class="wrap">{inner}</div></body></html>"""


def render_chapter(src: Path, out_dir: Path, scans: dict):
    meta, intro, pages = parse(src)
    name = meta.get('장', src.parent.name)
    head = (f'<header><b>{html.escape(name)}</b>'
            f'<span class="meta">책 {html.escape(meta.get("책쪽", "?"))} · '
            f'스캔 {len(pages)}쪽 · 판독 {html.escape(meta.get("판독", "?"))}</span>'
            f'<nav><a href="index.html">← 목록</a></nav></header>')
    body = []
    if any(l.strip() for l in intro):
        body.append(f'<div class="intro">{md_to_html(intro)}</div>')
    for p in pages:
        img = scans.get(p['scan'])
        left = (f'<img src="scan/{html.escape(img)}" loading="lazy" alt="스캔 {p["scan"]}쪽">'
                if img else '<div class="cap">스캔 없음</div>')
        book = inline(p['book'])   # 라벨에 **초점 불량** 처럼 강조가 들어온다
        body.append(
            f'<section class="page" id="p{p["scan"]}">'
            f'<div class="scan">{left}<div class="cap"><span>스캔 {p["scan"]}</span><span>{book}</span></div></div>'
            f'<div class="txt">{md_to_html(p["lines"])}</div></section>')
    (out_dir / f'{src.parent.name}.html').write_text(
        shell(name, ''.join(body), head), encoding='utf-8')
    return name, len(pages), meta, {p['scan'] for p in pages}


def main():
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    cards = []
    # 폴더 이름순으로 두면 10장이 3장 앞에 온다. 이름 속 첫 숫자로 정렬한다
    # ("챕터 1-2" → 1, "3장" → 3, "10장" → 10).
    def chapter_no(p: Path):
        m = re.search(r'\d+', p.parent.name)
        return (int(m.group()) if m else 999, p.parent.name)

    for dossier in sorted(root.glob('*/source/*/_dossier.md'), key=chapter_no):
        chdir = dossier.parent
        bundle = out / chdir.name
        (bundle / 'scan').mkdir(parents=True, exist_ok=True)
        scans = {}
        for jpg in chdir.glob('*.jpg'):
            m = re.search(r'(\d+)\.jpg$', jpg.name)
            if not m:
                continue
            n = int(m.group(1))
            safe = f'{n:03d}.jpg'
            (bundle / 'scan' / safe).write_bytes(jpg.read_bytes())
            scans[n] = safe
        # 폰트는 장마다 상대경로로 부르므로 각 폴더에 둔다 (심볼릭 대신 복사 — Drive 밖이다)
        (bundle / 'fonts').mkdir(exist_ok=True)
        for f in (root / '_shared' / 'fonts').glob('Pretendard-*.woff2'):
            (bundle / 'fonts' / f.name).write_bytes(f.read_bytes())
        name, n, meta, covered = render_chapter(dossier, bundle, scans)
        missing = sorted(set(scans) - covered)
        if missing:
            print(f'  경고: {chdir.name} — 판독물에 없는 스캔 {missing}')
        cards.append((f'{chdir.name}/{chdir.name}.html', name, n, meta))

    idx = ['<h1 style="font-size:22px;color:#16181C;margin:6px 0 0">교재 판독물</h1>',
           '<p style="color:#8A867E;font-size:14px;margin:6px 0 0">'
           '스캔 원본과 판독 텍스트를 쪽마다 나란히 둔다. 개인 참고용이며 배포하지 않는다.</p>',
           '<div class="idx">']
    for href, name, n, meta in cards:
        idx.append(f'<a href="{href}"><div class="n">{html.escape(name)}</div>'
                   f'<div class="s">책 {html.escape(meta.get("책쪽", "?"))} · 스캔 {n}쪽</div></a>')
    idx.append('</div>')
    (out / 'index.html').write_text(shell('교재 판독물', ''.join(idx)), encoding='utf-8')
    (out / 'fonts').mkdir(exist_ok=True)
    for f in (root / '_shared' / 'fonts').glob('Pretendard-*.woff2'):
        (out / 'fonts' / f.name).write_bytes(f.read_bytes())
    print(f'장 {len(cards)}개')


if __name__ == '__main__':
    main()
