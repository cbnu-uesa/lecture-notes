#!/usr/bin/env python3
"""10강(회귀분석)의 상호작용항·로그선형·로지스틱 사례를 만든다.

  4 상호작용항 회귀  효과가 집단마다 다른가
  5 로그-선형 회귀   관계를 비율(%)로 읽는다
  6 로지스틱 회귀    결과가 예/아니오일 때

10-세종회귀.py 가 1~3번(단순·다중·더미)을 맡고, 이 스크립트가 나머지 셋을 맡는다.
같은 자료·같은 걸러내기를 쓴다.

외부 라이브러리를 쓰지 않는다. 정규방정식은 가우스 소거로,
로지스틱은 뉴턴-랩슨(IRLS)으로 직접 푼다. 난수를 쓰지 않는다.

    python3 10-세종회귀확장.py

로직: 10-세종회귀확장-로직.md 를 먼저 읽는다.
"""
import csv, math, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
FILE = '3.세종시_아파트(매매)_실거래가.csv'
SRC = (DATA / FILE if (DATA / FILE).exists()
       else pathlib.Path.home() / 'data/compas/sejong-housing' / FILE)
AREA_MIN = 60

def load():
    rows = []
    with open(SRC, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get('해제사유발생일'): continue
            try:
                area = float(r['전용면적(㎡)'])
                amt  = int(r['거래금액(만원)'].replace(',', ''))
                built = int(r['건축년도'])
                year  = int(r['계약년월'][:4])
            except (ValueError, KeyError):
                continue
            if area <= AREA_MIN: continue
            dong = r['시군구'].split()[-1]
            # 세종은 신도시가 '동', 편입 읍면지역이 '리' 로 깨끗이 갈린다
            rows.append({'per': amt / area, 'area': area, 'age': year - built,
                         'new': 1.0 if dong.endswith('동') else 0.0, 'year': year})
    return rows

def ols(X, y):
    """정규방정식을 가우스 소거로 푼다. X 의 첫 열은 1 이어야 한다."""
    k = len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(len(y))) for b in range(k)] +
         [sum(X[i][a] * y[i] for i in range(len(y)))] for a in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        for r in range(k):
            if r == c: continue
            f = A[r][c] / A[c][c]
            for j in range(c, k + 1): A[r][j] -= f * A[c][j]
    return [A[i][k] / A[i][i] for i in range(k)]

def r2_of(X, y, b):
    pred = [sum(bi * xi for bi, xi in zip(b, x)) for x in X]
    m = st.mean(y)
    return 1 - sum((p - a) ** 2 for p, a in zip(pred, y)) / sum((a - m) ** 2 for a in y)

def logistic(X, y, iters=25):
    """뉴턴-랩슨(IRLS). 가중최소제곱을 되풀이해 계수를 구한다."""
    k = len(X[0]); b = [0.0] * k
    for _ in range(iters):
        p = [1 / (1 + math.exp(-max(-30, min(30, sum(bi * xi for bi, xi in zip(b, x)))))) for x in X]
        w = [max(pi * (1 - pi), 1e-6) for pi in p]
        z = [sum(bi * xi for bi, xi in zip(b, X[i])) + (y[i] - p[i]) / w[i] for i in range(len(y))]
        A = [[sum(w[i] * X[i][a] * X[i][c] for i in range(len(y))) for c in range(k)] +
             [sum(w[i] * X[i][a] * z[i] for i in range(len(y)))] for a in range(k)]
        for c in range(k):
            q = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[q] = A[q], A[c]
            for r in range(k):
                if r == c: continue
                f = A[r][c] / A[c][c]
                for j in range(c, k + 1): A[r][j] -= f * A[c][j]
        nb = [A[i][k] / A[i][i] for i in range(k)]
        if max(abs(a - c) for a, c in zip(nb, b)) < 1e-8:
            b = nb; break
        b = nb
    return b

def save(name, header, rows):
    p = HERE / name
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {p.name}')

def main():
    if not SRC.exists(): sys.exit(f'원본이 없습니다: {SRC}')
    rows = load()
    print(f'표본 {len(rows):,}건 (전용 {AREA_MIN}㎡ 초과, 취소 제외)\n')
    out = []

    # ── 4. 상호작용항 ─────────────────────────────────────────
    y = [r['per'] for r in rows]
    X0 = [[1.0, r['new'], r['age']] for r in rows]
    X1 = [[1.0, r['new'], r['age'], r['new'] * r['age']] for r in rows]
    b0 = ols(X0, y); b1 = ols(X1, y)
    print('상호작용항 — 건물나이의 효과가 신도시와 편입에서 다른가')
    print(f'  주효과만   ㎡당 = {b0[0]:.0f} {b0[1]:+.0f}·신도시 {b0[2]:+.2f}·나이            R² {r2_of(X0, y, b0):.3f}')
    print(f'  +상호작용  ㎡당 = {b1[0]:.0f} {b1[1]:+.0f}·신도시 {b1[2]:+.2f}·나이 {b1[3]:+.2f}·(신도시×나이)  R² {r2_of(X1, y, b1):.3f}')
    print(f'  → 나이 1년의 효과: 편입 {b1[2]:+.2f}만원 · 신도시 {b1[2] + b1[3]:+.2f}만원')
    out += [['4 상호작용 주효과만', round(b0[0], 1), round(b0[1], 1), round(b0[2], 2), '', round(r2_of(X0, y, b0), 3)],
            ['4 상호작용 포함', round(b1[0], 1), round(b1[1], 1), round(b1[2], 2), round(b1[3], 2), round(r2_of(X1, y, b1), 3)]]

    # ── 5. 로그-선형 ─────────────────────────────────────────
    ly = [math.log(r['per']) for r in rows]
    Xl = [[1.0, r['new'], r['age'], r['area']] for r in rows]
    bl = ols(Xl, ly)
    print('\n로그-선형 — ln(㎡당 가격) 을 설명한다')
    print(f'  ln(㎡당) = {bl[0]:.3f} {bl[1]:+.3f}·신도시 {bl[2]:+.4f}·나이 {bl[3]:+.5f}·면적   R² {r2_of(Xl, ly, bl):.3f}')
    print(f'  → 신도시이면 {(math.exp(bl[1]) - 1) * 100:+.1f}% · 나이 1년마다 {(math.exp(bl[2]) - 1) * 100:+.2f}%')
    print('  계수를 그대로 읽으면 안 된다. exp 를 취해 비율로 옮긴다')
    out.append(['5 로그-선형', round(bl[0], 3), round(bl[1], 3), round(bl[2], 4), round(bl[3], 5), round(r2_of(Xl, ly, bl), 3)])

    # ── 6. 로지스틱 ──────────────────────────────────────────
    med = st.median(y)
    yb = [1.0 if r['per'] > med else 0.0 for r in rows]
    Xb = [[1.0, r['new'], r['age'] / 10, r['area'] / 100] for r in rows]
    bb = logistic(Xb, yb)
    p = [1 / (1 + math.exp(-max(-30, min(30, sum(c * xi for c, xi in zip(bb, x)))))) for x in Xb]
    acc = st.mean(1.0 if (pi > 0.5) == (yi > 0.5) else 0.0 for pi, yi in zip(p, yb))
    print(f'\n로지스틱 — 「㎡당 가격이 중앙값({med:.0f}만원)을 넘는가」')
    print(f'  logit = {bb[0]:.3f} {bb[1]:+.3f}·신도시 {bb[2]:+.3f}·(나이/10) {bb[3]:+.3f}·(면적/100)')
    print(f'  승산비  신도시 {math.exp(bb[1]):.2f}배 · 나이 10년 {math.exp(bb[2]):.2f}배 · 면적 100㎡ {math.exp(bb[3]):.2f}배')
    print(f'  적중률 {acc * 100:.1f}%  (기준선 50%)')
    out.append(['6 로지스틱', round(bb[0], 3), round(bb[1], 3), round(bb[2], 3), round(bb[3], 3), round(acc, 3)])

    save('10-세종회귀확장.csv',
         ['모형', '절편', '신도시', '나이(또는 나이/10)', '넷째항', 'R2 또는 적중률'], out)

if __name__ == '__main__':
    main()
