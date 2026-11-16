#!/usr/bin/env python3
"""9강 보탬 계산 (2026-11-13) — 본 스크립트(09-세종회귀진단.py)의 load() 를 그대로 쓴다.

슬라이드의 window.REG2 를 만든다. 실행: ~/.venvs/osmnx/bin/python 09-세종회귀진단-보탬.py > reg2.json
  all_pts   최소제곱 산점도에 전체 15,486건을 찍기 위한 (나이, ㎡당 가격)
  std       변수를 모두 표준화해 넣은 회귀의 계수 (= 계수 × sx/sy 인지 확인)
  lin       나이 제곱항을 넣은 모형의 나이별 잔차 평균
  icc       단지별 잔차의 급내상관 · 설계효과 · 유효 표본 수, 단지 12곳의 잔차
  mon       계약 월별 고가 비율과 월 하나만 넣은 선형확률 · 로지스틱
  two       신도시 × 고가 2×2 표
  roc       다섯 변수 로지스틱의 ROC 점 · AUC · 예측확률 분포
"""
import importlib.util, json, pathlib
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import linear_reset

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('base', HERE / '09-세종회귀진단.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
d, _ = base.load()
rng = np.random.default_rng(9)
out = {}

out['all_pts'] = [int(v) for ab in zip(d['age'], d['per'].round()) for v in ab]

X = ['new', 'age', 'area', 'floor', 't']
z = d[['per'] + X].apply(lambda s: (s - s.mean()) / s.std())
mz = smf.ols('per ~ ' + ' + '.join(X), z).fit()
out['std'] = {k: float(mz.params[k]) for k in X}
out['sd'] = {k: float(d[k].std()) for k in ['per'] + X}

f = 'per ~ new + age + area + floor + t'
m2 = smf.ols(f, d).fit()
m3 = smf.ols('per ~ new + age + I(age**2) + area + floor + t', d).fit()
d['r3'] = m3.resid
b = d.groupby('age')['r3'].agg(['mean', 'size']).reset_index()
out['lin'] = {'bin': [[int(a), round(float(mn), 1), int(n)] for a, mn, n in b.values if n >= 30],
              'b_age': float(m3.params['age']), 'b_age2': float(m3.params['I(age ** 2)']),
              'p_age2': float(m3.pvalues['I(age ** 2)']), 'r2': float(m3.rsquared),
              'reset_F': float(linear_reset(m3, power=2, use_f=True).fvalue),
              'reset_p': float(linear_reset(m3, power=2, use_f=True).pvalue)}

d['r'] = m2.resid
g = d.groupby('complex')['r']
k, n = g.ngroups, len(d)
ni = g.size()
msb = float((ni * (g.mean() - d['r'].mean()) ** 2).sum() / (k - 1))
msw = float(((d['r'] - g.transform('mean')) ** 2).sum() / (n - k))
n0 = float((n - (ni ** 2).sum() / n) / (k - 1))
icc = (msb - msw) / (msb + (n0 - 1) * msw)
mbar = n / k
deff = 1 + (mbar - 1) * icc
big = ni.sort_values(ascending=False).head(40).index
means = g.mean().loc[big].sort_values()
pick = list(means.index[[0, 3, 7, 11, 15, 19, 23, 27, 31, 35, 38, 39]])
cl = []
for c in pick:
    r = d.loc[d['complex'] == c, 'r']
    s = r.sample(min(30, len(r)), random_state=9)
    cl.append({'n': int(len(r)), 'mean': round(float(r.mean()), 1), 'pts': [round(float(v)) for v in s]})
out['icc'] = {'icc': float(icc), 'k': int(k), 'mbar': float(mbar), 'median': float(ni.median()),
              'deff': float(deff), 'neff': float(n / deff), 'sd_resid': float(d['r'].std()), 'cl': cl}

d['mon'] = (d['계약년월'] // 100 - 2017) * 12 + d['계약년월'] % 100 - 1
mm = d.groupby('mon')['high'].agg(['mean', 'size']).reset_index()
l1 = smf.ols('high ~ mon', d).fit(); g1 = smf.logit('high ~ mon', d).fit(disp=0)
pl = l1.predict(pd.DataFrame({'mon': np.arange(-24, 73)}))
out['mon'] = {'pts': [[int(a), round(float(p), 3), int(s)] for a, p, s in mm.values],
              'lpm': [float(l1.params['Intercept']), float(l1.params['mon'])],
              'logit': [float(g1.params['Intercept']), float(g1.params['mon'])],
              'or': float(np.exp(g1.params['mon'])), 'or12': float(np.exp(12 * g1.params['mon']))}

t2 = pd.crosstab(d['new'], d['high'])
out['two'] = [[int(t2.loc[a, b]) for b in (1, 0)] for a in (1, 0)]   # [신도시[고가, 아님], 편입[고가, 아님]]

lg = smf.logit('high ~ new + age + area + floor + t', d).fit(disp=0)
p = lg.predict(); y = d['high'].values
P, N = y.sum(), (1 - y).sum()
roc = []
for c in np.round(np.arange(0, 1.0001, 0.02), 2):
    pr = p > c
    roc.append([float(c), round(float((pr & (y == 0)).sum() / N), 4), round(float((pr & (y == 1)).sum() / P), 4)])
o = np.argsort(-p); tp = np.cumsum(y[o]) / P; fp = np.cumsum(1 - y[o]) / N
auc = float(np.trapezoid(np.r_[0, tp], np.r_[0, fp]))
h0, e = np.histogram(p[y == 0], bins=20, range=(0, 1)); h1, _ = np.histogram(p[y == 1], bins=20, range=(0, 1))
out['roc'] = {'pts': roc, 'auc': auc, 'h0': h0.tolist(), 'h1': h1.tolist()}
print(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
