#!/usr/bin/env python3
"""10강 보탬 계산 (2026-11-14) — 본 스크립트의 load() 와 분할(SEED 10, 80:20)을 그대로 쓴다.

슬라이드의 window.ML2 를 만든다. 실행: ~/.venvs/osmnx/bin/python 10-세종랜덤포레스트-보탬.py
  boot63   복원추출 한 번에 원자료가 뽑히는 비율 (이론 1 − 1/e 와 실제)
  rf_depth 숲의 최대 깊이별 훈련 · 시험 R² (나무 100)
  rf_leaf  잎의 최소 거래 수별 훈련 · 시험 R²
  rf_feat  질문마다 볼 변수 비율별 시험 R²
  cmp      회귀계수와 SHAP 기울기 · 표준화계수와 평균 |SHAP| 순위
  one_lin  폭포 그림 거래 한 건의 선형회귀 몫
"""
import importlib.util, json, pathlib
import numpy as np
import statsmodels.formula.api as smf
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('base', HERE / '10-세종랜덤포레스트.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
d = B.load(); F = B.FEAT
X, y = d[F].values, d['per'].values
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=B.SEED)
out = {}
rng = np.random.default_rng(10); n = len(Xtr)
fr = [len(np.unique(rng.integers(0, n, n))) / n for _ in range(20)]
out['boot63'] = {'theory': float(1 - np.exp(-1)), 'mean': float(np.mean(fr)), 'n': n}

def fit(**kw):
    p = dict(n_estimators=100, min_samples_leaf=5, max_features=0.6, random_state=B.SEED, n_jobs=-1); p.update(kw)
    m = RandomForestRegressor(**p).fit(Xtr, ytr)
    return [round(float(r2_score(ytr, m.predict(Xtr))), 4), round(float(r2_score(yte, m.predict(Xte))), 4)]
out['rf_depth'] = [[k or 0] + fit(max_depth=k) for k in (2, 4, 6, 8, 10, 12, 15, 20, None)]
out['rf_leaf'] = [[k] + fit(min_samples_leaf=k) for k in (1, 2, 5, 10, 20, 50, 100, 200)]
out['rf_feat'] = [[k] + fit(max_features=k) for k in (0.2, 0.4, 0.6, 0.8, 1.0)]

import shap
rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.6, random_state=B.SEED, n_jobs=-1).fit(Xtr, ytr)
idx = np.random.default_rng(B.SEED).choice(len(Xte), 400, replace=False)
sv = shap.TreeExplainer(rf).shap_values(Xte[idx])
lm = smf.ols('per ~ ' + ' + '.join(F), d).fit()
z = d[['per'] + F].apply(lambda s: (s - s.mean()) / s.std())
beta = smf.ols('per ~ ' + ' + '.join(F), z).fit().params
cmp = []
for j, f in enumerate(F):
    slope = float(np.polyfit(Xte[idx, j], sv[:, j], 1)[0])
    cmp.append({'f': f, 'b': float(lm.params[f]), 'beta': float(beta[f]), 'shap_slope': slope,
                'mean_abs': float(np.abs(sv[:, j]).mean())})
out['cmp'] = cmp
# 폭포 그림의 거래 한 건: 선형회귀(훈련 자료)의 몫 = 계수 × (x − 훈련 평균)
from sklearn.linear_model import LinearRegression
lr = LinearRegression().fit(Xtr, ytr)
x1 = np.array([1.0, 2.0, 99.94, 11.0, 0.5])
mu = Xtr.mean(0)
out['one_lin'] = {'base': float(ytr.mean()), 'contrib': {f: float(lr.coef_[j] * (x1[j] - mu[j])) for j, f in enumerate(F)},
                  'pred': float(lr.predict(x1[None])[0]), 'mu': {f: float(mu[j]) for j, f in enumerate(F)}}
print(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
