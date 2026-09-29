#!/usr/bin/env python3
"""교수가 아티팩트에서 고친 문구를 원본 슬라이드와 맞대어 보여 준다.

    python3 _scripts/artifact/edits.py <아티팩트 HTML> <원본 슬라이드.html>

<아티팩트 HTML> 은 Artifact 도구의 read 가 저장해 준 파일이다.
수정마다 푸터 쪽 번호·슬라이드 제목·원래 문구·새 문구를 찍는다.
원본에 옮기는 일은 하지 않는다. 옮길 때는 design.md §4.8·§4.9·§4.14 를 따라
Claude 가 손으로 옮긴다 (&nbsp; 들여쓰기를 줄 맞춤 도구로 바꾸는 등 판단이 필요하다).

- 새 문구가 <br> 하나뿐이면 교수가 그 줄을 지운 것이다.
- "원본에 없음" 이 찍히면 아티팩트를 만든 뒤 원본이 바뀐 것이다. 그 수정은 눈으로 옮긴다.
- 쪽 번호는 deck-init.js 와 같은 방식으로 센다. 교수가 "N번 슬라이드"라고 하면 이 번호다.
"""
import json, re, sys


def pages(src):
    """<section> 시작 위치마다 (푸터 쪽 번호, 제목) — deck-init.js 의 stepOffset 과 같은 셈."""
    out, acc = [], 0
    for m in re.finditer(r"<section.*?</section>", src, re.S):
        sec = m.group(0)
        frs = re.findall(r'<[^>]*class="[^"]*\bfragment\b[^"]*"[^>]*>', sec)
        idx = [re.search(r'data-fragment-index="(\d+)"', f) for f in frs]
        steps = 1 + len({i.group(1) for i in idx if i}) + sum(1 for i in idx if not i)
        t = re.search(r"<h[12]>(.*?)</h[12]>|section-label\">(.*?)<", sec, re.S)
        title = re.sub(r"<[^>]+>", "", next((g for g in t.groups() if g), "")) if t else "(제목 없음)"
        out.append((m.start(), m.end(), acc + 1, title.strip()))
        acc += steps
    return out


def main(art, slide):
    a = open(art, encoding="utf8").read()
    src = open(slide, encoding="utf8").read()
    ed = json.loads(re.search(r'id="deck-edits">(.*?)</script>', a, re.S).group(1))
    secs = pages(src)
    flat = lambda h: re.sub(r"\s+", " ", h).strip()
    for k in sorted(ed, key=int):
        o, n = ed[k]["orig"], ed[k]["html"]
        cnt = src.count(o)
        where = "원본에 없음"
        if cnt == 1:
            pos = src.index(o)
            sec = next((s for s in secs if s[0] <= pos < s[1]), None)
            where = f"{sec[2]}쪽 「{sec[3]}」" if sec else "슬라이드 밖"
        elif cnt > 1:
            where = f"원본에 {cnt}번 — 위치를 눈으로 정한다"
        print(f"[{k}] {where}")
        print(f"  원래: {flat(o)}")
        print(f"  새로: {'(줄 삭제)' if flat(n) == '<br>' else flat(n)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
