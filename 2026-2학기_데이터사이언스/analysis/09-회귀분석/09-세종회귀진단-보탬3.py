#!/usr/bin/env python3
"""9강 보탬 계산 3 (2026-11-16) — 선형성 위배의 해결책 네 가지를 같은 자료로 비교한다.

슬라이드 「선형성 위배의 해결책 비교」 장의 숫자를 만든다.
실행: ~/.venvs/osmnx/bin/python 09-세종회귀진단-보탬3.py   (analysis/ 에서)

- 자료: 학생에게 나눠 준 세종_아파트_회귀자료.csv (15,486건)
- 가격 단위 R²: 로그 모형은 예측값을 exp 로 되돌리고 smearing 보정(잔차 exp 평균)을 곱해
  가격(만원/㎡) 기준으로 다시 계산한다. 그래야 가격 모형과 같은 기준으로 견줄 수 있다.
- 나이 구간별 잔차 평균: 가격 모형은 만원/㎡, 로그 모형은 % (잔차 × 100)
- RESET: 적합값 2·3제곱, F 검정
- RESET 기각률: 거래를 n건씩 200번 뽑아 p < .05 인 비율 (seed 10)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import linear_reset

HERE = Path(__file__).resolve().parent
CSV = HERE.parent / 'data/학생배포/09강-세종아파트회귀/세종_아파트_회귀자료.csv'

d = pd.read_csv(CSV)
d['ly'] = np.log(d.per)
d['b'] = pd.cut(d.age, [-1, 2, 5, 8, 11, 15, 20, 25, 40])
d['a5'] = pd.cut(d.age, [-1, 4, 9, 14, 19, 24, 40]).astype(str)
X = 'new + age + area + floor + t'

MODELS = [
    ('원래', f'per ~ {X}'),
    ('① 로그', f'ly ~ {X}'),
    ('② 나이²', f'per ~ {X} + I(age**2)'),
    ('③ 5년 더미', 'per ~ C(a5) + new + area + floor + t'),
    ('③ 5년 더미 + 로그', 'ly ~ C(a5) + new + area + floor + t'),
    # 신도시 여부는 단지가 정하므로 단지 고정효과에 흡수된다 → new 를 뺀다
    ('④ 단지 고정효과', 'per ~ age + area + floor + t + C(complex)'),
    ('④ 단지 고정효과 + 로그', 'ly ~ age + area + floor + t + C(complex)'),
]

out = {'models': []}
for name, f in MODELS:
    m = smf.ols(f, d).fit()
    log = f.startswith('ly')
    if log:
        yhat = np.exp(m.fittedvalues) * np.mean(np.exp(m.resid))
        rbin = (100 * m.resid).groupby(d.b, observed=True).mean()
    else:
        yhat = m.fittedvalues
        rbin = m.resid.groupby(d.b, observed=True).mean()
    r2p = 1 - ((d.per - yhat) ** 2).sum() / ((d.per - d.per.mean()) ** 2).sum()
    rs = linear_reset(m, power=[2, 3], use_f=True)
    out['models'].append({
        'name': name, 'k_extra': int(m.df_model) - 5, 'r2_price': round(float(r2p), 3),
        'reset_F': round(float(rs.fvalue), 1), 'reset_p': float(rs.pvalue),
        'resid_bin': [round(float(v), 1) for v in rbin], 'resid_unit': '%' if log else '만원',
    })

# 단지 안에서 나이가 움직이는 폭 (계약 시점과 함께 움직인다)
span = d.groupby('complex').age.agg(lambda s: s.max() - s.min())
out['complex_age_span'] = {'n_complex': int(span.size), 'min': int(span.min()), 'max': int(span.max())}

# 계수 안정성: 로그 → 로그 + 나이²
m1 = smf.ols(f'ly ~ {X}', d).fit()
m2 = smf.ols(f'ly ~ {X} + I(age**2)', d).fit()
def eff(m, a0, a1):
    e = m.params['age'] * (a1 - a0)
    if 'I(age ** 2)' in m.params:
        e += m.params['I(age ** 2)'] * (a1 ** 2 - a0 ** 2)
    return round(100 * (np.exp(e) - 1), 1)
out['stability'] = {
    'age_0_20': [eff(m1, 0, 20), eff(m2, 0, 20)],
    'age_0_10': [eff(m1, 0, 10), eff(m2, 0, 10)],
    'new': [round(m1.params['new'], 3), round(m2.params['new'], 3)],
    't': [round(m1.params['t'], 3), round(m2.params['t'], 3)],
    'age_pct_per_year': round(100 * (np.exp(m1.params['age']) - 1), 1),
}

# 표본 크기별 RESET 기각률
rng = np.random.default_rng(10)
rej = {}
for name, f in [('원래', f'per ~ {X}'), ('로그', f'ly ~ {X}')]:
    rej[name] = {}
    for n in (100, 300, 1000, 3000):
        k = 0
        for _ in range(200):
            s = d.sample(n, random_state=int(rng.integers(1e9)))
            k += linear_reset(smf.ols(f, s).fit(), power=[2, 3], use_f=True).pvalue < .05
        rej[name][n] = k / 200
out['reset_reject_rate'] = rej

print(json.dumps(out, ensure_ascii=False, indent=1))
