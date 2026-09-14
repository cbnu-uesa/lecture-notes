#!/usr/bin/env python3
"""11강(추세예측)의 나이브·이동평균·지수평활·홀트 계열 사례를 만든다.

11-화성인구.py 가 회귀 기반 예측(방법 6)을 맡고, 이 스크립트가 나머지 다섯을 맡는다.
  1 나이브 예측       마지막 값을 그대로
  2 이동평균          최근 k 개의 평균
  3 단순지수평활      최근에 가중치를 더
  4 홀트 선형추세     수준과 기울기를 함께 갱신
  5 홀트-윈터스 계절  계절 주기까지

같은 홀드아웃(마지막 12개월)과 같은 MAPE 로 채점해 방법 6 과 나란히 견줄 수 있게 한다.
평활상수는 격자탐색으로 **학습구간 MAPE 를 최소로** 하는 값을 고른다 — 손으로 정하지 않는다.

    python3 11-화성인구-평활.py

로직: 11-화성인구-로직.md 의 「평활 계열」 절.
"""
import csv, importlib.util, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
HOLDOUT = 12
SEASON = 12          # 월 자료의 계절 주기

# 원자료 읽기는 옆 스크립트의 것을 그대로 쓴다 — 같은 계열이어야 비교가 성립한다
spec = importlib.util.spec_from_file_location('base', HERE / '11-화성인구.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def mape(pred, actual):
    return st.mean(abs(p - a) / a * 100 for p, a in zip(pred, actual))

# ── 다섯 방법. 모두 「학습구간으로 상태를 만들고 검증구간을 한 걸음씩 내다본다」 ──

def naive(train, h):
    return [train[-1]] * h

def moving_avg(train, h, k):
    hist = list(train)
    out = []
    for _ in range(h):
        out.append(st.mean(hist[-k:]))
        hist.append(out[-1])            # 자기 예측을 이어 붙여 다음을 낸다
    return out

def ses(train, h, a):
    """단순지수평활. 수준만 갱신하므로 예측은 평평한 직선이다."""
    lv = train[0]
    for y in train[1:]:
        lv = a * y + (1 - a) * lv
    return [lv] * h

def holt(train, h, a, b):
    """수준과 기울기를 함께 갱신한다. 예측은 기울어진 직선이다."""
    lv, tr = train[0], train[1] - train[0]
    for y in train[1:]:
        prev = lv
        lv = a * y + (1 - a) * (lv + tr)
        tr = b * (lv - prev) + (1 - b) * tr
    return [lv + (i + 1) * tr for i in range(h)]

def holt_winters(train, h, a, b, g, m=SEASON):
    """가법 계절. 초기 계절지수는 첫 주기의 평균 대비 편차로 잡는다."""
    if len(train) < 2 * m:
        return None
    lv = st.mean(train[:m])
    tr = (st.mean(train[m:2 * m]) - st.mean(train[:m])) / m
    se = [train[i] - lv for i in range(m)]
    for i, y in enumerate(train):
        s = se[i % m]
        prev = lv
        lv = a * (y - s) + (1 - a) * (lv + tr)
        tr = b * (lv - prev) + (1 - b) * tr
        se[i % m] = g * (y - lv) + (1 - g) * s
    return [lv + (i + 1) * tr + se[(len(train) + i) % m] for i in range(h)]

def grid(fn, train, h, actual, space):
    """학습구간 안에서 다시 홀드아웃을 떼어 상수를 고른다. 검증구간은 보지 않는다."""
    inner = len(train) - HOLDOUT
    best = None
    for p in space:
        got = fn(train[:inner], HOLDOUT, *p)
        if got is None:
            continue
        e = mape(got, train[inner:])
        if best is None or e < best[0]:
            best = (e, p)
    return best[1] if best else None

def main():
    if not base.SRC.exists():
        sys.exit(f'원본이 없습니다: {base.SRC}')
    s = base.read_series()
    ys = [v for _, v in s]
    tr, te = ys[:-HOLDOUT], ys[-HOLDOUT:]
    print(f'관측 {len(ys)}개월 · 학습 {len(tr)} · 검증 {len(te)}')
    print(f'{s[0][0]} {ys[0]:,}명 → {s[-1][0]} {ys[-1]:,}명\n')

    R = [round(x / 20, 2) for x in range(1, 20)]          # 0.05 ~ 0.95
    rows = []

    rows.append(('나이브', naive(tr, HOLDOUT), '—'))
    k = grid(moving_avg, tr, HOLDOUT, te, [(k,) for k in range(2, 25)])[0]
    rows.append((f'이동평균 k={k}', moving_avg(tr, HOLDOUT, k), f'k={k}'))
    a = grid(ses, tr, HOLDOUT, te, [(a,) for a in R])[0]
    rows.append(('단순지수평활', ses(tr, HOLDOUT, a), f'α={a}'))
    ab = grid(holt, tr, HOLDOUT, te, [(a, b) for a in R for b in R])
    rows.append(('홀트 선형추세', holt(tr, HOLDOUT, *ab), f'α={ab[0]} β={ab[1]}'))
    abg = grid(holt_winters, tr, HOLDOUT, te,
               [(a, b, g) for a in R[::2] for b in R[::2] for g in R[::2]])
    if abg:
        rows.append(('홀트-윈터스', holt_winters(tr, HOLDOUT, *abg), f'α={abg[0]} β={abg[1]} γ={abg[2]}'))

    print(f"{'방법':<16}{'검증 MAPE':>10}{'마지막 달 예측':>16}   고른 상수")
    out = []
    for name, pred, par in rows:
        e = mape(pred, te)
        print(f'{name:<16}{e:>9.2f}%{pred[-1]:>16,.0f}   {par}')
        out.append([name, round(e, 3), round(pred[-1]), par])
    print(f'\n실제 {s[-1][0]} = {te[-1]:,}명')
    print('참고 — 회귀 기반(방법 6)의 검증 MAPE 는 11-화성인구.py 가 낸다')

    path = HERE / '11-화성인구-평활.csv'
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['방법', '검증MAPE(%)', '마지막달예측(명)', '고른상수'])
        w.writerows(out)
    print(f'  → {path.name}')

    # 슬라이드의 그림이 쓸 예측 경로도 남긴다
    path = HERE / '11-화성인구-예측경로.csv'
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['연월', '실제'] + [r[0] for r in rows])
        for i in range(HOLDOUT):
            w.writerow([s[-HOLDOUT + i][0].strftime('%Y-%m'), te[i]] +
                       [round(r[1][i]) for r in rows])
    print(f'  → {path.name}')

if __name__ == '__main__':
    main()
