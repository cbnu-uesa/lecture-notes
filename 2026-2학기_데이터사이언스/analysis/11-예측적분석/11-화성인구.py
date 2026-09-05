#!/usr/bin/env python3
"""11·12강(예측적 분석) — 화성시 월별 인구로 추세 외삽과 모형 비교를 한다.

입력: ~/data/compas/hwaseong-population/1.화성시_인구데이터.xlsx
      COMPAS 「AI기법에 의한 인구예측모델 정확도 비교 분석」(화성시, SBJ_2307_001)
      이 과제의 데이터는 전부 공개다.
로직: 11-화성인구-로직.md 를 먼저 읽는다.
외부 라이브러리를 쓰지 않는다 — xlsx 를 zip+XML 로 직접 읽고 회귀도 직접 푼다.
"""
import datetime, math, pathlib, statistics as st, sys, xml.etree.ElementTree as ET, zipfile

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'      # 원자료는 주차 폴더 밖, analysis/data/ 에 함께 둔다
FILE = '1.화성시_인구데이터.xlsx'
# 없으면 내려받아 둔 곳(~/data/compas)을 본다.
SRC = (DATA / FILE if (DATA / FILE).exists()
       else pathlib.Path.home() / 'data/compas/hwaseong-population' / FILE)
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
HOLDOUT = 12          # 마지막 12개월은 검증용으로 떼어 둔다

def read_series():
    z = zipfile.ZipFile(SRC)
    shared = [''.join(t.text or '' for t in si.iter(NS + 't'))
              for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si')]
    def val(c):
        v = c.find(NS + 'v')
        if v is None: return ''
        return shared[int(v.text)] if c.get('t') == 's' else v.text
    out = []
    for r in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//' + NS + 'row'):
        cells = {''.join(ch for ch in c.get('r') if ch.isalpha()): val(c)
                 for c in r.findall(NS + 'c')}
        a = cells.get('A', '')
        if a.isdigit() and cells.get('C', '').isdigit():
            # 엑셀 날짜 일련번호 → 날짜
            out.append((datetime.date(1899, 12, 30) + datetime.timedelta(days=int(a)),
                        int(cells['C'])))
    return out

def fit(xs, ys, deg=1):
    """다항 최소제곱. 정규방정식을 가우스 소거로 푼다."""
    k = deg + 1
    A = [[sum(x ** (a + b) for x in xs) for b in range(k)] +
         [sum(x ** a * y for x, y in zip(xs, ys))] for a in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        for r in range(k):
            if r == c: continue
            f = A[r][c] / A[c][c]
            for j in range(c, k + 1): A[r][j] -= f * A[c][j]
    return [A[i][k] / A[i][i] for i in range(k)]

def predict(b, x):
    return sum(c * x ** i for i, c in enumerate(b))

def mape(pred, actual):
    return st.mean(abs(p - a) / a * 100 for p, a in zip(pred, actual))

def main():
    if not SRC.exists():
        sys.exit(f'원본이 없습니다: {SRC}')
    s = read_series()
    print(f'관측 {len(s)}개월 · {s[0][0]} ~ {s[-1][0]}')
    print(f'인구 {s[0][1]:,} → {s[-1][1]:,}명 ({(s[-1][1]/s[0][1]-1)*100:.1f}% 증가)\n')

    tr, te = s[:-HOLDOUT], s[-HOLDOUT:]
    xs = list(range(len(tr))); ys = [v for _, v in tr]
    xt = list(range(len(tr), len(s))); yt = [v for _, v in te]

    print(f'학습 {len(tr)}개월 · 검증 {len(te)}개월')
    print(f"{'모형':<12}{'학습 MAPE':>11}{'검증 MAPE':>11}   마지막 달 예측")
    for name, deg in [('선형', 1), ('2차', 2), ('3차', 3)]:
        b = fit(xs, ys, deg)
        in_ = mape([predict(b, x) for x in xs], ys)
        out = mape([predict(b, x) for x in xt], yt)
        print(f'{name:<12}{in_:>10.2f}%{out:>10.2f}%   {predict(b, xt[-1]):>12,.0f}')
    # 로그 추세 — 증가율이 점점 낮아지는 꼴
    lb = fit(xs, [math.log(v) for v in ys], 1)
    lin_ = mape([math.exp(predict(lb, x)) for x in xs], ys)
    lout = mape([math.exp(predict(lb, x)) for x in xt], yt)
    print(f'{"지수":<12}{lin_:>10.2f}%{lout:>10.2f}%   {math.exp(predict(lb, xt[-1])):>12,.0f}')
    print(f'\n실제 {te[-1][0]} = {yt[-1]:,}명')
    b1 = fit(xs, ys, 1)
    print(f'선형 추세의 월 증가폭 {b1[1]:,.0f}명')

    # 슬라이드가 쓰는 표를 CSV 로 남긴다 — 월별 시계열이 11·12강 그림의 원자료다
    import csv
    with open(HERE / '11-화성인구-월별.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['연월', '총인구'])
        w.writerows([[d.isoformat()[:7], v] for d, v in s])
    with open(HERE / '11-화성인구-모형별.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['모형', '학습MAPE(%)', '검증MAPE(%)', f'{te[-1][0].isoformat()[:7]} 예측', '실제'])
        for name, deg in [('선형', 1), ('2차', 2), ('3차', 3)]:
            b = fit(xs, ys, deg)
            w.writerow([name, round(mape([predict(b, x) for x in xs], ys), 2),
                        round(mape([predict(b, x) for x in xt], yt), 2),
                        round(predict(b, xt[-1])), yt[-1]])
        w.writerow(['지수', round(lin_, 2), round(lout, 2),
                    round(math.exp(predict(lb, xt[-1]))), yt[-1]])
    print('\n요약표 저장\n  → 11-화성인구-월별.csv\n  → 11-화성인구-모형별.csv')

if __name__ == '__main__':
    main()
