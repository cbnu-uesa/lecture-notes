#!/usr/bin/env python3
"""강의노트 한 편을 교수가 직접 고칠 수 있는 아티팩트 페이지로 만든다.

    python3 _scripts/artifact/build.py 2026-2학기_도시및지역경제학/slides/05-도시노동시장.html

- 결과는 Drive 밖 ${TMPDIR}/lecture-artifact/<파일이름>/index.html 에 쓴다.
- 마지막 줄에 Artifact 도구의 files 인자로 넘길 JSON 을 찍는다
  (게시 경로 → 저장소 기준 원본 경로). Claude 가 이 둘로 게시한다.
- 원본 덱은 <template> 에 그대로 두고, 고친 문구만 {순번: {orig, html}} 으로 쌓인다.
  되받아 올 때는 _scripts/artifact/edits.py 를 쓴다.

제약
- 아티팩트는 밑줄로 시작하는 최상위 폴더를 받지 않는다. _shared/ 를 shared/ 로 옮겨 싣는다.
- 수식(MathJax) 덱은 아직 싣지 않는다. mathjax-tex-svg.js 가 2MB 라 빼 두었다.
- course.json 을 싣지 않고 표지 라벨·날짜·kicker·푸터를 미리 채운다.
- PDF 내려받기 단추는 만들지 않는다. 아티팩트 안에서는 동작하지 않는다.
"""
import json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def main(rel):
    src_path = os.path.join(ROOT, rel)
    src = open(src_path, encoding="utf8").read()
    course_dir = os.path.dirname(os.path.dirname(src_path))
    course = json.load(open(os.path.join(course_dir, "course.json"), encoding="utf8"))
    name = os.path.basename(src_path)
    no = int(name[:2])
    me = next((l for l in course.get("lectures", []) if l.get("no") == no), {})

    head = src.split("<head>", 1)[1].split("</head>", 1)[0]
    body = src.split("<body>", 1)[1].split("</body>", 1)[0]

    text_only = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    if re.search(r"\\\(|\\\[|\$\$|\$[^$<\s][^$<]{0,60}\$", text_only):
        sys.exit("수식이 있는 덱이다. 아직 싣지 못한다 (build.py 머리말 참조).")

    links = re.findall(r'<link rel="stylesheet"[^>]*>', head)
    head_scripts = re.findall(r"<script>.*?</script>", head, re.S)
    ext_scripts = re.findall(r'<script src="([^"]+)"></script>', head)
    styles = re.findall(r"<style>(.*?)</style>", head, re.S)
    deck = re.split(r'<script src="[^"]*vendor/reveal/reveal\.js">', body)[0].strip()

    files = {}

    def ship(path):
        """../../_shared/x → shared/x, ../assets/x → assets/x 로 바꾸고 files 에 싣는다."""
        if path.startswith("../../_shared/"):
            pub = "shared/" + path[len("../../_shared/"):]
            files[pub] = "_shared/" + path[len("../../_shared/"):]
            return pub
        if path.startswith("../assets/"):
            pub = "assets/" + path[len("../assets/"):]
            files[pub] = os.path.relpath(os.path.join(course_dir, "assets", path[len("../assets/"):]), ROOT)
            return pub
        return path

    fix = lambda s: re.sub(r'((?:src|href)=")(\.\./[^"]+)"', lambda m: m.group(1) + ship(m.group(2)) + '"', s)
    links = [fix(l).replace("<link ", "<link data-src ") for l in links]
    deck = fix(deck)
    for f in ("Pretendard-Regular", "Pretendard-Medium", "Pretendard-Bold", "BookkMyungjo-Bold"):
        ship(f"../../_shared/fonts/{f}.woff2")
    ship("../../_shared/vendor/reveal/reveal.js")

    if me.get("date"):
        deck = re.sub(r"(<[^>]*data-course-date[^>]*>)[^<]*(</p>)", lambda m: m.group(1) + me["date"] + m.group(2), deck)
    if course.get("label"):
        deck = re.sub(r"(<[^>]*data-course-label[^>]*>)[^<]*(<)", lambda m: m.group(1) + course["label"] + m.group(2), deck)

    tpl = "".join(f'<script src="{ship(s)}"></script>\n' for s in ext_scripts) + "\n".join(head_scripts) + "\n" + deck
    boot = open(os.path.join(HERE, "boot.js"), encoding="utf8").read()
    editor_css = open(os.path.join(HERE, "editor.css"), encoding="utf8").read()
    meta = {"no": no, "title": me.get("title", course.get("title", "")), "footer": course.get("footer", "")}
    title = f"{no}강 {meta['title']} 편집본"

    page = (
        f"<title data-src>{title}</title>\n" + "\n".join(links) + "\n"
        + "<style data-src>" + "".join(styles) + "</style>\n"
        + "<style data-src>" + editor_css + "</style>\n"
        + '<script type="application/json" id="deck-meta" data-src>' + json.dumps(meta, ensure_ascii=False) + "</script>\n"
        + '<script type="application/json" id="deck-edits">{}</script>\n'
        + '<template id="deck-src" data-src>' + tpl + "</template>\n"
        + '<script id="deck-boot" data-src>' + boot + "</script>\n"
    )
    out_dir = os.path.join(os.environ.get("TMPDIR", tempfile.gettempdir()), "lecture-artifact", name[:-5])
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "index.html")
    open(out, "w", encoding="utf8").write(page)

    tb = [v for v in files.values() if os.path.basename(v).startswith("tb-")]
    print(out)
    if tb:
        print(f"주의: 교재 유래 이미지 {len(tb)}개를 싣는다 (tb-*). 아티팩트는 비공개로 두고 공유 전에 판단받는다.")
    print(json.dumps(files, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
