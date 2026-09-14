#!/usr/bin/env python3
"""6강(기술적 분석 1)의 산점도·군집 슬라이드에 쓰는 수치를 만든다.

07-세종주택시장.py 가 분포·대표값·산포를 맡고, 이 스크립트가 나머지 셋을 맡는다.
  · 산점도      전용면적 ↔ 거래금액
  · K-means     동별 (거래건수, ㎡당 중앙값) 로 동을 유형화
  · 계층군집    같은 자료를 나무 모양으로

입력: 07-세종주택시장.py 와 같은 원자료.
로직: 07-세종주택시장-로직.md 의 「군집」 절.

    python3 07-세종군집.py

난수를 쓰지 않는다. K-means 의 초기 중심은 첫 좌표축에서 가장 멀리 떨어진 점들로
정하므로 몇 번을 돌려도 같은 답이 나온다.
"""
import csv, math, statistics as st, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
FILE = '3.세종시_아파트(매매)_실거래가.csv'
SRC = (DATA / FILE if (DATA / FILE).exists()
       else pathlib.Path.home() / 'data/compas/sejong-housing' / FILE)
AREA_MIN = 60
MIN_N    = 100
K        = 3      # 군집 개수. 팔꿈치 그림에서 고른 값이다
SAMPLE_N = 300    # 산점도에 찍을 점의 수 (전수는 SVG 에 너무 많다)

def load():
    rows = []
    with open(SRC, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get('해제사유발생일'):
                continue
            try:
                area = float(r['전용면적(㎡)'])
                amt  = int(r['거래금액(만원)'].replace(',', ''))
            except (ValueError, KeyError):
                continue
            if area <= AREA_MIN:
                continue
            rows.append({'dong': r['시군구'].split()[-1],
                         'area': area, 'amt': amt, 'per': amt / area})
    return rows

def save(name, header, rows):
    path = HERE / name
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {path.name}')

def pearson(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy)

def zscores(cols):
    """열마다 표준화한다. 거래건수(수천)와 ㎡당가격(수백)의 단위가 달라서다."""
    out = []
    for col in cols:
        m, s = st.mean(col), st.pstdev(col)
        out.append([(v - m) / s for v in col])
    return list(zip(*out))          # 행 단위로 돌려준다

def dist(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))

def kmeans(pts, k):
    """난수 없는 K-means. 초기 중심은 서로 가장 먼 점들로 고른다 (k-means++ 의 결정판)."""
    centers = [max(pts, key=lambda p: p[0])]          # 첫 축이 가장 큰 점
    while len(centers) < k:
        far = max(pts, key=lambda p: min(dist(p, c) for c in centers))
        centers.append(far)
    for _ in range(100):
        groups = [[] for _ in range(k)]
        for p in pts:
            groups[min(range(k), key=lambda i: dist(p, centers[i]))].append(p)
        new = [tuple(st.mean(c) for c in zip(*g)) if g else centers[i]
               for i, g in enumerate(groups)]
        if new == centers:
            break
        centers = new
    label = [min(range(k), key=lambda i: dist(p, centers[i])) for p in pts]
    wss = sum(dist(p, centers[l]) ** 2 for p, l in zip(pts, label))
    return label, centers, wss

def hierarchical(pts, names):
    """평균연결 응집형 군집. 합쳐진 순서와 그때의 거리를 남긴다 (덴드로그램의 재료)."""
    clusters = {i: [i] for i in range(len(pts))}
    merges = []
    while len(clusters) > 1:
        best = None
        for a in clusters:
            for b in clusters:
                if a >= b: continue
                d = st.mean([dist(pts[i], pts[j]) for i in clusters[a] for j in clusters[b]])
                if best is None or d < best[0]:
                    best = (d, a, b)
        d, a, b = best
        merges.append((names[clusters[a][0]], names[clusters[b][0]],
                       len(clusters[a]), len(clusters[b]), round(d, 3)))
        clusters[a] = clusters[a] + clusters[b]
        del clusters[b]
    return merges

def main():
    if not SRC.exists():
        sys.exit(f'원본이 없습니다: {SRC}')
    rows = load()

    # ── 5. 산점도 — 전용면적 ↔ 거래금액 ────────────────────────
    area = [r['area'] for r in rows]
    amt  = [r['amt'] for r in rows]
    r_all = pearson(area, amt)
    print(f'거래 {len(rows):,}건')
    print(f'\n산점도  전용면적 ↔ 거래금액   r = {r_all:.3f}')
    step = len(rows) // SAMPLE_N
    samp = rows[::step][:SAMPLE_N]          # 규칙적으로 솎는다. 난수를 쓰지 않는다
    print(f'  슬라이드용 표본 {len(samp)}개 ({step}건마다 하나)')
    save('07-세종군집-산점도표본.csv', ['전용면적(㎡)', '거래금액(만원)'],
         [[round(r['area'], 2), r['amt']] for r in samp])

    # ── 6·7. 동별 군집 ─────────────────────────────────────────
    by = {}
    for r in rows:
        by.setdefault(r['dong'], []).append(r['per'])
    dongs = sorted([(d, len(v), st.median(v)) for d, v in by.items() if len(v) >= MIN_N],
                   key=lambda t: -t[2])
    names = [d for d, _, _ in dongs]
    pts = zscores([[n for _, n, _ in dongs], [p for _, _, p in dongs]])

    label, centers, wss = kmeans(pts, K)
    print(f'\nK-means (k={K}, 표준화 후)   군집내 제곱합 {wss:.2f}')
    for g in range(K):
        mem = [names[i] for i, l in enumerate(label) if l == g]
        cnt = [dongs[i][1] for i, l in enumerate(label) if l == g]
        per = [dongs[i][2] for i, l in enumerate(label) if l == g]
        print(f'  군집 {g+1}  {len(mem)}개 — {" · ".join(mem)}')
        print(f'          거래건수 평균 {st.mean(cnt):,.0f}건 · ㎡당 중앙값 평균 {st.mean(per):,.0f}만원')
    save('07-세종군집-동별군집.csv', ['동', '거래건수', '㎡당중앙값(만원)', '군집'],
         [[names[i], dongs[i][1], round(dongs[i][2]), label[i] + 1] for i in range(len(names))])

    # 팔꿈치 — k 를 왜 3 으로 골랐는지 보이는 자료
    print('\n팔꿈치 (k 별 군집내 제곱합)')
    elbow = []
    for k in range(1, 7):
        _, _, w = kmeans(pts, k)
        elbow.append([k, round(w, 3)])
        print(f'  k={k}  {w:6.2f}')
    save('07-세종군집-팔꿈치.csv', ['k', '군집내제곱합'], elbow)

    merges = hierarchical(pts, names)
    print('\n계층군집 (평균연결) — 합쳐진 순서')
    for a, b, na, nb, d in merges:
        print(f'  {a}({na}) + {b}({nb})   거리 {d}')
    save('07-세종군집-계층군집.csv', ['묶음A', '묶음B', 'A크기', 'B크기', '거리'], merges)

if __name__ == '__main__':
    main()
