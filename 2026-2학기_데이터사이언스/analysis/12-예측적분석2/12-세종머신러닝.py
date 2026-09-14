#!/usr/bin/env python3
"""12강(머신러닝의 활용)의 지도학습 사례를 만든다.

  1 의사결정나무        조건을 나눠 가며 예측. 규칙이 눈에 보인다
  2 랜덤포레스트        나무를 여럿 심어 평균
  3 그래디언트 부스팅   틀린 곳을 이어서 고친다
  4 규제회귀 릿지·라쏘  계수를 눌러 과적합을 막는다
  5 K-최근접이웃        가까운 사례의 답을 빌린다
  6 부트스트랩 예측구간 숫자 하나 대신 범위

목표변수는 ㎡당 가격(만원). 설명변수는 전용면적·건물나이·신도시여부·계약연도로,
10강 회귀와 같은 것을 쓴다 — **같은 문제를 회귀로 풀 때와 견주기 위해서다.**

입력: 10강과 같은 세종 실거래가. COMPAS SBJ_2102_001 공개 데이터.

외부 라이브러리를 쓰지 않는다. 나무·숲·부스팅·좌표하강을 직접 짠다.
난수를 쓰지 않는다 — 표본추출과 부트스트랩은 **결정적인 규칙**으로 뽑는다
(k 번째 재표본은 인덱스 (i*A + k*B) % n 을 쓴다). 몇 번을 돌려도 같은 값이 나온다.

    python3 12-세종머신러닝.py

로직: 12-세종머신러닝-로직.md 를 먼저 읽는다.
"""
import csv, math, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
FILE = '3.세종시_아파트(매매)_실거래가.csv'
SRC = (DATA / FILE if (DATA / FILE).exists()
       else pathlib.Path.home() / 'data/compas/sejong-housing' / FILE)
AREA_MIN = 60
N_SAMPLE = 3000      # 표준 라이브러리로 숲을 심으므로 표본을 줄인다
TEST_FRAC = 0.25
FEAT = ['전용면적', '건물나이', '신도시', '계약연도']

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
            rows.append({'x': [area, year - built, 1.0 if dong.endswith('동') else 0.0, year],
                         'y': amt / area})
    return rows

# ── 결정적 분할 ────────────────────────────────────────────────
def split(rows):
    """25% 를 시험용으로. 4 번째마다 하나씩 떼어 난수를 쓰지 않는다."""
    tr = [r for i, r in enumerate(rows) if i % 4]
    te = [r for i, r in enumerate(rows) if i % 4 == 0]
    return tr, te

def rmse(pred, act):
    return math.sqrt(st.mean((p - a) ** 2 for p, a in zip(pred, act)))
def mae(pred, act):
    return st.mean(abs(p - a) for p, a in zip(pred, act))
def r2(pred, act):
    m = st.mean(act)
    return 1 - sum((p - a) ** 2 for p, a in zip(pred, act)) / sum((a - m) ** 2 for a in act)

# ── 1. 회귀나무 ────────────────────────────────────────────────
class Tree:
    def __init__(self, depth=6, min_leaf=20, feats=None):
        self.depth, self.min_leaf, self.feats = depth, min_leaf, feats
    def fit(self, X, y):
        self.root = self._grow(list(range(len(y))), X, y, 0); return self
    def _grow(self, idx, X, y, d):
        vals = [y[i] for i in idx]
        node = {'v': st.mean(vals)}
        if d >= self.depth or len(idx) < 2 * self.min_leaf:
            return node
        cols = self.feats if self.feats else range(len(X[0]))
        best = None
        for c in cols:
            order = sorted(idx, key=lambda i: X[i][c])
            s = sum(y[i] for i in order); n = len(order)
            ls = 0.0; ln = 0
            for k in range(n - 1):
                ls += y[order[k]]; ln += 1
                if ln < self.min_leaf or n - ln < self.min_leaf: continue
                if X[order[k]][c] == X[order[k + 1]][c]: continue
                gain = ls * ls / ln + (s - ls) ** 2 / (n - ln)
                if best is None or gain > best[0]:
                    best = (gain, c, (X[order[k]][c] + X[order[k + 1]][c]) / 2)
        if best is None: return node
        _, c, t = best
        L = [i for i in idx if X[i][c] <= t]; R = [i for i in idx if X[i][c] > t]
        if not L or not R: return node
        node.update({'c': c, 't': t, 'L': self._grow(L, X, y, d + 1),
                     'R': self._grow(R, X, y, d + 1)})
        return node
    def one(self, x, n=None):
        n = n or self.root
        while 'c' in n:
            n = n['L'] if x[n['c']] <= n['t'] else n['R']
        return n['v']
    def predict(self, X): return [self.one(x) for x in X]

def resample(n, k):
    """복원추출한 재표본. 씨앗을 k 로 고정한 선형합동생성기라 매번 같은 표본이 나온다.
       (i*a)%n 같은 식은 순열이 되어 버려 나무가 다양해지지 않는다 — 실제로 겪었다."""
    s = 12345 + k * 6789
    out = []
    for _ in range(n):
        s = (1103515245 * s + 12345) % (1 << 31)
        out.append(s % n)
    return out

def forest(X, y, n_tree=25, depth=8, feats_per=3):
    trees = []
    for k in range(n_tree):
        idx = resample(len(y), k + 1)
        Xk = [X[i] for i in idx]; yk = [y[i] for i in idx]
        cols = [(k + j) % len(X[0]) for j in range(feats_per)]   # 나무마다 다른 변수 묶음
        trees.append(Tree(depth=depth, min_leaf=10, feats=cols).fit(Xk, yk))
    return trees

def boost(X, y, n_tree=40, depth=3, lr=0.1):
    base = st.mean(y)
    res = [v - base for v in y]
    trees = []
    for _ in range(n_tree):
        t = Tree(depth=depth, min_leaf=20).fit(X, res)
        p = t.predict(X)
        res = [r - lr * q for r, q in zip(res, p)]
        trees.append(t)
    return base, trees, lr

# ── 4. 규제회귀 ────────────────────────────────────────────────
def standardize(X):
    m = [st.mean(c) for c in zip(*X)]
    s = [st.pstdev(c) or 1 for c in zip(*X)]
    return [[(v - mi) / si for v, mi, si in zip(x, m, s)] for x in X], m, s

def ridge(X, y, lam):
    """좌표하강. 표준화한 X 를 받는다."""
    n, p = len(X), len(X[0])
    b = [0.0] * p; b0 = st.mean(y)
    for _ in range(200):
        for j in range(p):
            r = [y[i] - b0 - sum(b[k] * X[i][k] for k in range(p) if k != j) for i in range(n)]
            num = sum(X[i][j] * r[i] for i in range(n))
            b[j] = num / (sum(X[i][j] ** 2 for i in range(n)) + lam)
    return b0, b

def lasso(X, y, lam):
    n, p = len(X), len(X[0])
    b = [0.0] * p; b0 = st.mean(y)
    for _ in range(200):
        for j in range(p):
            r = [y[i] - b0 - sum(b[k] * X[i][k] for k in range(p) if k != j) for i in range(n)]
            num = sum(X[i][j] * r[i] for i in range(n))
            den = sum(X[i][j] ** 2 for i in range(n))
            b[j] = max(0.0, abs(num) - lam) * (1 if num > 0 else -1) / den
    return b0, b

def linpred(b0, b, X): return [b0 + sum(bi * xi for bi, xi in zip(b, x)) for x in X]

# ── 5. KNN ────────────────────────────────────────────────────
def knn(Xtr, ytr, Xte, k=15):
    out = []
    for x in Xte:
        d = sorted(range(len(Xtr)), key=lambda i: sum((a - b) ** 2 for a, b in zip(x, Xtr[i])))[:k]
        out.append(st.mean(ytr[i] for i in d))
    return out

def save(name, header, rows):
    p = HERE / name
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {p.name}')

def main():
    if not SRC.exists(): sys.exit(f'원본이 없습니다: {SRC}')
    rows = load()
    rows = rows[::max(1, len(rows) // N_SAMPLE)][:N_SAMPLE]
    tr, te = split(rows)
    Xtr = [r['x'] for r in tr]; ytr = [r['y'] for r in tr]
    Xte = [r['x'] for r in te]; yte = [r['y'] for r in te]
    print(f'표본 {len(rows):,}건 (전수 15,486 에서 규칙적으로 솎음)')
    print(f'학습 {len(tr):,} · 시험 {len(te):,} · 목표 ㎡당 가격(만원)')
    print(f'설명변수 {" · ".join(FEAT)}\n')

    res = []
    def score(name, pred, note=''):
        res.append([name, round(mae(pred, yte), 1), round(rmse(pred, yte), 1),
                    round(r2(pred, yte), 3), note])
        print(f'{name:<18}MAE {mae(pred, yte):>6.1f}  RMSE {rmse(pred, yte):>6.1f}  '
              f'R² {r2(pred, yte):>6.3f}   {note}')

    t = Tree(depth=6, min_leaf=20).fit(Xtr, ytr)
    score('의사결정나무', t.predict(Xte), f'깊이 6 · 학습 R² {r2(t.predict(Xtr), ytr):.3f}')
    t2 = Tree(depth=14, min_leaf=1).fit(Xtr, ytr)
    score('  깊이 14', t2.predict(Xte), f'학습 R² {r2(t2.predict(Xtr), ytr):.3f} — 학습과 시험의 벌어짐이 과적합')

    F = forest(Xtr, ytr)
    score('랜덤포레스트', [st.mean(tt.one(x) for tt in F) for x in Xte], '나무 25 · 깊이 8')

    b0, T, lr = boost(Xtr, ytr)
    score('그래디언트 부스팅',
          [b0 + lr * sum(tt.one(x) for tt in T) for x in Xte], '나무 40 · lr 0.1 · 깊이 3')

    Z, m, s = standardize(Xtr)
    Zte = [[(v - mi) / si for v, mi, si in zip(x, m, s)] for x in Xte]
    r0, rb = ridge(Z, ytr, 10.0)
    score('릿지 (λ=10)', linpred(r0, rb, Zte), ' · '.join(f'{f} {c:+.0f}' for f, c in zip(FEAT, rb)))
    l0, lb = lasso(Z, ytr, 30.0)
    score('라쏘 (λ=30)', linpred(l0, lb, Zte),
          ' · '.join(f'{f} {c:+.0f}' for f, c in zip(FEAT, lb)))

    score('K-최근접이웃', knn(Z, ytr, Zte, 15), 'k=15 · 표준화 후')

    # ── 6. 부트스트랩 예측구간 ──
    B = 30
    preds = []
    for k in range(B):
        idx = resample(len(ytr), k + 100)
        tk = Tree(depth=6, min_leaf=20).fit([Xtr[i] for i in idx], [ytr[i] for i in idx])
        preds.append(tk.predict(Xte))
    lo = []; hi = []; mid = []
    for j in range(len(Xte)):
        col = sorted(p[j] for p in preds)
        lo.append(col[int(0.05 * B)]); hi.append(col[int(0.95 * B) - 1]); mid.append(st.median(col))
    cover = sum(1 for j in range(len(yte)) if lo[j] <= yte[j] <= hi[j]) / len(yte)
    print(f'\n부트스트랩 예측구간  재표본 {B}회 · 90% 구간')
    print(f'  평균 폭 {st.mean(h - l for l, h in zip(lo, hi)):.0f}만원/㎡ · 실제 포함률 {cover*100:.1f}%')
    print('  → 구간이 담는 것은 「모형이 흔들리는 폭」이지 「값이 흩어지는 폭」이 아니다')

    save('12-세종머신러닝-모형별.csv', ['모형', 'MAE', 'RMSE', 'R2', '비고'], res)
    save('12-세종머신러닝-예측구간.csv', ['실제', '중앙예측', '하한5%', '상한95%'],
         [[round(yte[j], 1), round(mid[j], 1), round(lo[j], 1), round(hi[j], 1)]
          for j in range(0, len(yte), max(1, len(yte) // 120))])

if __name__ == '__main__':
    main()
