/* 개념도 SVG 빌더 — design.md §6
 *
 * 기존 강의노트의 곡선은 실측 데이터가 아니라 손으로 그린 개념도다.
 * 차트 라이브러리를 쓰면 축·격자·범례가 딸려 나와 원본과 달라지므로 SVG로 직접 그린다.
 * 실측 데이터 그래프는 Chart.js를 쓴다 (design.md §6.3).
 *
 * 사용법
 *   <svg class="fig" id="f1" viewBox="0 0 440 300" role="img"><title>수요곡선의 도출</title></svg>
 *   <script>
 *     Fig.draw('#f1', {
 *       axes: { x: '수요량(통/월)', y: '가격(천원)' },
 *       parts: [
 *         Fig.curve(Fig.convex(), { fragment: 0 }),
 *         Fig.guide(150, 120, { xtick: '12', ytick: '20', fragment: 0 }),
 *         Fig.dot(150, 120, { fragment: 0 }),
 *         Fig.annot(200, 96, '→ 한계편익(marginal benefit)', { tone: 'blue', fragment: 1 }),
 *       ],
 *     });
 *   </script>
 *
 * 좌표는 SVG 사용자 단위다. 기본 플롯 영역은 x 55…410, y 25…255 (원점 55,255).
 * 크기가 다른 그림은 const F = Fig.withBox({x0,y0,x1,y1}) 로 같은 API를 새 기하에 묶어 쓴다.
 * 어떤 part에도 { fragment: n }을 주면 누적 공개 단계가 된다 (design.md §8).
 */

window.Fig = (function () {
  const DEFAULT_BOX = { x0: 55, y0: 255, x1: 410, y1: 25 };

  const esc = (s) =>
    String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const round = (v) => Math.round(v * 10) / 10;

  /* class 속성 + 누적 공개 속성 (design.md §8) */
  function attrs(cls, o = {}) {
    const isFrag = o.fragment !== undefined && o.fragment !== null;
    const klass = isFrag ? `${cls} fragment fade-in` : cls;
    const idx = isFrag ? ` data-fragment-index="${o.fragment}"` : '';
    return `class="${klass}"${idx}`;
  }

  /* ── 곡선 경로 ───────────────────────────────────────────
   * 단조 3차 보간(Fritsch–Carlson PCHIP).
   *
   * 데이터 점을 하나도 빠짐없이 정확히 지나면서 매끄럽다.
   * 예전에 쓰던 Catmull-Rom은 점 간격이 고르지 않으면(8→12→16→22→29)
   * 구간마다 장력이 달라져 곡선이 출렁였다. PCHIP은 기울기를 조화평균으로
   * 잡아 단조성을 보장하므로 넘침도 꺾임도 생기지 않는다.
   * 수요·공급곡선처럼 한 방향으로만 가는 데이터에 맞는 방식이다.
   *
   * x가 증가하지 않는 점묶음(세로선 등)은 Catmull-Rom으로 되돌린다. */
  function path(pts) {
    if (pts.length < 2) return '';
    if (pts.length === 2)
      return `M${pts[0][0]},${pts[0][1]} L${pts[1][0]},${pts[1][1]}`;

    const strictlyIncreasing = pts.every((p, i) => i === 0 || p[0] > pts[i - 1][0]);
    return strictlyIncreasing ? monotonePath(pts) : catmullRomPath(pts);
  }

  function monotonePath(pts) {
    const n = pts.length;
    const h = [], D = [];
    for (let i = 0; i < n - 1; i++) {
      h[i] = pts[i + 1][0] - pts[i][0];
      D[i] = (pts[i + 1][1] - pts[i][1]) / h[i];
    }
    // 각 점의 기울기 — 방향이 바뀌는 곳은 0으로 눌러 넘침을 막는다
    const m = [D[0]];
    for (let i = 1; i < n - 1; i++) {
      if (D[i - 1] * D[i] <= 0) {
        m[i] = 0;
      } else {
        const w1 = 2 * h[i] + h[i - 1];
        const w2 = h[i] + 2 * h[i - 1];
        m[i] = (w1 + w2) / (w1 / D[i - 1] + w2 / D[i]);
      }
    }
    m[n - 1] = D[n - 2];

    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < n - 1; i++) {
      const t = h[i] / 3;
      const c1 = [pts[i][0] + t, pts[i][1] + m[i] * t];
      const c2 = [pts[i + 1][0] - t, pts[i + 1][1] - m[i + 1] * t];
      d += ` C${round(c1[0])},${round(c1[1])} ${round(c2[0])},${round(c2[1])} ${pts[i + 1][0]},${pts[i + 1][1]}`;
    }
    return d;
  }

  function catmullRomPath(pts) {
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2] || p2;
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += ` C${round(c1[0])},${round(c1[1])} ${round(c2[0])},${round(c2[1])} ${p2[0]},${p2[1]}`;
    }
    return d;
  }

  /* 점 묶음 평행 이동 — 곡선의 이동 (2강 p.6, p.12) */
  function shift(pts, dx, dy) {
    return pts.map(([x, y]) => [round(x + dx), round(y + (dy || 0))]);
  }

  /* ── 곡선 위의 점 찾기 ───────────────────────────────────
   * 좌표를 손으로 찍으면 곡선에서 벗어난다. 점·보조선은 반드시 이걸로 구한다.
   *   at(pts, {x: 168})  → [168, 곡선의 y]
   *   at(pts, {y: 108})  → [곡선의 x, 108]
   * 구간을 벗어나면 가장 가까운 끝점을 준다. */
  function at(pts, q) {
    const byX = q.x !== undefined;
    const v = byX ? q.x : q.y;
    const i0 = byX ? 0 : 1, i1 = byX ? 1 : 0;
    let best = null, bestGap = Infinity;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      const lo = Math.min(a[i0], b[i0]), hi = Math.max(a[i0], b[i0]);
      if (v >= lo && v <= hi) {
        const span = b[i0] - a[i0];
        const t = span === 0 ? 0 : (v - a[i0]) / span;
        const other = a[i1] + (b[i1] - a[i1]) * t;
        return byX ? [round(v), round(other)] : [round(other), round(v)];
      }
      const gap = v < lo ? lo - v : v - hi;
      if (gap < bestGap) { bestGap = gap; best = v < lo ? a : b; }
    }
    return [round(best[0]), round(best[1])];
  }

  const MARKERS = `<defs>
    <marker id="ah-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#1A1A1A"/></marker>
    <marker id="ah-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#FF0000"/></marker>
    <marker id="ah-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#0328C3"/></marker>
  </defs>`;

  /* ── 라벨을 채움 영역 안으로 밀어넣는다 ────────────────────
   * labelIn()은 다각형 무게중심에 라벨을 놓지만, 두 줄짜리 라벨은
   * 삼각형 빗변을 넘어 삐져나오기 쉽다. 글자 상자를 실제로 재서
   * 네 모서리가 모두 안에 들어올 때까지 조금씩 옮긴다.
   * 브라우저에서 그린 뒤에만 잴 수 있으므로 draw() 끝에서 한 번 돈다. */
  function pointInPoly([px, py], poly) {
    let hit = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > py) !== (yj > py) &&
          px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) hit = !hit;
    }
    return hit;
  }

  function fitLabels(svg) {
    svg.querySelectorAll('text[data-in-poly]').forEach((t) => {
      const poly = t.getAttribute('data-in-poly').trim().split(/\s+/)
        .map((p) => p.split(',').map(Number));
      // 글자 상자를 여유분만큼 부풀려서 검사한다. 상자를 줄여서 재면
      // 아슬아슬하게 걸친 것도 '들어왔다'고 판정해 check-figures.sh 와 어긋난다.
      const margin = 2;
      const search = (b) => {
        const fits = (dx, dy) => {
          const x1 = b.x + dx - margin, x2 = b.x + b.width + dx + margin;
          const y1 = b.y + dy - margin, y2 = b.y + b.height + dy + margin;
          return pointInPoly([x1, y1], poly) && pointInPoly([x2, y1], poly) &&
                 pointInPoly([x1, y2], poly) && pointInPoly([x2, y2], poly);
        };
        if (fits(0, 0)) return [0, 0];
        let best = null, bestD = Infinity;
        for (let dx = -60; dx <= 60; dx += 2) {
          for (let dy = -50; dy <= 50; dy += 2) {
            const d = dx * dx + dy * dy;
            if (d >= bestD || !fits(dx, dy)) continue;
            best = [dx, dy]; bestD = d;
          }
        }
        return best;
      };

      const base = parseFloat(getComputedStyle(t).fontSize) || 14;
      const lh0 = t.querySelector('tspan[dy]')
        ? parseFloat(t.querySelector('tspan[dy]').getAttribute('dy')) : 0;

      // 자리를 옮겨서 안 되면 글자를 한 단계씩 줄여 본다 (design.md §6.6)
      for (let size = base; size >= 10; size -= 1) {
        if (size !== base) {
          t.style.fontSize = size + 'px';
          if (lh0) t.querySelectorAll('tspan[dy]').forEach(
            (sp) => sp.setAttribute('dy', (lh0 * size) / base));
        }
        let b;
        try { b = t.getBBox(); } catch (e) { return; }
        if (!b.width) return;

        const best = search(b);
        if (best) {
          // transform 대신 좌표를 직접 옮긴다 — 그래야 getBBox()가 옮긴 자리를
          // 그대로 돌려주고, check-figures.sh 가 따로 보정할 필요가 없다.
          const [dx, dy] = best;
          t.setAttribute('x', +t.getAttribute('x') + dx);
          t.setAttribute('y', +t.getAttribute('y') + dy);
          t.querySelectorAll('tspan').forEach((sp) => {
            if (sp.hasAttribute('x')) sp.setAttribute('x', +sp.getAttribute('x') + dx);
          });
          return;
        }
      }
      console.warn(
        `[Fig] "${(t.textContent || '').replace(/\s+/g, ' ')}" 라벨이 채움 영역보다 큽니다 — ` +
        `${svg.id || '(id 없음)'}. 영역을 넓히거나 라벨을 밖으로 빼십시오.`
      );
    });
  }

  /* ── 자체 검사: 좌표점이 곡선 위에 있는가 ─────────────────
   * 손으로 찍은 좌표는 곡선에서 벗어나기 쉽고, 눈으로는 놓치기 쉽다.
   * 그릴 때마다 각 점에서 가장 가까운 곡선까지의 거리를 재서 어긋나면 콘솔에 알린다.
   * 화면에는 아무 영향이 없다 — 고칠 수 있게 알려줄 뿐이다.  (design.md §6.4) */
  const TOL = 2.5; // px

  function checkDots(svg) {
    let curves;
    try {
      curves = [...svg.querySelectorAll('path.curve')];
      if (!curves.length) return;
    } catch (e) { return; }

    const samples = curves.map((p) => {
      const out = [];
      try {
        const L = p.getTotalLength();
        if (!L) return out;
        const n = Math.max(24, Math.min(240, Math.round(L / 3)));
        for (let i = 0; i <= n; i++) {
          const pt = p.getPointAtLength((L * i) / n);
          out.push([pt.x, pt.y]);
        }
      } catch (e) { /* 레이아웃 전이면 건너뛴다 */ }
      return out;
    }).filter((s) => s.length);
    if (!samples.length) return;

    svg.querySelectorAll('circle.dot, circle.dot-open').forEach((c) => {
      const cx = +c.getAttribute('cx'), cy = +c.getAttribute('cy');
      let min = Infinity;
      for (const s of samples)
        for (const [x, y] of s) {
          const d = Math.hypot(x - cx, y - cy);
          if (d < min) min = d;
        }
      if (min > TOL) {
        console.warn(
          `[Fig] 점이 곡선에서 ${min.toFixed(1)}px 벗어났습니다 — ` +
          `${svg.id || '(id 없음)'} (${cx}, ${cy}). ` +
          `Fig.scale() 또는 Fig.dot(x, y, { on: 곡선 })으로 곡선에서 좌표를 구하십시오.`
        );
      }
    });
  }

  /* ── 주어진 플롯 기하에 API를 묶는다 ─────────────────────── */
  function make(BOX) {
    /* 데이터 좌표 → 픽셀 (design.md §6.2)
     *
     * 표가 있는 그래프는 **반드시 이걸 쓴다.** 곡선·눈금·점을 같은 수에서 뽑아야
     * 서로 어긋나지 않는다. 손으로 픽셀을 찍으면 반드시 틀어진다.
     *
     *   const S = Fig.scale({ x: [0, 32], y: [0, 30] });
     *   const D = S.curve([[8,25],[12,20],[16,15],[22,10],[29,5]]);
     *   Fig.curve(D)
     *   Fig.dot(...S.p([12, 20]))
     *   Fig.guide(...S.p([12, 20]), { xtick: '12', ytick: '20' })
     */
    function scale(opts) {
      const [xa, xb] = opts.x, [ya, yb] = opts.y;
      const px = (v) => round(BOX.x0 + ((v - xa) / (xb - xa)) * (BOX.x1 - BOX.x0));
      const py = (v) => round(BOX.y0 - ((v - ya) / (yb - ya)) * (BOX.y0 - BOX.y1));
      return {
        x: px,
        y: py,
        p: ([x, y]) => [px(x), py(y)],
        curve: (data) => data.map(([x, y]) => [px(x), py(y)]),
      };
    }

    /* 원점에 볼록, 우하향 — 수요곡선·무차별곡선 */
    function convex(o = {}) {
      const x0 = o.x0 ?? BOX.x0 + 40;
      const x1 = o.x1 ?? BOX.x1 - 20;
      const yTop = o.yTop ?? BOX.y1 + 25;
      const yBot = o.yBot ?? BOX.y0 - 30;
      const k = o.bow ?? 0.28; // 작을수록 더 휜다
      const n = o.n ?? 24;
      const pts = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        const y = yTop + (yBot - yTop) * (t / (t + k)) * (1 + k);
        pts.push([round(x0 + (x1 - x0) * t), round(Math.min(y, yBot))]);
      }
      return pts;
    }

    /* 우상향, 원점에 오목 — 공급곡선 */
    function upward(o = {}) {
      const x0 = o.x0 ?? BOX.x0 + 30;
      const x1 = o.x1 ?? BOX.x1 - 20;
      const yBot = o.yBot ?? BOX.y0 - 20;
      const yTop = o.yTop ?? BOX.y1 + 20;
      const n = o.n ?? 20;
      const pts = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        pts.push([
          round(x0 + (x1 - x0) * t),
          round(yBot - (yBot - yTop) * Math.pow(t, 2.1)),
        ]);
      }
      return pts;
    }

    function curve(pts, o = {}) {
      const cls = 'curve' + (o.variant ? ' curve-' + o.variant : '');
      return `<path ${attrs(cls, o)} d="${path(pts)}"/>`;
    }

    function line(x1, y1, x2, y2, o = {}) {
      const cls = 'curve' + (o.variant ? ' curve-' + o.variant : '');
      return `<path ${attrs(cls, o)} d="M${x1},${y1} L${x2},${y2}"/>`;
    }

    /* 점선 보조선 + 축 눈금값. x·y 중 필요한 쪽만 눈금을 준다.
       only: 'x' | 'y' 로 한쪽 다리만 그릴 수 있다.
       on: 곡선 점묶음을 주면 y(또는 x)를 곡선에서 구해 맞춘다. */
    function guide(x, y, o = {}) {
      if (o.on) [x, y] = at(o.on, y === undefined || y === null ? { x } : { x });
      let d;
      if (o.only === 'y')      d = `M${BOX.x0},${y} L${x},${y}`;
      else if (o.only === 'x') d = `M${x},${y} L${x},${BOX.y0}`;
      else                     d = `M${BOX.x0},${y} L${x},${y} L${x},${BOX.y0}`;
      let s = `<g ${attrs('g-guide', o)}>`;
      s += `<path class="guide" d="${d}"/>`;
      if (o.ytick !== undefined)
        s += `<text class="tick" x="${BOX.x0 - 8}" y="${y + 4}" text-anchor="end">${esc(o.ytick)}</text>`;
      if (o.xtick !== undefined)
        s += `<text class="tick" x="${x}" y="${BOX.y0 + 17}" text-anchor="middle">${esc(o.xtick)}</text>`;
      return s + '</g>';
    }

    /* 좌표점. on: 곡선 점묶음을 주면 그 곡선 위로 스냅한다 (design.md §6.4) */
    function dot(x, y, o = {}) {
      if (o.on) [x, y] = at(o.on, { x });
      const cls = 'dot' + (o.open ? ' dot-open' : '');
      let s = `<g ${attrs('g-dot', o)}>`;
      s += `<circle class="${cls}" cx="${x}" cy="${y}" r="${o.r ?? 4.5}"/>`;
      if (o.label)
        s += `<text class="annot" x="${x + (o.lx ?? 7)}" y="${y + (o.ly ?? -7)}">${esc(o.label)}</text>`;
      return s + '</g>';
    }

    /* 주석. tone: 'red' | 'blue' | 없으면 검정. 줄바꿈은 \n */
    function annot(x, y, text, o = {}) {
      const cls = 'annot' + (o.tone ? ' ' + o.tone : '');
      const anchor = o.anchor ? ` text-anchor="${o.anchor}"` : '';
      const size = o.size ? ` style="font-size:${o.size}px"` : '';
      const tspans = String(text)
        .split('\n')
        .map((l, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : (o.lh ?? 16)}">${esc(l)}</tspan>`)
        .join('');
      return `<text ${attrs(cls, o)} x="${x}" y="${y}"${anchor}${size}>${tspans}</text>`;
    }

    function arrow(x1, y1, x2, y2, o = {}) {
      const cls = 'arrow' + (o.tone ? ' ' + o.tone : '');
      return `<path ${attrs(cls, o)} d="M${x1},${y1} L${x2},${y2}" marker-end="url(#ah-${o.tone || 'ink'})"/>`;
    }

    /* 임의의 SVG 조각을 그대로 넣는다 (채움 영역, 막대 등) */
    function raw(svg, o = {}) {
      return `<g ${attrs('g-raw', o)}>${svg}</g>`;
    }

    /* 채움 영역 안에 라벨을 넣는다 (design.md §6.6)
     *
     *   Fig.labelIn(삼각형, '소비자\n잉여', { tone: 'red' })
     *
     * 다각형의 무게중심에 가운데 정렬로 놓는다. 좌표를 눈으로 찍으면
     * 두 줄짜리 라벨이 빗변을 넘어 삼각형 밖으로 삐져나오기 쉽다.
     * 넘쳤는지는 check-figures.sh 가 글자 상자의 네 모서리로 검사한다. */
    function labelIn(poly, text, o = {}) {
      let cx = 0, cy = 0;
      for (const [x, y] of poly) { cx += x; cy += y; }
      cx = round(cx / poly.length + (o.dx || 0));
      cy = round(cy / poly.length + (o.dy || 0));

      const lines = String(text).split('\n');
      const lh = o.lh ?? 18;
      const top = cy - ((lines.length - 1) * lh) / 2;
      const cls = 'annot' + (o.tone ? ' ' + o.tone : '');
      const size = o.size ? ` style="font-size:${o.size}px"` : '';
      const tspans = lines
        .map((l, i) => `<tspan x="${cx}" dy="${i === 0 ? 0 : lh}">${esc(l)}</tspan>`)
        .join('');
      const region = poly.map(([x, y]) => `${x},${y}`).join(' ');
      return `<text ${attrs(cls, o)} x="${cx}" y="${round(top)}" text-anchor="middle"` +
             `${size} data-in-poly="${region}">${tspans}</text>`;
    }

    /* 막대그래프 — 각 막대의 가로 중앙을 곡선이 지나야 한다 (design.md §6.7).
     * values[i]는 i번째 막대(구간 i…i+1)의 높이. 반환값의 mid는 그 중앙점들이므로
     * 그대로 Fig.curve(mid)로 넘기면 선이 막대 꼭대기 한가운데를 지난다. */
    function bars(S, values, o = {}) {
      const x0 = o.from ?? 0;
      const w = S.x(x0 + 1) - S.x(x0);
      const rects = values.map((v, i) =>
        `<rect class="area-bar" x="${S.x(x0 + i)}" y="${S.y(v)}" ` +
        `width="${w}" height="${BOX.y0 - S.y(v)}"/>`
      ).join('');
      return {
        svg: rects,
        mid: values.map((v, i) => [x0 + i + 0.5, v]),   // 데이터 좌표
        labels: values.map((_, i) =>
          annot(S.x(x0 + i + 0.5), BOX.y0 + 17, String(i + 1),
                { anchor: 'middle', size: 12 })),
      };
    }

    /* 축 + 축 이름.
       세로축 이름은 축 위쪽에 가운데 정렬로 둔다. 예전처럼 축 왼쪽에 붙이면
       긴 한글 이름("가격(천원)")이 캔버스 왼쪽으로 잘려 나갔다.
       vb(viewBox)를 알면 위쪽으로도 넘치지 않게 눌러 준다. */
    function axesSvg(a = {}, vb) {
      const top = vb ? vb[1] : 0;
      let s = `<g class="g-axes">`;
      s += `<path class="axis" d="M${BOX.x0},${BOX.y1 - 8} L${BOX.x0},${BOX.y0} L${BOX.x1 + 10},${BOX.y0}"/>`;
      if (a.y) {
        const y = Math.max(BOX.y1 - 13, top + 13);
        s += `<text class="axis-name" x="${BOX.x0}" y="${y}" text-anchor="middle">${esc(a.y)}</text>`;
      }
      if (a.x)
        s += `<text class="axis-name" x="${BOX.x1 + 14}" y="${BOX.y0 + 5}">${esc(a.x)}</text>`;
      return s + '</g>';
    }

    function draw(sel, spec) {
      const el = typeof sel === 'string' ? document.querySelector(sel) : sel;
      if (!el) { console.warn('[Fig] 대상을 찾지 못했습니다:', sel); return; }
      const title = el.querySelector('title');
      const keep = title ? title.outerHTML : '';
      const vbAttr = el.getAttribute('viewBox');
      const vb = vbAttr ? vbAttr.trim().split(/[\s,]+/).map(Number) : null;
      el.innerHTML =
        keep + MARKERS +
        (spec.axes ? axesSvg(spec.axes, vb) : '') +
        (spec.parts || []).filter(Boolean).join('\n');
      fitLabels(el);
      if (spec.check !== false) checkDots(el);
    }

    return {
      draw, curve, line, guide, dot, annot, arrow, raw, labelIn, bars,
      convex, upward, path, shift, at, scale, BOX,
      withBox: (b) => make({ ...BOX, ...b }),
    };
  }

  return make(DEFAULT_BOX);
})();
