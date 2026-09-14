#!/usr/bin/env python3
"""9강(상관과 인과)의 교차표·카이제곱과 부분상관 사례를 만든다.

  4 교차표와 카이제곱 검정  범주끼리 관련이 있나
  6 부분상관                다른 변수를 묶어 둔 채 본 상관

입력: analysis/data/21.아산시_병원정보.csv        — 4 (의료기관 358곳)
      analysis/09-진단적분석1/09-아산의료접근성-지역별.csv — 6 (12개 지역)
      COMPAS 「의료 취약지역 도출」(아산, SBJ_2405_001) 공개 데이터

외부 라이브러리를 쓰지 않는다. 카이제곱의 p값은 감마함수 없이
**윌슨-힐퍼티 근사**로 정규분포에 옮겨 구한다.

    python3 09-아산교차표와부분상관.py

로직: 09-아산교차표와부분상관-로직.md 를 먼저 읽는다.
"""
import csv, math, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
HOSP = DATA / '21.아산시_병원정보.csv'
REGION = HERE / '09-아산의료접근성-지역별.csv'

# 도시 지역과 읍면 지역. 아산은 동(온양 시가지)과 읍·면이 성격이 다르다
URBAN_SUFFIX = '동'

def phi_cdf(z):
    """표준정규 누적분포. 오차함수는 표준 math 에 있다."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))

def chi2_p(x2, df):
    """자유도 df 카이제곱의 우측 꼬리. 윌슨-힐퍼티 근사 — 난수도 표도 쓰지 않는다."""
    if x2 <= 0: return 1.0
    t = (x2 / df) ** (1 / 3)
    z = (t - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    return 1 - phi_cdf(z)

def pearson(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy)

def partial(xs, ys, zs):
    """z 를 묶어 둔 채 본 x·y 의 상관. 세 단순상관에서 유도한다."""
    rxy, rxz, ryz = pearson(xs, ys), pearson(xs, zs), pearson(ys, zs)
    return (rxy - rxz * ryz) / math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))

def save(name, header, rows):
    p = HERE / name
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {p.name}')

def main():
    if not HOSP.exists(): sys.exit(f'원본이 없습니다: {HOSP}')

    # ── 4. 교차표와 카이제곱 ──────────────────────────────────
    rows = list(csv.DictReader(open(HOSP, encoding='utf-8-sig')))
    KIND = {'의원': '의원', '치과의원': '치과·한의', '한의원': '치과·한의'}
    def kind(g):
        if g in KIND: return KIND[g]
        if g.startswith('보건'): return '보건기관'
        return '병원급'
    ROWS = ['의원', '치과·한의', '병원급', '보건기관']
    COLS = ['동(도시)', '읍·면']
    tab = {r: {c: 0 for c in COLS} for r in ROWS}
    for r in rows:
        area = COLS[0] if r['emd_nm'].endswith(URBAN_SUFFIX) else COLS[1]
        tab[kind(r['mdcl_gbn'])][area] += 1
    n = sum(tab[r][c] for r in ROWS for c in COLS)
    rt = {r: sum(tab[r].values()) for r in ROWS}
    ct = {c: sum(tab[r][c] for r in ROWS) for c in COLS}
    print(f'의료기관 {n}곳 — 유형 × 소재지 교차표\n')
    print(f'{"":<10}' + ''.join(f'{c:>10}' for c in COLS) + f'{"계":>8}')
    for r in ROWS:
        print(f'{r:<10}' + ''.join(f'{tab[r][c]:>10,}' for c in COLS) + f'{rt[r]:>8,}')
    print(f'{"계":<10}' + ''.join(f'{ct[c]:>10,}' for c in COLS) + f'{n:>8,}')

    x2 = 0.0; cells = []
    for r in ROWS:
        for c in COLS:
            e = rt[r] * ct[c] / n
            x2 += (tab[r][c] - e) ** 2 / e
            cells.append([r, c, tab[r][c], round(e, 1), round((tab[r][c] - e) / math.sqrt(e), 2)])
    df = (len(ROWS) - 1) * (len(COLS) - 1)
    p = chi2_p(x2, df)
    v = math.sqrt(x2 / (n * min(len(ROWS) - 1, len(COLS) - 1)))
    print(f'\n카이제곱 = {x2:.2f} · 자유도 {df} · p = {p:.5f} · 크레이머 V = {v:.3f}')
    print('  기대도수와 가장 벌어진 칸')
    for r, c, o, e, sr in sorted(cells, key=lambda t: -abs(t[4]))[:3]:
        print(f'    {r} × {c}   관측 {o} · 기대 {e} · 표준화잔차 {sr:+.2f}')
    save('09-아산교차표.csv', ['유형', '소재지', '관측도수', '기대도수', '표준화잔차'], cells)

    # ── 6. 부분상관 ──────────────────────────────────────────
    reg = []
    for r in csv.DictReader(open(REGION, encoding='utf-8-sig')):
        try:
            reg.append((r['지역'], int(r['인구']), int(r['병원']), int(r['의사'])))
        except (ValueError, KeyError, TypeError):
            continue
    pop = [x[1] for x in reg]; hos = [x[2] for x in reg]; doc = [x[3] for x in reg]
    print(f'\n부분상관 — 지역 {len(reg)}개')
    print(f'  단순상관  병원↔의사 {pearson(hos, doc):.3f}')
    print(f'            병원↔인구 {pearson(hos, pop):.3f} · 의사↔인구 {pearson(doc, pop):.3f}')
    pr = partial(hos, doc, pop)
    print(f'  인구를 묶어 두면  병원↔의사 {pr:.3f}')
    print('  → 인구가 둘을 함께 끌어올린 몫을 걷어 낸 값이다')
    save('09-아산부분상관.csv', ['관계', '계수'], [
        ['병원↔의사 단순상관', round(pearson(hos, doc), 3)],
        ['병원↔인구 단순상관', round(pearson(hos, pop), 3)],
        ['의사↔인구 단순상관', round(pearson(doc, pop), 3)],
        ['병원↔의사 부분상관(인구 통제)', round(pr, 3)],
    ])

if __name__ == '__main__':
    main()
