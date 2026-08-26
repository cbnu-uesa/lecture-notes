#!/usr/bin/env python3
"""10강(진단적 분석 Ⅱ) — 7강에서 던진 질문에 답한다.

  "동별 ㎡당 가격이 5.33배 차이 나는데, 위치 때문인가 건축 연한 때문인가?"

입력: ~/data/compas/sejong-housing/3.세종시_아파트(매매)_실거래가.csv
로직: 10-세종회귀-로직.md 를 먼저 읽는다.
외부 라이브러리를 쓰지 않는다 — 정규방정식을 가우스 소거로 직접 푼다.
"""
import csv, pathlib, statistics as st, sys

SRC = pathlib.Path.home() / 'data/compas/sejong-housing/3.세종시_아파트(매매)_실거래가.csv'
AREA_MIN = 60

def ols(X, y):
    """(X'X)b = X'y. X 는 절편 열을 포함한다. 반환: 계수, R²"""
    k, n = len(X[0]), len(y)
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] +
         [sum(X[i][a] * y[i] for i in range(n))] for a in range(k)]
    for c in range(k):                                   # 부분 피벗팅
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        for r in range(k):
            if r == c:
                continue
            f = A[r][c] / A[c][c]
            for j in range(c, k + 1):
                A[r][j] -= f * A[c][j]
    b = [A[i][k] / A[i][i] for i in range(k)]
    yh = [sum(b[j] * X[i][j] for j in range(k)) for i in range(n)]
    my = st.mean(y)
    return b, 1 - sum((y[i]-yh[i])**2 for i in range(n)) / sum((v-my)**2 for v in y)

def load():
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
            if area <= AREA_MIN or built < 1960:
                continue
            dong = r['시군구'].split()[-1]
            year = int(r['계약년월'][:4])
            rows.append({'per': amt / area,
                         # 세종은 신도시가 '동', 편입 읍면지역이 '리' 로 깨끗이 갈린다
                         'new': 1 if dong.endswith('동') else 0,
                         'age': year - built, 'area': area})
    return rows

def main():
    if not SRC.exists():
        sys.exit(f'원본이 없습니다: {SRC}')
    rows = load()
    y = [r['per'] for r in rows]
    nw = [r['per'] for r in rows if r['new']]
    od = [r['per'] for r in rows if not r['new']]

    print(f'표본 {len(rows):,}건 (신도시 {len(nw):,} · 편입 {len(od):,})')
    print(f'㎡당 중앙값   신도시 {st.median(nw):.0f} · 편입 {st.median(od):.0f} 만원')
    print(f'건물나이 중앙값 신도시 {st.median([r["age"] for r in rows if r["new"]]):.0f} · '
          f'편입 {st.median([r["age"] for r in rows if not r["new"]]):.0f} 년\n')

    b1, r1 = ols([[1, r['new']] for r in rows], y)
    b2, r2 = ols([[1, r['new'], r['age']] for r in rows], y)
    b3, r3 = ols([[1, r['new'], r['age'], r['area']] for r in rows], y)
    print(f'모형1  ㎡당 = {b1[0]:.0f} + {b1[1]:.0f}·신도시                       R² {r1:.3f}')
    print(f'모형2  ㎡당 = {b2[0]:.0f} + {b2[1]:.0f}·신도시 {b2[2]:+.1f}·나이            R² {r2:.3f}')
    print(f'모형3  ㎡당 = {b3[0]:.0f} + {b3[1]:.0f}·신도시 {b3[2]:+.1f}·나이 {b3[3]:+.2f}·면적  R² {r3:.3f}')
    print(f'\n신도시 계수 {b1[1]:.0f} → {b2[1]:.0f} ({(1-b2[1]/b1[1])*100:.0f}% 감소)')

if __name__ == '__main__':
    main()
