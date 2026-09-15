/* 고아 줄 검사 — design.md §4.10
 *
 *   _scripts/check-orphans.sh [슬라이드.html ...]
 *
 * 줄 끝에서 한두 글자만 다음 줄로 흘러넘치면 그 줄이 눈에 걸린다.
 * 문단마다 실제로 그려진 줄을 Range.getClientRects() 로 재서,
 * 마지막 줄 폭이 가장 긴 줄의 일정 비율 이하이면 잡아낸다.
 *
 * 눈으로는 매번 놓친다. check-figures.sh 가 그림을 보듯 이쪽은 글줄을 본다.
 *
 * 고치는 순서는 design.md §4.10 대로다 — 문장을 줄인다 → 칸 너비 → 글자 크기.
 */
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const puppeteer = require(process.env.PUPPETEER_PATH || 'puppeteer');

/* 마지막 줄이 이 비율 이하이면 고아로 본다. 한글 기준 두 글자 남짓. */
const RATIO = Number(process.env.ORPHAN_RATIO || 0.16);

const urls = process.argv.slice(2);
if (!urls.length) {
  console.error('사용법: node check-orphans.mjs <url> [url ...]');
  process.exit(2);
}

const browser = await puppeteer.launch({ headless: 'new' });
let problems = 0;

for (const url of urls) {
  const page = await browser.newPage();
  await page.setViewport({ width: 960, height: 540 });
  await page.goto(url, { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 1600));

  const total = await page.evaluate(
    () => document.querySelectorAll('.slides > section').length);

  const found = [];
  for (let i = 0; i < total; i++) {
    await page.evaluate((k) => Reveal.slide(k, 0), i);
    await new Promise((r) => setTimeout(r, 300));
    // 누적 공개까지 펼친 상태로 잰다 — 마지막 단계가 가장 빽빽하다
    await page.evaluate(() => document.querySelectorAll('.present .fragment')
      .forEach((f) => f.classList.add('visible')));
    await new Promise((r) => setTimeout(r, 200));

    const bad = await page.evaluate((ratio) => {
      const out = [];
      const sec = document.querySelector('section.present');
      if (!sec) return out;

      sec.querySelectorAll('p, li, h2, td, th').forEach((el) => {
        if (el.querySelector('p, li, table, svg')) return;   // 잎 노드만 본다
        const txt = el.textContent.replace(/\s+/g, ' ').trim();
        if (!txt) return;

        const r = document.createRange();
        r.selectNodeContents(el);
        const rects = [...r.getClientRects()].filter((x) => x.width > 1 && x.height > 4);
        if (rects.length < 2) return;

        /* 글자 크기가 다른 조각(<span class="en">)이 같은 줄에 있으므로
           top 이 아니라 중심선으로 묶는다. top 으로 묶으면 제목이 오탐이 된다. */
        const H = Math.max(...rects.map((x) => x.height));
        const lines = [];
        rects.forEach((x) => {
          const c = x.top + x.height / 2;
          const l = lines.find((L) => Math.abs(L.c - c) < H * 0.6);
          if (l) { l.left = Math.min(l.left, x.left); l.right = Math.max(l.right, x.right); }
          else lines.push({ c, left: x.left, right: x.right });
        });
        if (lines.length < 2) return;

        const full = Math.max(...lines.map((L) => L.right - L.left));
        const last = lines[lines.length - 1];
        const w = last.right - last.left;
        if (w / full <= ratio) {
          out.push({ tag: el.tagName.toLowerCase(), pct: Math.round((w / full) * 100),
                     lines: lines.length, txt: txt.slice(-46) });
        }
      });
      return out;
    }, RATIO);

    bad.forEach((x) => found.push({ no: i + 1, ...x }));
  }

  const name = decodeURIComponent(url.split('/').pop());
  if (found.length) {
    console.log(`\n✗ ${name}`);
    found.forEach((f) => console.log(
      `   ${f.no}번 슬라이드 ${f.tag} — ${f.lines}줄 중 마지막이 ${f.pct}%  …${f.txt}`));
    problems += found.length;
  } else {
    console.log(`✓ ${name}`);
  }
  await page.close();
}

await browser.close();
console.log(problems ? `\n고아 줄 ${problems}건` : '\n문제 없음');
process.exit(problems ? 1 : 0);
