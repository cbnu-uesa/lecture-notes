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
