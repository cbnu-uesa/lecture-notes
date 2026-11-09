#!/usr/bin/env python3
"""10강(머신러닝) — 9강과 같은 세종 자료로 의사결정나무·랜덤포레스트·SHAP 을 보인다.

입력: analysis/data/3.세종시_아파트(매매)_실거래가.csv (9강과 같은 걸러내기, 15,486건)
로직: 10-세종랜덤포레스트-로직.md
실행: ~/.venvs/osmnx/bin/python 10-세종랜덤포레스트.py [--slide]
      scikit-learn·shap·pandas 가 필요하다. Drive 안에서 pip install 하지 않는다.
"""
import json, pathlib, sys
import numpy as np, pandas as pd
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, accuracy_score, roc_auc_score
from sklearn.inspection import permutation_importance

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / 'data' / '3.세종시_아파트(매매)_실거래가.csv'
SEED = 10
FEAT = ['new', 'age', 'area', 'floor', 't']
KO = {'new': '신도시', 'age': '건물 나이', 'area': '전용면적', 'floor': '층', 't': '계약 시점'}


def load():
    d = pd.read_csv(SRC, encoding='utf-8-sig')
    d = d[d['해제사유발생일'].isna()]
    d = d[(d['전용면적(㎡)'] > 60) & (d['건축년도'] >= 1960)].copy()
    d['per'] = d['거래금액(만원)'].str.replace(',', '').astype(int) / d['전용면적(㎡)']
    d['new'] = d['시군구'].str.split().str[-1].str.endswith('동').astype(int)
    y, m = d['계약년월'] // 100, d['계약년월'] % 100
    d['age'] = y - d['건축년도']
    d['area'] = d['전용면적(㎡)']
    d['floor'] = d['층']
    d['t'] = (y - 2017) + (m - 1) / 12          # 2017년 1월 = 0, 연 단위
    d['high'] = (d['per'] > d['per'].median()).astype(int)
    d['complex'] = d['시군구'] + ' ' + d['단지명']
    return d.reset_index(drop=True)


def reg_scores(y, p):
    return {'r2': float(r2_score(y, p)), 'rmse': float(mean_squared_error(y, p) ** .5),
            'mae': float(mean_absolute_error(y, p))}


def tree_struct(tr, feats):
    """sklearn 나무를 그림용 사전으로 바꾼다."""
    t = tr.tree_
    def node(i):
        if t.children_left[i] == -1:
            return {'leaf': True, 'v': round(float(t.value[i][0][0]), 1), 'n': int(t.n_node_samples[i])}
        return {'f': feats[t.feature[i]], 'th': round(float(t.threshold[i]), 2), 'n': int(t.n_node_samples[i]),
                'v': round(float(t.value[i][0][0]), 1),
                'L': node(t.children_left[i]), 'R': node(t.children_right[i])}
    return node(0)


def main():
    d = load()
    X, y, yc = d[FEAT].values, d['per'].values, d['high'].values
    out = {'n': len(d), 'feat': FEAT, 'ko': KO}

    # ── 1) 무작위 80:20 분할 ──
    Xtr, Xte, ytr, yte, ctr, cte = train_test_split(X, y, yc, test_size=.2, random_state=SEED)
    lin = LinearRegression().fit(Xtr, ytr)
    dt = DecisionTreeRegressor(max_depth=4, random_state=SEED).fit(Xtr, ytr)
    dtf = DecisionTreeRegressor(random_state=SEED).fit(Xtr, ytr)          # 끝까지 자란 나무
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.6,
                               oob_score=True, n_jobs=-1, random_state=SEED).fit(Xtr, ytr)
    out['reg'] = {
        '선형회귀': {'train': reg_scores(ytr, lin.predict(Xtr)), 'test': reg_scores(yte, lin.predict(Xte))},
        '나무(깊이 4)': {'train': reg_scores(ytr, dt.predict(Xtr)), 'test': reg_scores(yte, dt.predict(Xte))},
        '나무(끝까지)': {'train': reg_scores(ytr, dtf.predict(Xtr)), 'test': reg_scores(yte, dtf.predict(Xte))},
        '랜덤포레스트': {'train': reg_scores(ytr, rf.predict(Xtr)), 'test': reg_scores(yte, rf.predict(Xte))},
    }
    out['oob_r2'] = float(rf.oob_score_)
    # 예측구간: 시험 잔차의 5%·95% 분위로 만든 90% 범위와, 단지 분할에서의 실제 적중률
    rr = yte - rf.predict(Xte)
    q5, q95 = np.quantile(rr, [.05, .95])
    out['pi'] = {'q5': round(float(q5), 1), 'q95': round(float(q95), 1),
                 'mape_lin': round(float(np.mean(np.abs((yte - lin.predict(Xte)) / yte)) * 100), 2),
                 'mape_rf': round(float(np.mean(np.abs(rr / yte)) * 100), 2)}
    # 나무 수에 따른 시험 R² — 숲이 커지면 어떻게 되나
    preds = np.stack([e.predict(Xte) for e in rf.estimators_])
    out['ntrees'] = [[k, round(float(r2_score(yte, preds[:k].mean(0))), 4)] for k in (1, 2, 3, 5, 10, 20, 50, 100, 200, 300)]

    # 분류: 로지스틱 대 랜덤포레스트
    lgc = LogisticRegression(max_iter=2000).fit(Xtr, ctr)
    rfc = RandomForestClassifier(n_estimators=300, min_samples_leaf=5, max_features=0.6,
                                 n_jobs=-1, random_state=SEED).fit(Xtr, ctr)
    def cls(m):
        p = m.predict_proba(Xte)[:, 1]
        return {'acc': float(accuracy_score(cte, p > .5)), 'auc': float(roc_auc_score(cte, p))}
    out['cls'] = {'로지스틱': cls(lgc), '랜덤포레스트': cls(rfc)}

    # ── 2) 단지 단위 분할 — 시험 단지는 훈련에 한 건도 없다 ──
    gss = GroupShuffleSplit(n_splits=1, test_size=.2, random_state=SEED)
    gi, go = next(gss.split(X, y, d['complex']))
    lin_g = LinearRegression().fit(X[gi], y[gi])
    rf_g = RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.6,
                                 n_jobs=-1, random_state=SEED).fit(X[gi], y[gi])
    rg = y[go] - rf_g.predict(X[go])
    pi_cover = float(np.mean((rg >= out['pi']['q5']) & (rg <= out['pi']['q95'])))
    out['group'] = {'pi_cover': round(pi_cover, 3),'n_test_complex': int(d.loc[go, 'complex'].nunique()), 'n_test': int(len(go)),
                    '선형회귀': reg_scores(y[go], lin_g.predict(X[go])),
                    '랜덤포레스트': reg_scores(y[go], rf_g.predict(X[go]))}

    # ── 3) 그림용 나무 — 나이·계약시점 두 변수, 깊이 2 ──
    two = ['age', 't']
    X2 = d[two].values
    small = DecisionTreeRegressor(max_depth=2, random_state=SEED).fit(X2, y)
    out['tree2'] = tree_struct(small, two)
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(d), 500, replace=False)
    out['pts2'] = [[int(d.loc[i, 'age']), round(float(d.loc[i, 't']), 3), round(float(d.loc[i, 'per']), 0)] for i in pick]
    # 첫 질문을 고르는 법 — 나이 기준값마다 두 묶음의 제곱오차 합이 얼마나 줄어드나
    ya, aa = d['per'].values, d['age'].values
    sse0 = float(((ya - ya.mean()) ** 2).sum())
    cut = []
    for th in np.arange(0.5, 25.5, 1.0):
        L, R = ya[aa <= th], ya[aa > th]
        if len(L) and len(R):
            s = ((L - L.mean()) ** 2).sum() + ((R - R.mean()) ** 2).sum()
            cut.append([float(th), round(1 - float(s) / sse0, 4), int(len(L)), round(float(L.mean()), 1), round(float(R.mean()), 1)])
    out['cut_age'] = cut
    # 깊이에 따른 훈련·시험 R² — 나무가 깊어지면 외운다
    out['depth'] = []
    for dep in list(range(1, 21)) + [None]:
        m = DecisionTreeRegressor(max_depth=dep, random_state=SEED).fit(Xtr, ytr)
        out['depth'].append([dep or 0, round(float(r2_score(ytr, m.predict(Xtr))), 4), round(float(r2_score(yte, m.predict(Xte))), 4)])
    # 부트스트랩 나무 세 그루 — 표본과 변수를 무작위로 바꾸면 나무가 달라진다
    boots = []
    probe = {'age': 5, 't': 3.5, 'new': 1, 'area': 85, 'floor': 10}
    # 그림에서 차이가 보이도록 뿌리 질문이 서로 다른 세 그루를 씨앗 순서대로 고른다
    roots, k = set(), 0
    while len(boots) < 3:
        r = np.random.default_rng(100 + k)
        bi = r.choice(len(d), len(d), replace=True)
        cols = [str(c) for c in r.choice(FEAT, 2, replace=False)]
        tr = DecisionTreeRegressor(max_depth=2, random_state=k).fit(d.loc[bi, cols].values, y[bi])
        root = cols[tr.tree_.feature[0]]
        k += 1
        if root in roots:
            continue
        roots.add(root)
        pv = float(tr.predict(np.array([[probe[c] for c in cols]]))[0])
        boots.append({'seed': 100 + k - 1, 'cols': cols, 'tree': tree_struct(tr, cols), 'probe': round(pv, 1),
                      'uniq': int(len(np.unique(bi)))})
    out['boots'] = boots
    out['probe'] = probe
    out['probe_rf'] = round(float(rf.predict(np.array([[probe[c] for c in FEAT]]))[0]), 1)

    # ── 4) 변수 중요도와 SHAP ──
    out['imp'] = {f: round(float(v), 4) for f, v in zip(FEAT, rf.feature_importances_)}
    pi = permutation_importance(rf, Xte, yte, n_repeats=5, random_state=SEED, n_jobs=-1)
    out['perm'] = {f: round(float(v), 4) for f, v in zip(FEAT, pi.importances_mean)}
    import shap
    sidx = np.random.default_rng(SEED).choice(len(Xte), 400, replace=False)
    ex = shap.TreeExplainer(rf)
    sv = ex.shap_values(Xte[sidx])
    base = float(np.ravel(ex.expected_value)[0])
    out['shap'] = {'base': round(base, 1),
                   'mean_abs': {f: round(float(np.abs(sv[:, j]).mean()), 2) for j, f in enumerate(FEAT)},
                   # 점마다 [특성값, SHAP]
                   'pts': {f: [[round(float(Xte[sidx][i, j]), 3), round(float(sv[i, j]), 1)] for i in range(len(sidx))]
                           for j, f in enumerate(FEAT)}}
    # 한 거래의 분해 — 폭포 그림
    i0 = int(np.argmax(Xte[sidx][:, 1] < 3) )  # 첫 번째 새 아파트(나이 3년 미만)
    out['one'] = {'x': {f: round(float(Xte[sidx][i0, j]), 2) for j, f in enumerate(FEAT)},
                  'sv': {f: round(float(sv[i0, j]), 1) for j, f in enumerate(FEAT)},
                  'pred': round(float(rf.predict(Xte[sidx][i0:i0 + 1])[0]), 1), 'y': round(float(yte[sidx][i0]), 1)}
    out['lin_coef'] = {f: round(float(c), 3) for f, c in zip(FEAT, lin.coef_)}

    if '--slide' in sys.argv:
        print('window.ML = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
        return
    print(f"표본 {out['n']:,}")
    for k, v in out['reg'].items():
        print(f"  {k:8s} 훈련 R² {v['train']['r2']:.3f}  시험 R² {v['test']['r2']:.3f}  RMSE {v['test']['rmse']:.1f}  MAE {v['test']['mae']:.1f}")
    print(f"  OOB R² {out['oob_r2']:.3f} · 나무 수별 시험 R² {out['ntrees']}")
    print('  분류', out['cls']); print('  구간', out['pi'])
    print('  단지 분할', out['group'])
    print('  깊이2 나무', json.dumps(out['tree2'], ensure_ascii=False))
    for b in out['boots']:
        print('  부트스트랩', b['cols'], b['probe'], b['uniq'], json.dumps(b['tree'], ensure_ascii=False)[:200])
    print('  probe RF', out['probe_rf'])
    print('  불순도 중요도', out['imp'], '\n  순열 중요도', out['perm'])
    print('  SHAP base', out['shap']['base'], out['shap']['mean_abs'])
    print('  한 거래', out['one'])
    print('  선형계수', out['lin_coef'])


if __name__ == '__main__':
    main()
