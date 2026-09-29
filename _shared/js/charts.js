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
    // dash: 점선으로 (이동 전 곡선, 예정선 등). CSS 클래스로 두면 곡선 색 규칙과 엉킨다.
    const dash = o.dash ? ` stroke-dasharray="${o.dash}"` : '';
    return `class="${klass}"${idx}${dash}`;
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

  /* 글자 폭 어림. SVG에 넣기 전에 자리를 판단해야 해서 getBBox 를 쓸 수 없다.
     한글·전각기호는 한 칸, 영문·숫자·공백은 0.55칸으로 친다. */
  function textW(str, size = 12) {
    let n = 0;
    for (const ch of String(str))
      n += /[ᄀ-ᇿ　-〿㄰-㆏가-힯＀-￯]/.test(ch) ? 1 : 0.55;
    return n * size;
  }

  /* ── 포락선 위에 접하는 U자 ─────────────────────────────
   * 장기평균비용곡선(LAC)과 단기평균비용곡선(SAC)의 관계를 그릴 때 쓴다.
   *
   * SAC 을 눈대중으로 찍고 LAC 을 그 최저점들에 이으면 LAC 이 SAC 을 뚫고 지나간다.
   * 포물선은 최저점 근처가 평평해서, 기울기가 0이 아닌 선이 최저점을 지나면
   * 반드시 한쪽에서 위로 새어 나오기 때문이다.
   *
   * 그래서 순서를 뒤집는다. LAC 을 먼저 정하고 SAC 을 그 접선 위에 얹는다.
   *   SAC(x) = L(t) + L'(t)(x−t) − k(x−t)²
   * 이면  L(x) − SAC(x) = k(x−t)² + (L 의 오목분) ≥ 0 이므로
   * SAC 은 어디서도 LAC 위로 올라오지 않고 x=t 에서만 닿는다.
   * L 이 굽은 경우엔 k > |L''|/2 이면 된다.
   *
   *   L, dL : LAC 의 값과 기울기 (픽셀 좌표 함수)
   *   t     : 닿는 지점의 x
   *   half  : U 의 반폭
   *   k     : 벌어짐. 클수록 좁고 가파른 U (양 팔의 높이 = k·half²) */
  function tangentU(L, dL, t, half, k) {
    const pts = [];
    const step = Math.max(2, half / 20);
    for (let d = -half; d <= half + 1e-9; d += step)
      pts.push([round(t + d), round(L(t) + dL(t) * d - k * d * d)]);
    return pts;
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

  /* ── 두 곡선이 만나는 점 ─────────────────────────────────
   * MR = MC, 수요 = 공급처럼 "교차점"은 그림마다 나온다. 눈으로 찍으면 어긋나므로
   * 두 곡선에서 직접 구한다 (design.md §6.4).
   * 겹치는 x 구간을 훑어 부호가 바뀌는 곳을 찾고 이분법으로 좁힌다.
   * 만나지 않으면 null 을 준다 — 부르는 쪽에서 그림을 고쳐야 한다는 신호다. */
  function cross(p, q) {
    const lo = Math.max(p[0][0], q[0][0]);
    const hi = Math.min(p[p.length - 1][0], q[q.length - 1][0]);
    if (!(hi > lo)) return null;
    const f = (x) => at(p, { x })[1] - at(q, { x })[1];
    let a = lo, fa = f(a), b = hi, fb = f(b);
    if (fa === 0) return [round(a), round(at(p, { x: a })[1])];
    if (fa * fb > 0) {
      let found = false;
      for (let i = 1; i <= 240; i++) {
        const x = lo + ((hi - lo) * i) / 240, fx = f(x);
        if (fa * fx <= 0) { b = x; fb = fx; found = true; break; }
        a = x; fa = fx;
      }
      if (!found) return null;
    }
    for (let i = 0; i < 50; i++) {
      const m = (a + b) / 2, fm = f(m);
      if (fa * fm <= 0) { b = m; } else { a = m; fa = fm; }
    }
    const x = (a + b) / 2;
    return [round(x), round(at(p, { x })[1])];
  }

  /* 화살촉 색은 .arrow / .arrow.red / .arrow.blue / .arrow.green 의 stroke 와
     같은 토큰을 쓴다. 색값을 적어 두면 테마를 바꿀 때 선과 촉이 서로 다른 색이 된다.
     SVG 표현속성에서도 var() 가 풀린다 (Chrome·decktape 확인). */
  const MARKERS = `<defs>
    <marker id="ah-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--ink)"/></marker>
    <marker id="ah-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--point-red)"/></marker>
    <marker id="ah-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--chart-blue)"/></marker>
    <marker id="ah-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--accent-green)"/></marker>
  </defs>`;

  /* ── 산점도 표본 (이변량 정규) ───────────────────────────
   * 산점도의 점을 손으로 찍지 않기 위한 생성기다 (design.md §6.4).
   * 씨앗이 같으면 언제나 같은 점이 나오므로 PDF를 다시 뽑아도 그림이 바뀌지 않는다.
   *
   *   Fig.scatter({ n: 50, mx: 3, my: 3, sx: 1, sy: 1, r: 0.8, seed: 4 })
   *
   * 뽑은 표본을 표준화하고 z2에서 z1 성분을 걷어낸 뒤
   *   x = mx + sx·z1,  y = my + sy·(r·z1 + √(1−r²)·z2)
   * 로 합성하므로 **표본평균·표본표준편차·표본상관계수가 지정한 값과 정확히 일치한다.**
   * "평균과 표준편차는 같은데 상관계수만 다른 두 산포도"처럼
   * 슬라이드의 설명이 그림에서도 참이어야 하는 자리에서 이 성질이 필요하다.
   * 표준편차는 표본표준편차(n−1)다 — 강의에서 쓰는 정의와 같다. */
  function scatter(o = {}) {
    const n = o.n ?? 50;
    const r = o.r ?? 0;
    const mx = o.mx ?? 0, my = o.my ?? 0;
    const sx = o.sx ?? 1, sy = o.sy ?? 1;

    let s = (o.seed ?? 1) >>> 0;
    const rnd = () => {                                   // mulberry32
      s = (s + 0x6D2B79F5) >>> 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const gauss = () =>                                   // Box–Muller
      Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(2 * Math.PI * rnd());

    const mean = (v) => v.reduce((p, q) => p + q, 0) / v.length;
    const unit = (v) => {
      const m = mean(v);
      const sd = Math.sqrt(v.reduce((p, q) => p + (q - m) ** 2, 0) / (v.length - 1)) || 1;
      return v.map((q) => (q - m) / sd);
    };

    const a = [], b = [];
    for (let i = 0; i < n; i++) { a.push(gauss()); b.push(gauss()); }

    const z1 = unit(a);
    let z2 = unit(b);
    const c12 = z1.reduce((p, q, i) => p + q * z2[i], 0) / (n - 1);
    z2 = unit(z2.map((q, i) => q - c12 * z1[i]));         // z1 ⟂ z2 라야 상관계수가 정확히 r

    const k = Math.sqrt(Math.max(0, 1 - r * r));
    return z1.map((q, i) => [mx + sx * q, my + sy * (r * q + k * z2[i])]);
  }

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

    svg.querySelectorAll('circle.dot:not([data-free]), circle.dot-open:not([data-free])').forEach((c) => {
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

    /* 정규분포의 확률밀도 — 데이터 좌표 [x, f(x)] (design.md §6.4)
     *
     *   const S = F.scale({ x: [-3.6, 3.6], y: [0, 0.42] });
     *   F.curve(S.curve(F.normal(0, 1, -3.6, 3.6)), { variant: 'demand' })
     *
     * 종모양을 손으로 찍지 않는다. 곡선·채움(확률)·눈금이 같은 함수에서 나오므로
     * "면적 = 확률"이 그림에서 저절로 맞는다.
     *
     * 굽는 구간이 많아 표본을 촘촘히 뽑는다(기본 96). 성기게 뽑으면 at() 의
     * 선형보간이 curve() 의 스플라인과 어긋나 점이 곡선을 벗어난다.
     * 눈금·좌표점으로 쓸 x 는 through 로 표본에 반드시 넣는다. */
    function normal(mu, sigma, x0, x1, o = {}) {
      const n = o.n ?? 96;
      const k = 1 / (sigma * Math.sqrt(2 * Math.PI));
      const xs = [];
      for (let i = 0; i <= n; i++) xs.push(x0 + ((x1 - x0) * i) / n);
      for (const x of o.through || []) if (x > x0 && x < x1) xs.push(x);
      xs.sort((a, b) => a - b);
      // 데이터 좌표이므로 여기서 반올림하지 않는다 (hyper() 와 같은 이유)
      return xs.map((x) => [x, k * Math.exp(-0.5 * Math.pow((x - mu) / sigma, 2))]);
    }

    /* 곡선 아래를 밑변까지 닫아 칠한다 — 확률분포에서 "구간의 면적 = 확률"
     *
     *   F.under(S.curve(F.normal(0, 1, -3.6, -1.5)), { cls: 'area-loss' })
     *
     * 픽셀 점묶음을 받아 곡선과 같은 스플라인으로 윤곽을 그리므로 칠한 자리가
     * 곡선과 어긋나지 않는다. 곡선에 넘긴 것과 같은 점을 잘라서 넘기면 된다.
     * baseY 기본값은 플롯의 가로축(BOX.y0). */
    function under(pxPts, o = {}) {
      if (pxPts.length < 2) return '';
      const baseY = o.baseY ?? BOX.y0;
      const a = pxPts[0], z = pxPts[pxPts.length - 1];
      return `<path ${attrs(o.cls || 'area-surplus', o)} ` +
             `d="${path(pxPts)} L${z[0]},${baseY} L${a[0]},${baseY} Z"/>`;
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

    /* 직각쌍곡선 xy = k 의 데이터 점 — 무차별곡선·등량곡선 (design.md §6.8)
     *
     * 교과서의 무차별곡선은 두 축에 점근하는 강한 볼록 형태다.
     * 표 값을 그대로 이으면 앞부분이 직선이 되어 충분히 휘지 않는다.
     * 곡선을 먼저 정하고 그 위에서 눈금값을 고르는 편이 낫다.
     *
     *   Fig.hyper(200, 6.5, 45)   → [[6.5,30.8], … , [45,4.4]]  (데이터 좌표)
     *   S.curve(Fig.hyper(200, 6.5, 45))
     *
     * 어떤 점이 곡선 위에 있는지는 xy = k 로 바로 확인된다 — (8,25)·(10,20)·(20,10)은
     * 모두 k=200이다. */
    function hyper(k, x0, x1, o = {}) {
      const n = o.n ?? 26;
      const xs = [];
      // 로그 간격으로 뽑아야 휘는 구간에 점이 촘촘히 놓인다
      const r = Math.log(x1 / x0);
      for (let i = 0; i <= n; i++) xs.push(x0 * Math.exp((r * i) / n));
      // 눈금·좌표점으로 쓸 x는 반드시 표본에 넣는다.
      // 표본 사이를 스플라인이 잇는 탓에, 빠뜨리면 점이 곡선에서 몇 px 벗어난다.
      for (const x of o.through || []) if (x > x0 && x < x1) xs.push(x);
      xs.sort((a, b) => a - b);
      // 여기서 반올림하지 않는다 — 이건 데이터 좌표다. 픽셀로 바꿀 때(S.curve)
      // 반올림하면 충분하고, 여기서 자리를 줄이면 1.25가 1.3이 되어 점이 곡선에서 벗어난다.
      return xs.map((x) => [x, k / x]);
    }

    /* 우상향하며 기울기가 점점 완만 — 총효용·총생산곡선
       (체감하는 증가. upward()는 반대로 체증한다) */
    function concave(o = {}) {
      const x0 = o.x0 ?? BOX.x0 + 20;
      const x1 = o.x1 ?? BOX.x1 - 20;
      const yBot = o.yBot ?? BOX.y0 - 10;
      const yTop = o.yTop ?? BOX.y1 + 20;
      const n = o.n ?? 24;
      const p = o.bend ?? 0.55;      // 작을수록 빨리 눕는다
      const pts = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        pts.push([
          round(x0 + (x1 - x0) * t),
          round(yBot - (yBot - yTop) * Math.pow(t, p)),
        ]);
      }
      return pts;
    }

    /* 우하향하며 완만해짐 — 한계효용·한계생산곡선 */
    function decay(o = {}) {
      const x0 = o.x0 ?? BOX.x0 + 20;
      const x1 = o.x1 ?? BOX.x1 - 20;
      const yTop = o.yTop ?? BOX.y1 + 30;
      const yBot = o.yBot ?? BOX.y0 - 30;
      const n = o.n ?? 24;
      const k = o.bow ?? 0.45;
      const pts = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        pts.push([
          round(x0 + (x1 - x0) * t),
          round(yTop + (yBot - yTop) * (t / (t + k)) * (1 + k)),
        ]);
      }
      return pts;
    }

    /* U자 — 한계비용·평균비용곡선 */
    function ushape(o = {}) {
      const x0 = o.x0 ?? BOX.x0 + 30;
      const x1 = o.x1 ?? BOX.x1 - 30;
      const yBot = o.yBot ?? BOX.y0 - 60;   // 골짜기
      const yL = o.yLeft ?? BOX.y1 + 40;
      const yR = o.yRight ?? BOX.y1 + 10;
      const m = o.min ?? 0.42;               // 골짜기 위치 (0~1)
      const n = o.n ?? 28;
      const pts = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        const d = (t - m) / (t < m ? m : 1 - m);
        const top = t < m ? yL : yR;
        pts.push([round(x0 + (x1 - x0) * t), round(yBot - (yBot - top) * d * d)]);
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

    /* 좌표점. on: 곡선 점묶음을 주면 그 곡선 위로 스냅한다 (design.md §6.4)
     *
     * free: 일부러 곡선 밖에 두는 점 (예. 무차별곡선보다 낮은/높은 효용의 상품묶음,
     *       예산집합 밖의 점). 자체검사에서 제외한다 — 오류가 아니라 설명 장치다. */
    function dot(x, y, o = {}) {
      if (o.on) [x, y] = at(o.on, { x });
      const cls = 'dot' + (o.open ? ' dot-open' : '');
      let s = `<g ${attrs('g-dot', o)}>`;
      s += `<circle class="${cls}" cx="${x}" cy="${y}" r="${o.r ?? 4.5}"` +
           `${o.free ? ' data-free="1"' : ''}/>`;
      if (o.label)
        s += `<text class="annot" x="${x + (o.lx ?? 7)}" y="${y + (o.ly ?? -7)}">${esc(o.label)}</text>`;
      return s + '</g>';
    }

    /* 산점도의 점들. Fig.scatter()가 만든 데이터 좌표를 S.curve()로 픽셀로 옮겨 넘긴다.
     *
     *   Fig.dots(S.curve(Fig.scatter({ n: 50, mx: 3, my: 3, r: .8, seed: 4 })))
     *
     * 좌표점(.dot)과 클래스를 나눈 이유: .dot 은 "곡선 위에 있어야 하는 점"이라
     * checkDots 의 검사 대상이지만, 산점도의 점은 자료 그 자체라 곡선 밖이 정상이다. */
    function dots(pts, o = {}) {
      const cls = 'pt' + (o.variant ? ' pt-' + o.variant : '');
      const rr = o.r ?? 2.4;
      return `<g ${attrs('g-pt', o)}>` +
        pts.map(([x, y]) => `<circle class="${cls}" cx="${round(x)}" cy="${round(y)}" r="${rr}"/>`).join('') +
        '</g>';
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
      if (a.x) {
        // 기본은 축 오른쪽 끝. 좁은 캔버스에서는 그러면 글자가 잘려 나가므로
        // 축 아래 오른쪽으로 접어 넣는다. 세로축 이름과 같은 취지의 보정이다.
        const right = vb ? vb[0] + vb[2] : Infinity;
        s += BOX.x1 + 14 + textW(a.x, 12) <= right - 2
          ? `<text class="axis-name" x="${BOX.x1 + 14}" y="${BOX.y0 + 5}">${esc(a.x)}</text>`
          : `<text class="axis-name" x="${BOX.x1 + 10}" y="${BOX.y0 + 32}" text-anchor="end">${esc(a.x)}</text>`;
      }
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
      draw, curve, line, guide, dot, dots, annot, arrow, raw, labelIn, bars,
      under, convex, upward, concave, decay, ushape, hyper, normal,
      tangentU, path, shift, at, cross, scatter, scale, BOX,
      withBox: (b) => make({ ...BOX, ...b }),
    };
  }

  return make(DEFAULT_BOX);
})();
