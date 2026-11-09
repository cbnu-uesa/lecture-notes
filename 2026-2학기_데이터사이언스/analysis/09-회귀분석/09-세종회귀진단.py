#!/usr/bin/env python3
"""9강(회귀분석) — 세종 아파트 ㎡당 가격으로 회귀계수·유의성·가정 진단·로지스틱을 보인다.

입력: analysis/data/3.세종시_아파트(매매)_실거래가.csv (6·10강과 같은 자료, 같은 걸러내기)
로직: 09-세종회귀진단-로직.md
실행: ~/.venvs/osmnx/bin/python 09-세종회귀진단.py [--slide]
      statsmodels·scipy·pandas 가 필요하다. Drive 안에서 pip install 하지 않는다.
--slide 를 주면 슬라이드에 넣을 JSON(window.REG)을 찍는다.
"""
import json, pathlib, sys
import numpy as np, pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from statsmodels.stats.outliers_influence import variance_inflation_factor

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / 'data' / '3.세종시_아파트(매매)_실거래가.csv'
SEED = 9


def load():
    d = pd.read_csv(SRC, encoding='utf-8-sig')
    n0 = len(d)
    d = d[d['해제사유발생일'].isna()]
    n1 = len(d)
    d = d[(d['전용면적(㎡)'] > 60) & (d['건축년도'] >= 1960)].copy()
    d['amt'] = d['거래금액(만원)'].str.replace(',', '').astype(int)
    d['per'] = d['amt'] / d['전용면적(㎡)']                 # ㎡당 가격(만원)
    dong = d['시군구'].str.split().str[-1]
    d['new'] = dong.str.endswith('동').astype(int)           # 신도시(동)=1, 편입 읍면(리)=0
    d['year'] = d['계약년월'] // 100
    d['age'] = d['year'] - d['건축년도']
    d['area'] = d['전용면적(㎡)']
    d['floor'] = d['층']
    d['t'] = d['year'] - 2017                                 # 2017년=0
    d['high'] = (d['per'] > d['per'].median()).astype(int)    # 로지스틱의 y
    d['complex'] = d['시군구'] + ' ' + d['단지명']
    return d.reset_index(drop=True), (n0, n1)


def coef_table(m, names):
    ci = m.conf_int()
    return [{'name': k, 'b': float(m.params[k]), 'se': float(m.bse[k]), 't': float(m.tvalues[k]),
             'p': float(m.pvalues[k]), 'lo': float(ci.loc[k, 0]), 'hi': float(ci.loc[k, 1])}
            for k in names]


def main():
    d, (n0, n1) = load()
    out = {'n_raw': n0, 'n_cancel': n0 - n1, 'n': len(d), 'n_new': int(d['new'].sum()),
           'median_per': float(d['per'].median())}

    # 1) 단순회귀 — 나이 하나
    m1 = smf.ols('per ~ age', d).fit()
    # 2) 다중회귀 — 본 모형
    f = 'per ~ new + age + area + floor + t'
    m2 = smf.ols(f, d).fit()
    names = ['Intercept', 'new', 'age', 'area', 'floor', 't']
    out['simple'] = {'b0': float(m1.params['Intercept']), 'b1': float(m1.params['age']),
                     'r2': float(m1.rsquared)}
    out['ols'] = {'coef': coef_table(m2, names), 'r2': float(m2.rsquared),
                  'r2adj': float(m2.rsquared_adj), 'F': float(m2.fvalue), 'Fp': float(m2.f_pvalue),
                  'df_model': int(m2.df_model), 'df_resid': int(m2.df_resid)}

    # 표준화 계수 — 변수의 단위를 걷어 낸 크기 비교
    z = d[['per', 'new', 'age', 'area', 'floor', 't']].apply(lambda s: (s - s.mean()) / s.std())
    ms = smf.ols(f, z).fit()
    out['beta'] = {k: float(ms.params[k]) for k in names[1:]}

    # 3) 가정 진단
    res, fit = m2.resid, m2.fittedvalues
    bp = het_breuschpagan(res, m2.model.exog)
    jb = jarque_bera(res)
    X = d[['new', 'age', 'area', 'floor', 't']].assign(const=1.0)
    vif = {c: float(variance_inflation_factor(X.values, i)) for i, c in enumerate(X.columns) if c != 'const'}
    infl = m2.get_influence()
    cook = infl.cooks_distance[0]
    # 같은 단지의 거래는 서로 닮았다 — 단지로 묶은 표준오차와 비교
    mc = smf.ols(f, d).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(d['complex'])[0]})
    mh = smf.ols(f, d).fit(cov_type='HC3')
    # 계약 순서로 늘어놓은 잔차의 더빈-왓슨 (시간 순서가 있는 자료에서만 뜻이 있다)
    order = d.sort_values(['계약년월', '계약일']).index
    out['diag'] = {
        'bp_lm': float(bp[0]), 'bp_p': float(bp[1]),
        'jb': float(jb[0]), 'jb_p': float(jb[1]), 'skew': float(jb[2]), 'kurt': float(jb[3]),
        'dw_time': float(durbin_watson(res.loc[order])),
        'vif': vif,
        'cook_n': int((cook > 4 / len(d)).sum()), 'cook_max': float(cook.max()),
        'se': {k: {'ols': float(m2.bse[k]), 'hc3': float(mh.bse[k]), 'cl': float(mc.bse[k]),
                   't_cl': float(mc.tvalues[k]), 'p_cl': float(mc.pvalues[k])} for k in names[1:]},
        'n_complex': int(d['complex'].nunique()),
    }
    # 잔차 그림용 표본 (600점) · Q-Q 점 (61점)
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(d), 600, replace=False)
    out['resid_pts'] = [[round(float(fit.iloc[i]), 1), round(float(res.iloc[i]), 1)] for i in idx]
    q = np.linspace(0.01, 0.99, 61)
    from scipy.stats import norm
    sr = (res - res.mean()) / res.std()
    out['qq'] = [[round(float(norm.ppf(p)), 3), round(float(np.quantile(sr, p)), 3)] for p in q]

    # 선형성: RESET 검정과 나이·시점 구간별 잔차 평균 (0 에서 벗어나 휘면 직선이 못 담은 모양)
    from statsmodels.stats.diagnostic import linear_reset
    rs = linear_reset(m2, power=2, use_f=True)
    out['diag']['reset_F'] = float(rs.fvalue); out['diag']['reset_p'] = float(rs.pvalue)
    out['bin_age'] = [[int(a), round(float(res[d['age'] == a].mean()), 1), int((d['age'] == a).sum())]
                      for a in range(0, 31) if (d['age'] == a).sum() >= 20]
    # 영향점: Cook 거리 큰 순 상위 300 과 무작위 300
    ck = pd.Series(cook)
    top = ck.sort_values(ascending=False).index[:300]
    out['cook_pts'] = [[int(i), round(float(ck[i]), 5)] for i in sorted(set(top) | set(rng.choice(len(d), 300, replace=False)))]
    out['cook_thr'] = 4 / len(d)

    # 로그 변환 뒤 다시 진단
    ml = smf.ols('np.log(per) ~ new + age + area + floor + t', d).fit()
    bpl = het_breuschpagan(ml.resid, ml.model.exog)
    jbl = jarque_bera(ml.resid)
    out['log'] = {'coef': {k: float(ml.params[k]) for k in names}, 'r2': float(ml.rsquared),
                  'bp_lm': float(bpl[0]), 'skew': float(jbl[2]), 'kurt': float(jbl[3])}
    srl = (ml.resid - ml.resid.mean()) / ml.resid.std()
    out['qq_log'] = [[round(float(norm.ppf(p)), 3), round(float(np.quantile(srl, p)), 3)] for p in q]
    out['resid_pts_log'] = [[round(float(ml.fittedvalues.iloc[i]), 3), round(float(ml.resid.iloc[i]), 3)] for i in idx]

    # 4) 로지스틱 — ㎡당 가격이 중앙값을 넘는가
    lg = smf.logit('high ~ new + age + area + floor + t', d).fit(disp=0)
    ci = lg.conf_int()
    out['logit'] = {
        'coef': [{'name': k, 'b': float(lg.params[k]), 'se': float(lg.bse[k]), 'z': float(lg.tvalues[k]),
                  'p': float(lg.pvalues[k]), 'or': float(np.exp(lg.params[k])),
                  'or_lo': float(np.exp(ci.loc[k, 0])), 'or_hi': float(np.exp(ci.loc[k, 1]))} for k in names],
        'pseudo_r2': float(lg.prsquared), 'llr': float(lg.llr), 'llr_p': float(lg.llr_pvalue),
        'll': float(lg.llf), 'll0': float(lg.llnull),
    }
    p = lg.predict(d)
    pred = (p > 0.5).astype(int)
    tab = pd.crosstab(d['high'], pred)
    out['logit']['table'] = [[int(tab.loc[a, b]) for b in (0, 1)] for a in (0, 1)]
    out['logit']['acc'] = float((pred == d['high']).mean())
    # 그림용: 나이에 따른 예측확률 (신도시·편입, 나머지는 평균)
    grid = np.arange(0, 31, 1)
    curves = {}
    for nw in (0, 1):
        g = pd.DataFrame({'new': nw, 'age': grid, 'area': d['area'].mean(),
                          'floor': d['floor'].mean(), 't': d['t'].mean()})
        curves[str(nw)] = [round(float(v), 4) for v in lg.predict(g)]
    out['logit']['curve_age'] = list(map(int, grid))
    out['logit']['curves'] = curves
    # 선형확률모형과 비교 — 0~1 밖 예측이 몇 건인가
    lpm = smf.ols('high ~ new + age + area + floor + t', d).fit()
    out['lpm_out'] = int(((lpm.fittedvalues < 0) | (lpm.fittedvalues > 1)).sum())

    # 그림용: 나이-가격 산점 표본, 나이 하나로 본 선형확률모형과 로지스틱
    pi = rng.choice(len(d), 400, replace=False)
    out['pts_age'] = [[int(d.loc[i, 'age']), round(float(d.loc[i, 'per']), 0)] for i in pi]
    pj = rng.choice(len(d), 300, replace=False)
    out['pts_high'] = [[int(d.loc[i, 'age']), int(d.loc[i, 'high'])] for i in pj]
    l1 = smf.ols('high ~ age', d).fit()
    g1 = smf.logit('high ~ age', d).fit(disp=0)
    out['one_lpm'] = [float(l1.params['Intercept']), float(l1.params['age'])]
    out['one_logit'] = [float(g1.params['Intercept']), float(g1.params['age'])]
    out['one_lpm_out'] = int(((l1.fittedvalues < 0) | (l1.fittedvalues > 1)).sum())
    out['mean_per'] = float(d['per'].mean())
    out['sse_mean'] = float(((d['per'] - d['per'].mean()) ** 2).sum())
    out['sse_simple'] = float((m1.resid ** 2).sum())

    if '--slide' in sys.argv:
        print('window.REG = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
        return
    o = out['ols']
    print(f"표본 {out['n']:,} (원자료 {n0:,}, 취소 {out['n_cancel']:,}) · 신도시 {out['n_new']:,}")
    print(f"단순회귀: ㎡당 = {out['simple']['b0']:.1f} + {out['simple']['b1']:.2f}·나이  R² {out['simple']['r2']:.3f}")
    print(f"다중회귀 R² {o['r2']:.3f} · 수정 {o['r2adj']:.3f} · F {o['F']:.1f} (p {o['Fp']:.2g})")
    for c in o['coef']:
        print(f"  {c['name']:9s} b {c['b']:9.3f}  se {c['se']:7.3f}  t {c['t']:7.2f}  p {c['p']:.3g}  [{c['lo']:.2f}, {c['hi']:.2f}]")
    print('표준화계수', {k: round(v, 3) for k, v in out['beta'].items()})
    g = out['diag']
    print(f"BP {g['bp_lm']:.1f} p {g['bp_p']:.2g} · JB {g['jb']:.0f} 왜도 {g['skew']:.2f} 첨도 {g['kurt']:.2f} · DW(시간순) {g['dw_time']:.3f}")
    print(f"RESET F {g['reset_F']:.1f} p {g['reset_p']:.2g}")
    print('VIF', {k: round(v, 2) for k, v in g['vif'].items()}, f"· Cook>4/n {g['cook_n']}건 최대 {g['cook_max']:.3f}")
    print(f"단지 {g['n_complex']}개")
    for k, v in g['se'].items():
        print(f"  SE {k:6s} OLS {v['ols']:.3f}  HC3 {v['hc3']:.3f}  단지군집 {v['cl']:.3f}  (t {v['t_cl']:.2f}, p {v['p_cl']:.3g})")
    L = out['log']
    print(f"로그: R² {L['r2']:.3f} BP {L['bp_lm']:.1f} 왜도 {L['skew']:.2f} 첨도 {L['kurt']:.2f}", {k: round(v, 4) for k, v in L['coef'].items()})
    lg_ = out['logit']
    print(f"로지스틱: 의사 R² {lg_['pseudo_r2']:.3f} · LR {lg_['llr']:.0f} (p {lg_['llr_p']:.2g}) · 적중 {lg_['acc']:.3f} · 표 {lg_['table']}")
    for c in lg_['coef']:
        print(f"  {c['name']:9s} b {c['b']:8.4f} z {c['z']:7.2f} p {c['p']:.3g}  OR {c['or']:.3f} [{c['or_lo']:.3f}, {c['or_hi']:.3f}]")
    print('선형확률모형 0~1 밖 예측', out['lpm_out'], '· 나이 하나', out['one_lpm'], out['one_logit'], out['one_lpm_out'], '· 평균', round(out['mean_per'],1))


if __name__ == '__main__':
    main()
