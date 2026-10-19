#!/usr/bin/env python3
"""6강(기술적 분석 1)의 실루엣 계수와 「2020년 단지별 군집」 실습 장에 쓰는 수치를 만든다.

07-세종군집.py 의 K-means(난수 없음)와 표준화를 그대로 가져다 쓴다.
  · 실루엣 계수   17개 동, k = 2~6 — 팔꿈치와 함께 k 를 고르는 두 번째 근거
  · 단지별 군집   2020년 계약분, 거래 10건 이상인 단지를
                  ㎡당 중앙값 · 건축년도 · 거래건수 세 변수로 묶는다

입력: 07-세종주택시장.py 와 같은 원자료.
로직: 07-세종주택시장-로직.md 의 「실루엣과 단지별 군집」 절.

    python3 07-세종단지군집.py
"""
import csv, statistics as st, pathlib, sys, importlib.util

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gj', HERE / '07-세종군집.py')
gj = importlib.util.module_from_spec(spec); spec.loader.exec_module(gj)
SRC, AREA_MIN, MIN_N = gj.SRC, gj.AREA_MIN, gj.MIN_N
YEAR      = '2020'
MIN_DANJI = 10      # 단지별 군집에 넣을 최소 거래 건수 (2020년 한 해)

def silhouette(pts, label):
    """점마다 (b − a) / max(a, b). a = 자기 군집 안 평균거리, b = 가장 가까운 다른 군집까지 평균거리."""
    ks = sorted(set(label)); out = []
    for i, p in enumerate(pts):
        own = [gj.dist(p, q) for j, q in enumerate(pts) if label[j] == label[i] and j != i]
        if not own:                     # 혼자인 군집의 점은 0 으로 둔다 (관례)
            out.append(0.0); continue
        a = st.mean(own)
        b = min(st.mean([gj.dist(p, q) for j, q in enumerate(pts) if label[j] == k])
                for k in ks if k != label[i])
        out.append((b - a) / max(a, b))
    return st.mean(out)

def load_full():
    rows = []
    with open(SRC, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get('해제사유발생일'):
                continue
            try:
                area = float(r['전용면적(㎡)'])
                amt  = int(r['거래금액(만원)'].replace(',', ''))
                built = int(r['건축년도'])
            except (ValueError, KeyError):
                continue
            if area <= AREA_MIN:
                continue
            rows.append({'year': r['계약년월'][:4], 'dong': r['시군구'].split()[-1],
                         'danji': r['단지명'], 'built': built, 'per': amt / area})
    return rows

def main():
    if not SRC.exists():
        sys.exit(f'원본이 없습니다: {SRC}')
    rows = load_full()

    # ── 실루엣 — 17개 동 ───────────────────────────────────
    by = {}
    for r in rows:
        by.setdefault(r['dong'], []).append(r['per'])
    dongs = sorted([(d, len(v), st.median(v)) for d, v in by.items() if len(v) >= MIN_N], key=lambda t: -t[2])
    pts = gj.zscores([[n for _, n, _ in dongs], [p for _, _, p in dongs]])
    print('17개 동 — k 별 군집내 제곱합과 실루엣')
    sil = []
    for k in range(2, 7):
        lab, _, w = gj.kmeans(pts, k)
        s = silhouette(pts, lab)
        sil.append([k, round(w, 3), round(s, 3)])
        print(f'  k={k}  WSS {w:6.2f}  실루엣 {s:.3f}')
    gj.save('07-세종군집-실루엣.csv', ['k', '군집내제곱합', '실루엣'], sil)

    # ── 2020년 단지별 군집 ─────────────────────────────────
    dj = {}
    for r in rows:
        if r['year'] != YEAR:
            continue
        dj.setdefault((r['dong'], r['danji']), []).append(r)
    items = [(k, len(v), st.median([x['per'] for x in v]), st.median([x['built'] for x in v]))
             for k, v in dj.items() if len(v) >= MIN_DANJI]
    items.sort(key=lambda t: -t[2])
    print(f'\n{YEAR}년 단지 — 거래 {MIN_DANJI}건 이상 {len(items)}개 (전체 {len(dj)}개 단지)')
    P = gj.zscores([[t[2] for t in items], [t[3] for t in items], [t[1] for t in items]])
    print('  k 별 군집내 제곱합과 실루엣')
    tab = []
    for k in range(2, 8):
        lab, _, w = gj.kmeans(P, k)
        s = silhouette(P, lab)
        tab.append([k, round(w, 3), round(s, 3)])
        print(f'    k={k}  WSS {w:7.2f}  실루엣 {s:.3f}')
    gj.save('07-세종단지군집-k선택.csv', ['k', '군집내제곱합', '실루엣'], tab)
    K = max(tab, key=lambda t: t[2])[0]
    lab, _, _ = gj.kmeans(P, K)
    print(f'  실루엣이 가장 큰 k = {K}')
    out = []
    for g in range(K):
        m = [items[i] for i, l in enumerate(lab) if l == g]
        print(f'  군집 {g+1}  {len(m)}개 단지 · ㎡당 {st.mean([t[2] for t in m]):.0f}만원 · '
              f'건축 {st.mean([t[3] for t in m]):.0f}년 · 거래 {st.mean([t[1] for t in m]):.1f}건')
        print('         ', ' · '.join(f'{t[0][1]}({t[0][0]})' for t in m[:6]), '…' if len(m) > 6 else '')
    for i, t in enumerate(items):
        out.append([t[0][0], t[0][1], t[1], round(t[2]), round(t[3]), lab[i] + 1])
    gj.save('07-세종단지군집-결과.csv', ['동', '단지명', '거래건수', '㎡당중앙값(만원)', '건축년도', '군집'], out)

if __name__ == '__main__':
    main()
