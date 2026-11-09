#!/usr/bin/env python3
"""7강(탐색적 공간분석)의 사례를 서울 자료로 만든다. 광양 격자를 대신한다 (2026-10-30).

  1 단계구분도        분류 기준값    등간 · 분위 · 자연분류(Jenks) 다섯 계급
  2 커널밀도추정      KDE            따릉이 대여소 점의 밀도 (가우스 커널, 대역폭 1km)
  3 전역 공간자기상관  Moran's I      비슷한 값이 뭉쳐 있나를 한 숫자로
  4 국지 공간자기상관  LISA           어느 동이 뭉침에 기여하나
  5 핫스팟 분석        Getis-Ord Gi*  높은 값과 낮은 값이 몰린 곳
  6 밀도기반 공간군집  DBSCAN         위치만으로 덩어리와 잡음

값은 동마다 **주간인구지수** = 평일 14시 생활인구 ÷ 평일 03시 생활인구 × 100.
100 보다 크면 낮에 사람이 모여드는 동, 작으면 낮에 빠져나가는 동이다.
단계구분도(1)는 지수 그대로, 3 · 4 · 5 는 **ln(지수 ÷ 100)** 으로 한다. 지수는 50 ~ 1,083 으로
위쪽 꼬리만 길어서 평균보다 낮은 쪽으로는 멀리 갈 수 없고, 그대로 두면 콜드스팟이 하나도 안 나온다.

입력: analysis/data/서울_행정동경계_2016.geojson     — 1 · 3 · 4 · 5
      analysis/data/서울_생활인구_202607_평일.csv    — 1 · 3 · 4 · 5
      analysis/data/서울_따릉이대여소_2606.csv       — 2 · 6
      세 파일은 07-서울자료준비.py 가 원자료에서 만든다.

외부 라이브러리를 쓰지 않는다. 공간가중행렬도 직접 만든다.
Moran's I 의 유의성은 **정규근사**로, LISA 의 동마다 유의성은 **조건부 순열**(시드 고정)로 구한다.

    python3 07-서울공간분석.py            # 결과 CSV
    python3 07-서울공간분석.py --slide    # 슬라이드 head 에 넣을 SEOUL_RAW 를 찍는다

로직: 07-서울공간분석-로직.md 를 먼저 읽는다.
"""
import csv, json, math, pathlib, random, statistics as st, sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
BND  = DATA / '서울_행정동경계_2016.geojson'
POP  = DATA / '서울_생활인구_202607_평일.csv'
BIKE = DATA / '서울_따릉이대여소_2606.csv'
EPS_M    = 500    # DBSCAN 반경(m). 걸어서 6~7분
MIN_PTS  = 15     # 반경 안 대여소 수(자기 포함). 서울 평균은 약 3.6곳 — 그 네 배 넘게 촘촘한 곳만 덩어리로 본다
KDE_BW   = 1000   # KDE 대역폭(m)
KDE_ALT  = (500, 2000)   # 견줘 볼 대역폭(m)
LISA_PERMS = 9999   # LISA 조건부 순열 횟수
LISA_SEED  = 2026   # 순열의 난수 시드 — 고정해야 같은 결과가 나온다
LISA_ALPHA = 0.05
KDE_CELL = 250    # KDE 를 계산할 격자 한 칸(m)
K_CLASS  = 5      # 단계구분도 계급 수
SIMPLIFY = 25     # 슬라이드용 경계 단순화 허용오차(m)

# ── 좌표 도우미 ────────────────────────────────────────────────
LAT0 = 37.55                                   # 서울 중위도
MPD_LAT = 110_574.0
MPD_LON = 111_320.0 * math.cos(math.radians(LAT0))

def to_m(lon, lat):
    return (lon * MPD_LON, lat * MPD_LAT)

def ring_area(r):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]))) / 2

def load_dongs():
    """동마다 외곽 고리(미터 좌표) · 면적 · 주간인구지수. 구멍은 서울 경계에 없다."""
    pop = {r['adm_cd']: r for r in csv.DictReader(open(POP, encoding='utf-8-sig'))}
    out = []
    for f in json.load(open(BND, encoding='utf-8'))['features']:
        p = f['properties']
        rings = [[to_m(*pt) for pt in poly[0]] for poly in f['geometry']['coordinates']]
        r = pop[p['adm_cd']]
        day, night = float(r['평일14시_생활인구']), float(r['평일03시_생활인구'])
        out.append({'cd': p['adm_cd'], 'gu': p['gu'], 'dong': p['dong'], 'rings': rings,
                    'raw': f['geometry']['coordinates'],
                    'area': sum(ring_area(g) for g in rings) / 1e6,
                    'day': day, 'night': night, 'v': day / night * 100})
    return out

def queen(dongs):
    """꼭짓점을 하나라도 같이 쓰면 이웃 (퀸 인접). 경계 파일이 이웃 동과 꼭짓점을 공유한다."""
    owner = defaultdict(set)
    for i, d in enumerate(dongs):
        for poly in d['raw']:
            for pt in poly[0]:
                owner[(round(pt[0], 5), round(pt[1], 5))].add(i)
    W = [set() for _ in dongs]
    for s in owner.values():
        for i in s: W[i] |= s - {i}
    return [sorted(w) for w in W]

# ── 3. Moran's I ──────────────────────────────────────────────
def morans_i(v, W):
    n = len(v)
    m = st.mean(v)
    z = [x - m for x in v]
    s0 = sum(len(w) for w in W)
    num = sum(z[i] * z[j] for i in range(n) for j in W[i])
    den = sum(x * x for x in z)
    I = (n / s0) * (num / den)
    # 정규근사 — 무작위화 가정에서의 기대값과 분산 (Cliff & Ord)
    EI = -1 / (n - 1)
    s1 = 0.5 * sum((2 ** 2) for i in range(n) for j in W[i])   # 이진 대칭가중
    s2 = sum((len(W[i]) + len(W[i])) ** 2 for i in range(n))
    b2 = (sum(x ** 4 for x in z) / n) / ((sum(x * x for x in z) / n) ** 2)
    A = n * ((n * n - 3 * n + 3) * s1 - n * s2 + 3 * s0 * s0)
    B = b2 * ((n * n - n) * s1 - 2 * n * s2 + 6 * s0 * s0)
    VI = (A - B) / ((n - 1) * (n - 2) * (n - 3) * s0 * s0) - EI * EI
    zscore = (I - EI) / math.sqrt(VI) if VI > 0 else float('nan')
    return I, EI, zscore

# ── 4. LISA ───────────────────────────────────────────────────
def lisa(v, W):
    m = st.mean(v)
    sd = st.pstdev(v)
    z = [(x - m) / sd for x in v]
    out = []
    for i in range(len(v)):
        lag = st.mean(z[j] for j in W[i])
        if   z[i] > 0 and lag > 0: t = 'HH'
        elif z[i] < 0 and lag < 0: t = 'LL'
        elif z[i] > 0 and lag < 0: t = 'HL'
        else:                      t = 'LH'
        out.append((z[i] * lag, t))
    return out

def lisa_p(v, W, perms=LISA_PERMS, seed=LISA_SEED):
    """조건부 순열 — 나를 고정하고 나머지 동 값을 이웃 자리에 무작위로 넣어 국지 I 를 다시 구한다.
    p 는 관측값보다 극단인 쪽의 비율 (GeoDa · PySAL 의 pseudo p 와 같은 계산)."""
    rng = random.Random(seed)
    m = st.mean(v)
    sd = st.pstdev(v)
    z = [(x - m) / sd for x in v]
    out = []
    for i in range(len(v)):
        k = len(W[i])
        obs = z[i] * sum(z[j] for j in W[i]) / k
        others = z[:i] + z[i + 1:]
        hit = sum(1 for _ in range(perms) if z[i] * sum(rng.sample(others, k)) / k >= obs)
        hit = min(hit, perms - hit)
        out.append((hit + 1) / (perms + 1))
    return out

# ── 5. Getis-Ord Gi* ──────────────────────────────────────────
def getis(v, W):
    n = len(v)
    m = st.mean(v)
    s = st.pstdev(v)
    out = []
    for i in range(n):
        idx = W[i] + [i]                     # Gi* 는 자기 자신을 포함한다
        w = len(idx)
        num = sum(v[j] for j in idx) - m * w
        den = s * math.sqrt((n * w - w * w) / (n - 1))
        out.append(num / den if den else 0.0)
    return out

# ── 6. DBSCAN ─────────────────────────────────────────────────
def dbscan(pts, eps, minpts):
    bucket = defaultdict(list)                # 점이 많아 eps 칸으로 나눠 이웃 후보만 본다
    for i, (x, y) in enumerate(pts):
        bucket[(int(x // eps), int(y // eps))].append(i)
    W = [[] for _ in pts]
    for (bx, by), ids in bucket.items():
        cand = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in bucket.get((bx + dx, by + dy), [])]
        for i in ids:
            W[i] = [j for j in cand if j != i and math.dist(pts[i], pts[j]) <= eps]
    lab = [None] * len(pts)                   # None 미방문 · -1 잡음 · 0.. 군집
    cid = 0
    for i in range(len(pts)):
        if lab[i] is not None: continue
        if len(W[i]) < minpts - 1:
            lab[i] = -1; continue
        lab[i] = cid
        queue = list(W[i])
        while queue:
            j = queue.pop()
            if lab[j] == -1: lab[j] = cid     # 잡음이 경계점으로 바뀐다
            if lab[j] is not None: continue
            lab[j] = cid
            if len(W[j]) >= minpts - 1:
                queue += W[j]
        cid += 1
    return lab, cid

# ── 1. 단계구분도 분류 기준 ───────────────────────────────────
def breaks_equal(v, k):
    lo, hi = min(v), max(v)
    return [lo + (hi - lo) * i / k for i in range(1, k)]

def breaks_quantile(v, k):
    s = sorted(v); n = len(s)
    return [s[int(n * i / k)] for i in range(1, k)]

def breaks_jenks(v, k):
    """자연분류(Jenks). 동적계획법으로 계급 안 제곱오차의 합이 가장 작은 경계를 찾는다."""
    xs = sorted(v); m = len(xs)
    S = [0]; Q = [0]
    for x in xs:
        S.append(S[-1] + x); Q.append(Q[-1] + x * x)
    def sse(i, j):            # xs[i..j] 포함
        w = j - i + 1; s = S[j + 1] - S[i]
        return Q[j + 1] - Q[i] - s * s / w
    INF = float('inf')
    D = [[INF] * m for _ in range(k)]; P = [[0] * m for _ in range(k)]
    for j in range(m): D[0][j] = sse(0, j)
    for c in range(1, k):
        for j in range(c, m):
            for i in range(c, j + 1):
                val = D[c - 1][i - 1] + sse(i, j)
                if val < D[c][j]: D[c][j] = val; P[c][j] = i
    cuts = []; j = m - 1
    for c in range(k - 1, 0, -1):
        i = P[c][j]; cuts.append(xs[i - 1]); j = i - 1
    return sorted(cuts)

# ── 2. KDE ────────────────────────────────────────────────────
def kde_at(pts, x, y, bw):
    """가우스 커널. 값은 km² 당 대여소 수. 3 × 대역폭 밖의 점은 무시한다."""
    c = 1 / (2 * math.pi * bw * bw) * 1e6
    r2 = (3 * bw) ** 2
    s = 0.0
    for px, py in pts:
        d2 = (x - px) ** 2 + (y - py) ** 2
        if d2 < r2: s += math.exp(-d2 / (2 * bw * bw))
    return c * s

def inside(x, y, rings):
    """rings 는 (고리, 최소x, 최소y, 최대x, 최대y). 상자 밖이면 변을 보지 않는다."""
    hit = False
    for r, bx0, by0, bx1, by1 in rings:
        if not (bx0 <= x <= bx1 and by0 <= y <= by1): continue
        for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                hit = not hit
    return hit

# ── 슬라이드용 경계 단순화 ────────────────────────────────────
def simplify(r, tol):
    """더글러스-포이커."""
    if len(r) < 4: return r
    (x1, y1), (x2, y2) = r[0], r[-1]
    L = math.hypot(x2 - x1, y2 - y1) or 1e-9
    dmax, k = 0, 0
    for i in range(1, len(r) - 1):
        d = abs((x2 - x1) * (y1 - r[i][1]) - (x1 - r[i][0]) * (y2 - y1)) / L
        if d > dmax: dmax, k = d, i
    if dmax <= tol: return [r[0], r[-1]]
    return simplify(r[:k + 1], tol)[:-1] + simplify(r[k:], tol)

def save(name, header, rows):
    p = HERE / name
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {p.name}')

def analyse():
    dongs = load_dongs()
    v = [d['v'] for d in dongs]
    print(f'행정동 {len(dongs)} · 면적 {sum(d["area"] for d in dongs):.1f}km²')
    print(f'주간인구지수  평균 {st.mean(v):.1f} · 중앙값 {st.median(v):.1f} · 최소 {min(v):.1f} · 최대 {max(v):.1f}')
    print(f'  100 넘는 동 {sum(1 for x in v if x > 100)} · 200 넘는 동 {sum(1 for x in v if x > 200)}\n')
    B = {}
    for key, nm, f in (('eq', '등간', breaks_equal), ('q', '분위', breaks_quantile), ('jk', '자연분류', breaks_jenks)):
        B[key] = [round(x, 1) for x in f(v, K_CLASS)]
        cnt = Counter(sum(1 for b in B[key] if x > b) for x in v)
        print(f'  단계구분도 {nm:<4} 경계 {B[key]}  계급별 {[cnt[i] for i in range(K_CLASS)]}')

    lv = [math.log(x / 100) for x in v]       # 3 · 4 · 5 는 로그 지수로
    W = queen(dongs)
    deg = [len(w) for w in W]
    print(f'공간가중  퀸 인접 · 평균 이웃수 {st.mean(deg):.2f} · 최소 {min(deg)} · 이웃 없는 동 {deg.count(0)}')

    I, EI, zs = morans_i(lv, W)
    I0 = morans_i(v, W)[0]
    print(f"\n(지수 그대로면 Moran's I = {I0:.4f})")
    print(f"Moran's I = {I:.4f}  (기대값 {EI:.5f} · z = {zs:.1f})")

    L = lisa(lv, W)
    cnt = Counter(t for _, t in L)
    print('\nLISA 유형')
    for t in ('HH', 'LL', 'HL', 'LH'):
        print(f'  {t:<3} {cnt[t]:>4}동  {cnt[t]/len(L)*100:>5.1f}%')
    hh = Counter(dongs[i]['gu'] for i in range(len(dongs)) if L[i][1] == 'HH')
    print('  HH 가 많은 구', hh.most_common(6))
    LP = lisa_p(lv, W)
    sig = [p <= LISA_ALPHA for p in LP]
    cs = Counter(L[i][1] for i in range(len(L)) if sig[i])
    print(f'LISA 유의성  조건부 순열 {LISA_PERMS:,}번 · 시드 {LISA_SEED} · p ≤ {LISA_ALPHA}')
    for t in ('HH', 'LL', 'HL', 'LH'):
        names = [dongs[i]['dong'] for i in range(len(L)) if sig[i] and L[i][1] == t]
        print(f'  {t:<3} {cs[t]:>4}동  {names[:12]}')
    print(f'  유의 {sum(sig)}동 · 유의하지 않음 {len(sig) - sum(sig)}동')
    print('  유의한 HH 구', Counter(dongs[i]['gu'] for i in range(len(L)) if sig[i] and L[i][1] == 'HH').most_common(6))
    print('  유의한 LL 구', Counter(dongs[i]['gu'] for i in range(len(L)) if sig[i] and L[i][1] == 'LL').most_common(6))

    G0 = getis(v, W)
    print(f'\n(지수 그대로면 Gi* |z|>1.96 핫스팟 {sum(1 for g in G0 if g > 1.96)} · 콜드스팟 {sum(1 for g in G0 if g < -1.96)})')
    G = getis(lv, W)
    hot = [i for i in range(len(G)) if G[i] > 1.96]; cold = [i for i in range(len(G)) if G[i] < -1.96]
    print(f'Getis-Ord Gi*  |z|>1.96 (95%)  핫스팟 {len(hot)}동 · 콜드스팟 {len(cold)}동')
    print('  그중 |z|>2.58 (99%)', sum(1 for g in G if g > 2.58), '/', sum(1 for g in G if g < -2.58))
    print('  핫스팟 구', Counter(dongs[i]['gu'] for i in hot).most_common())
    print('  콜드스팟 구', Counter(dongs[i]['gu'] for i in cold).most_common())
    for i in sorted(range(len(G)), key=lambda i: -G[i])[:5]:
        print(f'    {dongs[i]["gu"]} {dongs[i]["dong"]}  지수 {v[i]:.0f}  Gi* {G[i]:.2f}')
    for i in sorted(range(len(G)), key=lambda i: G[i])[:3]:
        print(f'    {dongs[i]["gu"]} {dongs[i]["dong"]}  지수 {v[i]:.0f}  Gi* {G[i]:.2f}')

    save('07-서울공간분석-동.csv',
         ['adm_cd', '자치구', '행정동', '면적_km2', '평일14시', '평일03시', '주간인구지수', 'LISA_I', 'LISA유형', 'LISA_p', 'Gi_z'],
         [[d['cd'], d['gu'], d['dong'], round(d['area'], 3), round(d['day']), round(d['night']),
           round(v[i], 1), round(L[i][0], 4), L[i][1], round(LP[i], 4), round(G[i], 3)] for i, d in enumerate(dongs)])

    # ── 따릉이 DBSCAN ──
    rows = [(r['대여소명'], r['자치구'], float(r['lon']), float(r['lat']))
            for r in csv.DictReader(open(BIKE, encoding='utf-8-sig'))]
    pts = [to_m(lo, la) for _, _, lo, la in rows]
    area = sum(d['area'] for d in dongs)
    print(f'\n따릉이 {len(rows):,}곳 · km² 당 {len(rows)/area:.2f}곳 · 반경 {EPS_M}m 원 안 평균 '
          f'{len(rows)/area * math.pi * (EPS_M/1000)**2:.1f}곳')
    lab, k = dbscan(pts, EPS_M, MIN_PTS)
    noise = lab.count(-1)
    print(f'DBSCAN  eps {EPS_M}m · minPts {MIN_PTS}  군집 {k}개 · 잡음 {noise:,}곳 ({noise/len(rows)*100:.1f}%)')
    for c in range(k):
        mem = [i for i in range(len(rows)) if lab[i] == c]
        print(f'  군집 {c+1}  {len(mem)}곳 — {Counter(rows[i][1] for i in mem).most_common(2)} · '
              f'{" · ".join(rows[i][0] for i in mem[:3])}')
    save('07-서울공간분석-따릉이군집.csv', ['대여소명', '자치구', 'lon', 'lat', '군집'],
         [[*rows[i], lab[i] + 1 if lab[i] >= 0 else '잡음'] for i in range(len(rows))])

    # ── 따릉이 KDE — 서울 안의 250m 칸마다 ──
    allr = [(r, min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r))
            for d in dongs for r in d['rings']]
    xs = [p[0] for r, *_ in allr for p in r]; ys = [p[1] for r, *_ in allr for p in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    grid = []
    for j in range(int((y1 - y0) // KDE_CELL) + 1):
        for i in range(int((x1 - x0) // KDE_CELL) + 1):
            x, y = x0 + KDE_CELL * (i + .5), y0 + KDE_CELL * (j + .5)
            if inside(x, y, allr): grid.append((x, y, kde_at(pts, x, y, KDE_BW)))
    # 대역폭을 바꾼 지도 — 같은 칸에서 다시 구한다
    alt = {bw: [(x, y, kde_at(pts, x, y, bw)) for x, y, _ in grid] for bw in KDE_ALT}
    for bw, g in alt.items():
        t = max(g, key=lambda c: c[2])
        nr = sorted(range(len(rows)), key=lambda i: math.dist(pts[i], t[:2]))[:2]
        print(f'  대역폭 {bw}m  최대 {t[2]:.1f}곳/km² · 가까운 대여소 ' + ' · '.join(rows[i][0] for i in nr))
    top = max(grid, key=lambda g: g[2])
    near = sorted(range(len(rows)), key=lambda i: math.dist(pts[i], top[:2]))[:2]
    print(f'\nKDE  대역폭 {KDE_BW}m · 칸 {KDE_CELL}m · 서울 안 {len(grid):,}칸 · 최대 {top[2]:.1f}곳/km² '
          f'· 중앙값 {st.median(g[2] for g in grid):.1f}')
    print('  가장 촘촘한 칸 가까이:', ' · '.join(f'{rows[i][0]}({math.dist(pts[i], top[:2]):.0f}m)' for i in near))
    save('07-서울공간분석-KDE.csv', ['lon', 'lat', '밀도_곳per㎢'],
         [[round(x / MPD_LON, 6), round(y / MPD_LAT, 6), round(d, 3)] for x, y, d in grid])
    return dongs, v, L, G, B, (I, EI, zs), rows, pts, lab, grid, (x0, y0, x1, y1), sig, alt

def slide(res):
    """슬라이드 head 의 window.SEOUL_RAW. 좌표는 서울 남서쪽 끝 기준 10m 단위 정수."""
    dongs, v, L, G, B, (I, EI, zs), rows, pts, lab, grid, (x0, y0, x1, y1), sig, alt = res
    T = {'HH': 0, 'LL': 1, 'HL': 2, 'LH': 3}
    q = lambda x, o: round((x - o) / 10)
    ds = []
    for i, d in enumerate(dongs):
        polys = []
        for r in d['rings']:
            if ring_area(r) < 20_000: continue          # 2ha 미만 섬은 지도에서 안 보인다
            k = max(range(len(r)), key=lambda i: math.dist(r[0], r[i]))   # 닫힌 고리는 가장 먼 점에서 둘로 나눠 줄인다
            s = simplify(r[:k + 1], SIMPLIFY)[:-1] + simplify(r[k:] + [r[0]], SIMPLIFY)[:-1]
            polys.append(' '.join(f'{q(x, x0)} {q(y, y0)}' for x, y in s))
        ds.append(f'{d["gu"]}|{d["dong"]}|{v[i]:.2f}|{T[L[i][1]]}|{round(G[i] * 1000)}|' + '/'.join(polys))
    st_ = ';'.join(f'{q(x, x0)},{q(y, y0)},{lab[i] + 1}' for i, (x, y) in enumerate(pts))
    kd = ';'.join(f'{q(x, x0)},{q(y, y0)},{round(d * 10)}' for x, y, d in grid if d >= 0.5)
    print('  window.SEOUL_RAW = {')
    print(f'    W: {q(x1, x0)}, H: {q(y1, y0)},')
    print(f"    dong: {json.dumps('#'.join(ds), ensure_ascii=False)},")
    print(f"    st: '{st_}',")
    print(f"    kde: '{kd}',")
    for bw, g in alt.items():
        print(f"    kde{bw}: '" + ';'.join(f'{q(x, x0)},{q(y, y0)},{round(d * 10)}' for x, y, d in g if d >= 2) + "',")
    print(f"    lisaSig: '{''.join('1' if x else '0' for x in sig)}',")
    print(f"    breaks: {json.dumps(B)}, I: {I:.4f}, EI: {EI:.5f}, zI: {zs:.1f},")
    print(f"    eps: {EPS_M}, minPts: {MIN_PTS}, bw: {KDE_BW}, kdeCell: {KDE_CELL}, "
          f"kdeMax: {max(g[2] for g in grid):.1f}, "
          + ', '.join(f'kdeMax{bw}: {max(c[2] for c in g):.1f}' for bw, g in alt.items()) + ',')
    print('  };')

if __name__ == '__main__':
    if '--slide' in sys.argv:
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            res = analyse()
        slide(res)
    else:
        analyse()
