/* Reveal 초기화 + 슬라이드 크롬(푸터바·페이지번호·다운로드) 주입
 * design.md §2.1, §4.1
 *
 * 강의노트 HTML은 이 파일 하나만 부르면 된다. 과목 메타는 ../course.json에서 읽으므로
 * 슬라이드에 과목명·학기를 하드코딩하지 않는다 (CLAUDE.md 참조).
 */

(async function () {
  const root = document.currentScript
    ? new URL('..', document.currentScript.src)
    : new URL('../', location.href);

  // ── 과목 메타 ──────────────────────────────────────────────
  // slides/NN-x.html 기준으로 ../course.json. file://에서는 fetch가 막히므로
  // 실패해도 슬라이드 자체는 뜨게 둔다.
  let course = {};
  try {
    const res = await fetch('../course.json');
    if (res.ok) course = await res.json();
  } catch (e) {
    console.warn('[deck] course.json을 읽지 못했습니다. _scripts/serve.sh로 여십시오.', e);
  }

  const deck = document.querySelector('.reveal');
  const sections = deck.querySelectorAll('.slides > section');

  // ── 표지 라벨 ("2026-1학기 도시경제학입문") ────────────────
  document.querySelectorAll('[data-course-label]').forEach((el) => {
    if (course.label) el.textContent = course.label;
  });

  // ── 푸터바 주입 ────────────────────────────────────────────
  // 표지(.s-cover)에는 넣지 않는다.
  const footerText = course.footer || '';
  sections.forEach((sec) => {
    if (sec.classList.contains('s-cover')) return;
    const bar = document.createElement('div');
    bar.className = 'deck-footer';
    bar.innerHTML = '<span class="ft-text"></span><span class="ft-num"></span>';
    bar.querySelector('.ft-text').textContent = footerText;
    sec.appendChild(bar);
  });

  // ── 페이지 번호 ────────────────────────────────────────────
  // 슬라이드가 아니라 "단계"를 센다. 누적 공개 한 단계가 PDF 한 쪽이 되므로
  // (design.md §8) 이렇게 해야 화면 번호와 PDF 쪽 번호가 일치한다.
  const stepOffset = [];
  let acc = 0;
  sections.forEach((sec, i) => {
    stepOffset[i] = acc;
    const idx = [...sec.querySelectorAll('.fragment')].map((f) =>
      f.hasAttribute('data-fragment-index') ? +f.dataset.fragmentIndex : null
    );
    // 인덱스가 붙은 것은 같은 값끼리 한 단계, 안 붙은 것은 각자 한 단계
    const numbered = new Set(idx.filter((v) => v !== null));
    const unnumbered = idx.filter((v) => v === null).length;
    acc += 1 + numbered.size + unnumbered;
  });

  function paintPageNumber() {
    const { h, f } = Reveal.getIndices();
    const n = stepOffset[h] + (f === undefined || f < 0 ? 0 : f + 1) + 1;
    const el = Reveal.getCurrentSlide().querySelector('.ft-num');
    if (el) el.textContent = String(n);
  }

  // ── 다운로드 버튼 ──────────────────────────────────────────
  // 이 슬라이드와 같은 이름의 PDF를 가리킨다: slides/02-x.html → pdf/02-x.pdf
  // ?export=1 은 PDF 빌드용 헤드리스 브라우저가 붙이는 표시다. 그때는 버튼을 만들지 않는다
  // (안 그러면 버튼이 PDF 모든 쪽에 찍힌다).
  const exporting = new URLSearchParams(location.search).has('export');
  const base = location.pathname.split('/').pop().replace(/\.html?$/, '');
  if (base && !exporting) {
    const a = document.createElement('a');
    a.className = 'deck-download';
    a.href = '../pdf/' + base + '.pdf';
    // base는 URL 인코딩된 상태다. href에는 그대로 쓰고,
    // 내려받는 파일 이름은 디코딩해 한글이 %EC%88%98… 로 저장되지 않게 한다.
    a.setAttribute('download', decodeURIComponent(base) + '.pdf');
    a.textContent = 'PDF 내려받기';
    document.body.appendChild(a);
    // PDF가 아직 빌드되지 않았으면 버튼을 감춘다
    fetch(a.href, { method: 'HEAD' })
      .then((r) => { if (!r.ok) a.hidden = true; })
      .catch(() => { a.hidden = true; });
  }

  // ── Reveal ────────────────────────────────────────────────
  Reveal.initialize({
    // design.md §2.1 — PPT의 pt와 CSS px를 1:1로 맞춘다
    width: 960,
    height: 540,
    margin: 0,
    minScale: 0.2,
    maxScale: 2.0,

    hash: true,
    controls: false,
    progress: false,
    slideNumber: false,        // 푸터바에서 직접 그린다
    transition: 'none',        // design.md §11
    backgroundTransition: 'none',
    fragmentInURL: true,

    // PDF: fragment 단계마다 페이지를 분리해 기존 PPT 출력과 장수를 맞춘다 (design.md §8)
    pdfSeparateFragments: true,
    pdfMaxPagesPerSlide: 1,

    plugins: [RevealNotes, RevealMath.MathJax3],

    // MathJax 3의 tex-svg 번들은 파일 하나로 완결된다.
    // (4는 음성 보조용 sre/ 파일 수백 개를 워커로 따로 불러오므로 쓰지 않는다 —
    //  Drive 폴더에 파일을 늘리지 않는다는 CLAUDE.md 제약 때문)
    // SVG 출력이라 PDF에서 벡터로 남는다 (design.md §7).
    mathjax3: {
      mathjax: root.href + 'vendor/mathjax-tex-svg.js',
      tex: {
        inlineMath: [['$', '$'], ['\\(', '\\)']],
        displayMath: [['$$', '$$'], ['\\[', '\\]']],
      },
      options: {
        // 개념도 SVG 안의 텍스트는 수식으로 처리하지 않는다
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'svg'],
      },
    },
  });

  // 번호는 초기 표시 후 슬라이드·단계가 바뀔 때마다 다시 그린다
  ['ready', 'slidechanged', 'fragmentshown', 'fragmenthidden'].forEach((ev) =>
    Reveal.on(ev, paintPageNumber)
  );
})();
