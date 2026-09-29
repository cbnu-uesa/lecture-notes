/* 강의노트 편집본(아티팩트) 부팅 — _scripts/artifact/build.py 가 페이지에 넣는다.
 * 원본 덱은 <template id="deck-src"> 에 그대로 두고,
 * 교수가 고친 문구만 #deck-edits 에 {순번: {orig, html}} 으로 쌓는다.
 * 저장하면 이 페이지를 통째로 다시 써서 새 판으로 올린다 (artifact 능력). */
(async function () {
  const reset = [...document.head.querySelectorAll('style')].find((s) => !s.hasAttribute('data-src'));
  const SKEL = '<!doctype html><html><head><meta charset=utf8>' +
    '<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">' +
    '<style>' + (reset ? reset.textContent : '') + '</style></head><body>';
  const meta = JSON.parse(document.getElementById('deck-meta').textContent);
  let edits = {};
  try { edits = JSON.parse(document.getElementById('deck-edits').textContent || '{}'); } catch (e) { edits = {}; }

  // ── 고칠 수 있는 글 덩어리를 고른다 ────────────────────────
  // 문단·목록·표 칸처럼 글이 직접 들어 있는 가장 바깥 요소. 그림(svg)·스크립트를 품은 것은 뺀다.
  const TEXT_TAGS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'P', 'LI', 'TD', 'TH', 'DT', 'DD', 'FIGCAPTION', 'BLOCKQUOTE', 'CAPTION']);
  function pick(root) {
    const out = [];
    (function walk(node) {
      for (const el of node.children) {
        if (el.namespaceURI !== 'http://www.w3.org/1999/xhtml') continue;
        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
        if (el.matches('[data-course-date],[data-course-label]')) continue;
        const blocked = el.querySelector('svg,script,canvas,img,table');
        const direct = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
        if (!blocked && (TEXT_TAGS.has(el.tagName) || direct)) { out.push(el); continue; }
        walk(el);
      }
    })(root);
    return out;
  }

  const tpl = document.getElementById('deck-src');
  const frag = tpl.content.cloneNode(true);
  const orig = [];
  let stale = 0;
  pick(frag).forEach((el, i) => {
    orig[i] = el.innerHTML;
    el.setAttribute('data-eid', i);
    const e = edits[i];
    if (e) { if (e.orig === el.innerHTML) el.innerHTML = e.html; else stale++; }
  });
  frag.querySelectorAll('script').forEach((s) => s.setAttribute('type', 'text/x-deck'));
  document.body.appendChild(frag);

  // 덱 안의 스크립트를 원래 순서대로 돌린다 (charts.js → 상수 → 그림)
  const load = (src) => new Promise((r) => {
    const s = document.createElement('script'); s.src = src; s.onload = s.onerror = r; document.body.appendChild(s);
  });
  for (const old of [...document.querySelectorAll('script[type="text/x-deck"]')]) {
    const s = document.createElement('script');
    if (old.getAttribute('src')) {
      await new Promise((r) => { s.onload = s.onerror = r; s.src = old.getAttribute('src'); old.replaceWith(s); });
    } else {
      s.textContent = old.textContent;
      try { old.replaceWith(s); } catch (e) { console.error(e); }
    }
  }
  await load('shared/vendor/reveal/reveal.js');

  // ── deck-init.js 와 같은 크롬 (course.json 대신 #deck-meta) ──
  const sections = document.querySelectorAll('.reveal .slides > section');
  const kick = `${String(meta.no).padStart(2, '0')}. ${meta.title}`;
  sections.forEach((sec) => {
    if (sec.matches('.s-cover, .s-closing, .s-section') || !sec.querySelector('h2')) return;
    const k = document.createElement('p'); k.className = 'kicker'; k.textContent = kick;
    sec.insertBefore(k, sec.firstChild);
  });
  sections.forEach((sec) => {
    if (sec.classList.contains('s-cover')) return;
    const bar = document.createElement('div'); bar.className = 'deck-footer';
    bar.innerHTML = '<span class="ft-text"></span><span class="ft-num"></span>';
    bar.querySelector('.ft-text').textContent = meta.footer;
    sec.appendChild(bar);
  });
  const stepOffset = []; let acc = 0;
  sections.forEach((sec, i) => {
    stepOffset[i] = acc;
    const idx = [...sec.querySelectorAll('.fragment')].map((f) =>
      f.hasAttribute('data-fragment-index') ? +f.dataset.fragmentIndex : null);
    acc += 1 + new Set(idx.filter((v) => v !== null)).size + idx.filter((v) => v === null).length;
  });
  function paintPageNumber() {
    const { h, f } = Reveal.getIndices();
    const el = Reveal.getCurrentSlide().querySelector('.ft-num');
    if (el) el.textContent = String(stepOffset[h] + (f === undefined || f < 0 ? 0 : f + 1) + 1);
  }
  await Reveal.initialize({
    width: 960, height: 540, margin: 0, minScale: 0.2, maxScale: 2.0,
    hash: true, controls: false, progress: false, slideNumber: false,
    transition: 'none', backgroundTransition: 'none', fragmentInURL: true,
  });
  ['ready', 'slidechanged', 'fragmentshown', 'fragmenthidden'].forEach((ev) => Reveal.on(ev, paintPageNumber));
  paintPageNumber();

  // ── 편집 ──────────────────────────────────────────────────
  const live = [...document.querySelectorAll('.reveal [data-eid]')];
  const clean = (html) => {
    const d = document.createElement('div'); d.innerHTML = html;
    d.querySelectorAll('*').forEach((n) => {
      n.removeAttribute('contenteditable'); n.removeAttribute('spellcheck'); n.removeAttribute('data-dirty');
      if (n.classList) { n.classList.remove('visible', 'current-fragment'); if (!n.classList.length) n.removeAttribute('class'); }
    });
    return d.innerHTML;
  };
  const base = {};
  live.forEach((el) => { base[el.dataset.eid] = clean(el.innerHTML); });

  const bar = document.createElement('div');
  bar.className = 'ed-bar';
  bar.innerHTML = '<button type="button" id="ed-toggle">편집</button>' +
    '<span class="ed-status" id="ed-status"></span>' +
    '<button type="button" id="ed-undo" hidden>고친 것 버리기</button>' +
    '<button type="button" id="ed-save" class="primary" hidden>저장</button>';
  document.body.appendChild(bar);
  const $ = (id) => document.getElementById(id);
  const saved = Object.keys(edits).length;
  function status(msg, warn) {
    const s = $('ed-status');
    if (msg) { s.textContent = msg; s.classList.toggle('warn', !!warn); return; }
    const n = live.filter((el) => el.hasAttribute('data-dirty')).length;
    s.textContent = (n ? `저장 안 한 곳 ${n}` : '') + (n && saved ? ' · ' : '') + (saved ? `저장된 수정 ${saved}곳` : '') +
      (stale ? ` · 원본이 바뀌어 적용 못 한 수정 ${stale}` : '');
    s.classList.toggle('warn', !!stale);
    $('ed-save').disabled = !n; $('ed-undo').disabled = !n;
  }

  const artifact = window.claude ? await window.claude.use('artifact') : null;
  if (!artifact) { $('ed-toggle').hidden = true; bar.hidden = !saved; status(saved ? `저장된 수정 ${saved}곳 (보기 전용)` : ''); return; }

  let editing = false;
  $('ed-toggle').addEventListener('click', () => {
    editing = !editing;
    document.body.classList.toggle('deck-editing', editing);
    live.forEach((el) => { if (editing) { el.contentEditable = 'true'; el.spellcheck = false; } else el.removeAttribute('contenteditable'); });
    $('ed-toggle').textContent = editing ? '편집 끝' : '편집';
    $('ed-save').hidden = $('ed-undo').hidden = !editing;
    status();
  });
  document.addEventListener('input', (ev) => {
    const el = ev.target.closest && ev.target.closest('[data-eid]'); if (!el) return;
    el.toggleAttribute('data-dirty', clean(el.innerHTML) !== base[el.dataset.eid]);
    status();
  });
  // 붙여넣기는 글자만, Enter 는 줄바꿈(<br>) — 문단이 <div> 로 쪼개지지 않게
  document.addEventListener('paste', (ev) => {
    if (!ev.target.closest || !ev.target.closest('[data-eid]')) return;
    ev.preventDefault();
    document.execCommand('insertText', false, (ev.clipboardData || window.clipboardData).getData('text/plain'));
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && ev.target.closest && ev.target.closest('[data-eid]')) {
      ev.preventDefault(); document.execCommand('insertLineBreak');
    }
  });
  $('ed-undo').addEventListener('click', () => {
    live.forEach((el) => { if (el.hasAttribute('data-dirty')) { el.innerHTML = base[el.dataset.eid]; el.removeAttribute('data-dirty'); } });
    status();
  });
  $('ed-save').addEventListener('click', async () => {
    const next = { ...edits };
    live.forEach((el) => {
      if (!el.hasAttribute('data-dirty')) return;
      const i = el.dataset.eid, html = clean(el.innerHTML);
      if (html === clean(orig[i])) delete next[i]; else next[i] = { orig: orig[i], html };
    });
    let out = SKEL;
    document.querySelectorAll('[data-src]').forEach((el) => {
      out += el.outerHTML + '\n';
      if (el.id === 'deck-meta') {
        out += '<script type="application/json" id="deck-edits">' +
          JSON.stringify(next).replace(/</g, '\\u003c') + '</scr' + 'ipt>\n';
      }
    });
    out += '</body></html>';
    $('ed-save').disabled = true; status('저장 중…');
    try {
      await artifact.publish(out);
      status('저장했습니다. 새 판으로 다시 엽니다.');
    } catch (e) {
      const code = e && e.code;
      if (code === 'conflict') status('다른 창에서 먼저 저장했습니다. 그 판으로 다시 엽니다.', true);
      else if (code === 'not_granted' || code === 'not_writer') status('이 계정은 보기만 할 수 있어 저장하지 못했습니다.', true);
      else { status('저장하지 못했습니다: ' + (e && e.message || e), true); $('ed-save').disabled = false; }
    }
  });
  status();
})();
