#!/usr/bin/env python3
"""9강(진단적 분석 Ⅰ) 슬라이드의 수치를 만드는 스크립트.

입력: ~/data/compas/asan-medical/  (COMPAS 「보건의료 불균형 — 의료 취약지역 도출」
      아산시, SBJ_2405_001 공개 데이터)
로직: 09-아산의료접근성-로직.md 를 먼저 읽는다.

    python3 09-아산의료접근성.py
"""
import csv, collections, math, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
# 원자료는 data/ 에 함께 둔다. 없으면 내려받아 둔 곳(~/data/compas)을 본다.
BASE = (HERE / 'data' if (HERE / 'data' / '21.아산시_병원정보.csv').exists()
        else pathlib.Path.home() / 'data/compas/asan-medical')
# 온양 시가지의 법정동. 인구 파일은 행정동(온양1~6동), 병원 파일은 법정동을 쓴다.
# 그대로 이으면 온양 지역 병원이 0개가 된다 — 9강에서 다루는 함정이다.
DONG = {'온천동', '모종동', '용화동', '풍기동', '권곡동', '읍내동',
        '장존동', '방축동', '득산동', '배미동', '좌부동', '실옥동'}

def unit(name: str) -> str:
    n = (name or '').strip()
    return '온양 시가지' if (n in DONG or n.startswith('온양')) else n

def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    return (sum((x - ma) * (y - mb) for x, y in zip(a, b))
            / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)))

def main():
    if not BASE.exists():
        sys.exit(f'원본이 없습니다: {BASE}')

    pop = collections.Counter()
    with open(BASE / '2.아산시_주민등록인구현황.csv', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    last = max(r['year'] for r in rows)
    for r in rows:
        if r['year'] == last:
            pop[unit(r['adm_nm'].split()[-1])] += int(r['m_pop']) + int(r['fm_pop'])

    hos, doc, naive, unmatched = collections.Counter(), collections.Counter(), collections.Counter(), 0
    with open(BASE / '21.아산시_병원정보.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            raw = (r['emd_nm'] or '').strip()
            if not raw:
                unmatched += 1
                continue
            naive[raw] += 1                      # 이름을 그대로 쓴 경우 (잘못된 방식)
            u = unit(raw)
            hos[u] += 1
            try:
                doc[u] += int(r['doc_cnt'] or 0)
            except ValueError:
                pass

    order = sorted(pop, key=lambda k: -pop[k])
    per = {n: hos.get(n, 0) / pop[n] * 100000 for n in order}

    print(f'인구 시점 {last} · 총인구 {sum(pop.values()):,} · 지역 {len(pop)}개')
    print(f'읍면동 이름이 빈 병원 {unmatched}건 (집계에서 제외)\n')
    print(f"{'지역':<10}{'인구':>9}{'병원':>5}{'의사':>6}{'10만명당':>10}")
    for n in order:
        print(f'{n:<10}{pop[n]:>9,}{hos.get(n,0):>5}{doc.get(n,0):>6}{per[n]:>10.1f}')

    print(f'\n인구 vs 병원 수        r = {corr([pop[n] for n in order], [hos.get(n,0) for n in order]):.3f}')
    print(f'인구 vs 10만명당 병원   r = {corr([pop[n] for n in order], [per[n] for n in order]):.3f}')
    srt = sorted(per.items(), key=lambda kv: kv[1])
    print(f'10만명당 최저 {srt[0][0]} {srt[0][1]:.1f} · 최고 {srt[-1][0]} {srt[-1][1]:.1f} '
          f'({srt[-1][1]/srt[0][1]:.1f}배)')

    path = HERE / '09-아산의료접근성-지역별.csv'
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['지역', '인구', '병원', '의사', '10만명당병원'])
        w.writerows([[n, pop[n], hos.get(n, 0), doc.get(n, 0), round(per[n], 1)] for n in order])
        w.writerow([])
        w.writerow(['인구 vs 병원 수 r', round(corr([pop[n] for n in order], [hos.get(n,0) for n in order]), 3)])
        w.writerow(['인구 vs 10만명당 병원 r', round(corr([pop[n] for n in order], [per[n] for n in order]), 3)])
    print(f'\n요약표 저장\n  → {path.name}')

    print('\n[참고] 이름을 그대로 이었다면 — 온양1~6동 인구 '
          f'{sum(v for k, v in pop.items() if k == "온양 시가지"):,}명에 병원 '
          f'{sum(v for k, v in naive.items() if k.startswith("온양"))}개로 잡힌다.')

if __name__ == '__main__':
    main()
