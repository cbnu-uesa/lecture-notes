#!/usr/bin/env python3
"""9강 보탬 계산 2 (2026-11-16) — 본 스크립트(09-세종회귀진단.py)의 load() 를 그대로 쓴다.

슬라이드의 window.REG3 를 만든다. 실행: ~/.venvs/osmnx/bin/python 09-세종회귀진단-보탬2.py > reg3.json
  desc      기술통계량 (평균 · 표준편차 · 최솟값 · 중앙값 · 최댓값)
  lin_pts   선형성 잔차도: 표본 600건의 (나이, 원래 모형 잔차, 나이² 모형 잔차).
            표본은 등분산성 잔차도(resid_pts)와 같은 600건이다 (같은 SEED, 같은 첫 추출)
"""
import importlib.util, json, pathlib
import numpy as np
import statsmodels.formula.api as smf

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('base', HERE / '09-세종회귀진단.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
d, _ = base.load()
out = {}

out['desc'] = {k: [round(float(d[k].mean()), 2), round(float(d[k].std()), 2), round(float(d[k].min()), 2),
                   round(float(d[k].median()), 2), round(float(d[k].max()), 2)]
               for k in ['per', 'new', 'age', 'area', 'floor', 't', 'high']}

m2 = smf.ols('per ~ new + age + area + floor + t', d).fit()
m3 = smf.ols('per ~ new + age + I(age**2) + area + floor + t', d).fit()
rng = np.random.default_rng(base.SEED)
idx = rng.choice(len(d), 600, replace=False)
out['lin_pts'] = [[int(d['age'].iloc[i]), round(float(m2.resid.iloc[i]), 1), round(float(m3.resid.iloc[i]), 1)]
                  for i in idx]

print(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
