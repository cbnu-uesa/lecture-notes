#!/usr/bin/env python3
"""7강(탐색적 공간분석)의 공간자기상관·핫스팟·밀도군집 사례를 만든다.

  3 전역 공간자기상관  Moran's I      비슷한 값이 뭉쳐 있나를 한 숫자로
  4 국지 공간자기상관  LISA           어느 구역이 뭉침에 기여하나
  5 핫스팟 분석        Getis-Ord Gi*  높은 값이 몰린 곳
  6 밀도기반 공간군집  DBSCAN         위치만으로 덩어리와 잡음

입력: analysis/data/08.광양시_격자별인구현황(100X100).geojson  — 3·4·5
      analysis/data/01.광양시_충전기설치현황.csv                — 6
      COMPAS 「전기차 충전소 최적입지 선정」(광양, SBJ_2009_001) 공개 데이터

외부 라이브러리를 쓰지 않는다. 공간가중행렬도 직접 만든다.
난수를 쓰지 않는다 — Moran's I 의 유의성은 무작위 순열 대신 **정규근사**로 잰다.

    python3 07-광양공간분석.py

로직: 07-광양공간분석-로직.md 를 먼저 읽는다.
"""
import csv, json, math, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
GRID = DATA / '08.광양시_격자별인구현황(100X100).geojson'
EVSE = DATA / '01.광양시_충전기설치현황.csv'
EPS_M   = 700     # DBSCAN 반경(m). 도보권 10분 남짓
MIN_PTS = 3       # 군집으로 인정할 최소 점 수

# ── 좌표 도우미 ────────────────────────────────────────────────
LAT0 = 34.97                                   # 광양 중위도
MPD_LAT = 110_574.0                            # 위도 1도 = m
MPD_LON = 111_320.0 * math.cos(math.radians(LAT0))

def to_m(lon, lat):
    return (lon * MPD_LON, lat * MPD_LAT)

def load_grid():
    """격자 중심점과 인구. val 이 없는 칸은 조사 대상이 아니므로 뺀다."""
    d = json.load(open(GRID, encoding='utf-8'))
    out = []
    for f in d['features']:
        v = f['properties'].get('val')
        if v is None:
            continue
        ring = f['geometry']['coordinates'][0][0]
        lon = sum(p[0] for p in ring[:-1]) / (len(ring) - 1)
        lat = sum(p[1] for p in ring[:-1]) / (len(ring) - 1)
        out.append({'gid': f['properties']['gid'], 'lon': lon, 'lat': lat, 'v': float(v)})
    return out

def neighbors(cells, radius_m):
    """격자 중심 사이 거리가 radius 이내면 이웃. 격자 크기가 100m 라
       radius 150m 면 상하좌우(rook), 200m 면 대각까지(queen) 가 잡힌다."""
    bucket = {}
    for i, c in enumerate(cells):
        x, y = to_m(c['lon'], c['lat'])
        c['x'], c['y'] = x, y
        bucket.setdefault((int(x // radius_m), int(y // radius_m)), []).append(i)
    W = [[] for _ in cells]
    for (bx, by), idxs in bucket.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand += bucket.get((bx + dx, by + dy), [])
        for i in idxs:
            for j in cand:
                if i == j: continue
                if math.dist((cells[i]['x'], cells[i]['y']),
                             (cells[j]['x'], cells[j]['y'])) <= radius_m:
                    W[i].append(j)
    return W

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
    n = len(v)
    m = st.mean(v)
    sd = st.pstdev(v)
    z = [(x - m) / sd for x in v]
    out = []
    for i in range(n):
        if not W[i]:
            out.append((0.0, '이웃없음')); continue
        lag = st.mean(z[j] for j in W[i])
        Ii = z[i] * lag
        if   z[i] > 0 and lag > 0: t = 'HH'
        elif z[i] < 0 and lag < 0: t = 'LL'
        elif z[i] > 0 and lag < 0: t = 'HL'
        else:                      t = 'LH'
        out.append((Ii, t))
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
    n = len(pts)
    W = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and math.dist(pts[i], pts[j]) <= eps:
                W[i].append(j)
    lab = [None] * n                          # None 미방문 · -1 잡음 · 0.. 군집
    cid = 0
    for i in range(n):
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

def save(name, header, rows):
    p = HERE / name
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {p.name}')

def main():
    if not GRID.exists() or not EVSE.exists():
        sys.exit('원본이 없습니다. COMPAS SBJ_2009_001 을 내려받으십시오.')

    cells = load_grid()
    v = [c['v'] for c in cells]
    print(f'격자 {len(cells):,}칸 (인구값이 있는 칸) · 인구 합 {sum(v):,.0f}명')
    print(f'칸당 인구  평균 {st.mean(v):.1f} · 중앙값 {st.median(v):.1f} · 최대 {max(v):.0f}\n')

    W = neighbors(cells, 150)                 # 상하좌우 이웃
    deg = [len(w) for w in W]
    print(f'공간가중  이웃 반경 150m · 평균 이웃수 {st.mean(deg):.2f} · 이웃 없는 칸 {deg.count(0):,}')

    I, EI, zs = morans_i(v, W)
    print(f"\nMoran's I = {I:.4f}  (기대값 {EI:.5f} · z = {zs:.1f})")
    print('  → 양수이고 z 가 크면 비슷한 값이 뭉쳐 있다는 뜻')

    L = lisa(v, W)
    from collections import Counter
    cnt = Counter(t for _, t in L)
    print('\nLISA 유형')
    for t in ('HH', 'LL', 'HL', 'LH', '이웃없음'):
        if cnt[t]: print(f'  {t:<5} {cnt[t]:>6,}칸  {cnt[t]/len(L)*100:>5.1f}%')

    G = getis(v, W)
    hot = sum(1 for g in G if g > 2.58)
    cold = sum(1 for g in G if g < -2.58)
    print(f'\nGetis-Ord Gi*  |z|>2.58 (99%)  핫스팟 {hot:,}칸 · 콜드스팟 {cold:,}칸')
    top = sorted(range(len(G)), key=lambda i: -G[i])[:8]
    print('  가장 뜨거운 칸')
    for i in top:
        print(f'    {cells[i]["gid"]}  인구 {v[i]:>5.0f}  Gi* {G[i]:>6.2f}')

    save('07-광양공간분석-격자.csv',
         ['gid', 'lon', 'lat', '인구', 'LISA_I', 'LISA유형', 'Gi_z'],
         [[cells[i]['gid'], round(cells[i]['lon'], 6), round(cells[i]['lat'], 6),
           round(v[i]), round(L[i][0], 4), L[i][1], round(G[i], 3)]
          for i in range(len(cells))])

    # ── 충전소 DBSCAN ──
    rows = []
    with open(EVSE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try: rows.append((r['충전소명'], float(r['lon']), float(r['lat'])))
            except (ValueError, KeyError, TypeError): pass
    pts = [to_m(lo, la) for _, lo, la in rows]
    lab, k = dbscan(pts, EPS_M, MIN_PTS)
    noise = lab.count(-1)
    print(f'\nDBSCAN  충전소 {len(rows)}곳 · eps {EPS_M}m · minPts {MIN_PTS}')
    print(f'  군집 {k}개 · 잡음 {noise}곳 ({noise/len(rows)*100:.0f}%)')
    for c in range(k):
        mem = [rows[i][0] for i in range(len(rows)) if lab[i] == c]
        print(f'  군집 {c+1}  {len(mem)}곳 — {" · ".join(mem[:4])}{" …" if len(mem) > 4 else ""}')
    save('07-광양공간분석-충전소군집.csv', ['충전소명', 'lon', 'lat', '군집'],
         [[rows[i][0], rows[i][1], rows[i][2], lab[i] + 1 if lab[i] >= 0 else '잡음']
          for i in range(len(rows))])

if __name__ == '__main__':
    main()
