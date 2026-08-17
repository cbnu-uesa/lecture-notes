/* 그래프 자동 검사 — design.md §6.4
 *
 *   _scripts/check-figures.sh [슬라이드.html ...]
 *
 * 헤드리스 브라우저로 슬라이드를 열어 두 가지를 잰다.
 *   1. 좌표점이 곡선에서 벗어났는가        (charts.js의 자체검사 경고를 수집)
 *   2. 그래프 안의 글자가 캔버스를 넘어갔는가 (viewBox 밖으로 잘리는 라벨)
 *
 * 눈으로는 놓치기 쉬운 것들이라 빌드 전에 기계로 한 번 걸러낸다.
 */
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const puppeteer = require(process.env.PUPPETEER_PATH || 'puppeteer');

const urls = process.argv.slice(2);
if (!urls.length) {
  console.error('사용법: node check-figures.mjs <url> [url ...]');
  process.exit(2);
}

const browser = await puppeteer.launch({ headless: 'new' });
let problems = 0;

for (const url of urls) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900 });

  const warnings = [];
  page.on('console', (m) => {
    const t = m.text();
    if (t.includes('[Fig]')) warnings.push(t);
  });
  page.on('pageerror', (e) => warnings.push('페이지 오류: ' + e.message));

  await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 1500));

  // 글자가 viewBox 밖으로 나갔는지 / 채움 영역 밖으로 삐져나왔는지
  const overflow = await page.evaluate(() => {
    const out = [];

    // 점이 다각형 안에 있는가 (ray casting)
    const inside = ([px, py], poly) => {
      let hit = false;
      for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [xi, yi] = poly[i], [xj, yj] = poly[j];
        if ((yi > py) !== (yj > py) &&
            px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) hit = !hit;
      }
      return hit;
    };

    for (const svg of document.querySelectorAll('svg.fig')) {
      const vb = svg.viewBox.baseVal;
      if (!vb || !vb.width) continue;
      const id = svg.id || '(id 없음)';

      for (const t of svg.querySelectorAll('text')) {
        let b;
        try { b = t.getBBox(); } catch (e) { continue; }
        if (!b.width) continue;
        const label = (t.textContent || '').replace(/\s+/g, ' ').slice(0, 24);

        if (b.x < vb.x - 1 || b.y < vb.y - 1 ||
            b.x + b.width > vb.x + vb.width + 1 ||
            b.y + b.height > vb.y + vb.height + 1) {
          out.push(`${id}: "${label}" 가 캔버스를 벗어남`);
        }

        // labelIn()으로 넣은 라벨은 지정한 영역 안에 완전히 들어가야 한다
        const spec = t.getAttribute('data-in-poly');
        if (spec) {
          const poly = spec.trim().split(/\s+/).map((p) => p.split(',').map(Number));
          const corners = [
            [b.x, b.y], [b.x + b.width, b.y],
            [b.x, b.y + b.height], [b.x + b.width, b.y + b.height],
          ];
          const outside = corners.filter((c) => !inside(c, poly)).length;
          if (outside) {
            out.push(`${id}: "${label}" 가 채움 영역 밖으로 ${outside}/4 모서리 삐져나옴`);
          }
        }
      }
    }
    // ── 본문이 푸터를 넘었는가 ────────────────────────────────
    // 표·그림이 푸터선과 겹치면 강의실에서도 PDF 에서도 잘려 보인다.
    // 눈으로는 50쪽을 다 못 보므로 여기서 기계로 잡는다.
    document.querySelectorAll('.reveal .slides > section').forEach((sec, i) => {
      const foot = sec.querySelector('.deck-footer');
      if (!foot) return;                       // 표지·마무리에는 푸터가 없다
      const sr = sec.getBoundingClientRect();
      if (!sr.height) return;
      const scale = sr.height / 540;           // reveal 이 확대해 놓은 배율
      const limit = foot.getBoundingClientRect().top - sr.top;
      const body = sec.querySelector('.body');
      if (!body) return;
      const seen = new Set();
      body.querySelectorAll('table, svg.fig, img, ul, ol, p, div').forEach((el) => {
        const r = el.getBoundingClientRect();
        if (!r.height) return;
        const over = (r.bottom - sr.top) - limit;
        if (over <= 2 * scale) return;
        const tag = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '');
        if (seen.has(tag)) return;
        seen.add(tag);
        out.push(`${i + 1}번 슬라이드: ${tag} 가 푸터를 ${Math.round(over / scale)}px 넘었습니다`);
      });
    });

    // ── 한 그림 안에서 뜻이 다른 곡선이 같은 색인가 ──────────
    // design.md §3.3 의 기계 판정판. variant 가 달라도 토큰 값이 같아지면
    // (예: --accent-blue 와 --chart-blue 는 같은 #1F5C8B) 두 곡선이 겹쳐 보인다.
    // 같은 variant 의 다발(예산선 3개, 이동 전/후 파선)은 class 가 같아서 걸리지 않는다.
    {
      const secs = [...document.querySelectorAll('.reveal .slides > section')];
      document.querySelectorAll('svg.fig').forEach((svg) => {
        const no = secs.indexOf(svg.closest('section')) + 1;
        const byColor = new Map();
        svg.querySelectorAll('[class*="curve"]').forEach((el) => {
          const cls = [...el.classList].filter((c) => c.startsWith('curve')).join('.');
          if (!cls) return;
          const col = getComputedStyle(el).stroke;
          if (!byColor.has(col)) byColor.set(col, new Set());
          byColor.get(col).add(cls);
        });
        for (const [col, set] of byColor) {
          if (set.size > 1) {
            out.push(`${no}번 슬라이드: ${svg.id ? 'svg#' + svg.id : 'svg'} — ` +
                     `${[...set].join(' / ')} 가 같은 색 ${col} 입니다`);
          }
        }
      });
    }

    return out;
  });

  const name = decodeURIComponent(url.split('/').pop());
  const all = [...warnings, ...overflow];
  if (all.length) {
    console.log(`\n✗ ${name}`);
    all.forEach((w) => console.log('   ' + w.replace(/^\[Fig\]\s*/, '')));
    problems += all.length;
  } else {
    console.log(`✓ ${name}`);
  }
  await page.close();
}

await browser.close();
console.log(problems ? `\n문제 ${problems}건` : '\n문제 없음');
process.exit(problems ? 1 : 0);
