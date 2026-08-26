#!/usr/bin/env python3
"""7강(기술적 분석) 슬라이드에 쓰는 수치를 만드는 스크립트.

입력: ~/data/compas/sejong-housing/3.세종시_아파트(매매)_실거래가.csv
      COMPAS 「주택 시장 특성분석」(세종, SBJ_2102_001) 공개 데이터
로직: 같은 폴더의 07-세종주택시장-로직.md 에 적었다. 그쪽을 먼저 읽는다.

    python3 07-세종주택시장.py
"""
import csv, collections, statistics as st, pathlib, sys

SRC = pathlib.Path.home() / 'data/compas/sejong-housing/3.세종시_아파트(매매)_실거래가.csv'
AREA_MIN = 60      # 전용면적 하한(㎡). 소형은 임대 목적이 섞여 성격이 다르다
MIN_N    = 100     # 동별 비교에 넣을 최소 거래 건수

def load():
    rows = []
    with open(SRC, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get('해제사유발생일'):            # 취소 거래는 뺀다
                continue
            try:
                area = float(r['전용면적(㎡)'])
                amt  = int(r['거래금액(만원)'].replace(',', ''))
            except (ValueError, KeyError):
                continue
            if area <= AREA_MIN:
                continue
            rows.append({'year': r['계약년월'][:4],
                         'dong': r['시군구'].split()[-1],
                         'area': area, 'amt': amt, 'per': amt / area})
    return rows

def main():
    if not SRC.exists():
        sys.exit(f'원본이 없습니다: {SRC}\nCOMPAS 에서 SBJ_2102_001 을 내려받으십시오.')
    rows = load()
    amt = [r['amt'] for r in rows]
    per = [r['per'] for r in rows]
    q = st.quantiles(amt, n=4)

    print(f'거래 {len(rows):,}건 (전용 {AREA_MIN}㎡ 초과, 취소 제외)')
    print(f'거래금액  평균 {st.mean(amt):,.0f} · 중앙값 {st.median(amt):,.0f} · 표준편차 {st.pstdev(amt):,.0f} 만원')
    print(f'          Q1 {q[0]:,.0f} · Q3 {q[2]:,.0f} · 최소 {min(amt):,} · 최대 {max(amt):,}')
    print(f'㎡당 가격  평균 {st.mean(per):,.0f} · 중앙값 {st.median(per):,.0f} 만원')

    print('\n연도별')
    by = collections.defaultdict(list)
    for r in rows:
        by[r['year']].append(r)
    for y in sorted(by):
        v = by[y]
        print(f'  {y}  {len(v):>5,}건  금액중앙값 {st.median([x["amt"] for x in v]):>7,.0f}  '
              f'㎡당중앙값 {st.median([x["per"] for x in v]):>5.0f}')

    print(f'\n동별 ㎡당 중앙값 (거래 {MIN_N}건 이상)')
    bd = collections.defaultdict(list)
    for r in rows:
        bd[r['dong']].append(r['per'])
    ok = sorted(((d, v) for d, v in bd.items() if len(v) >= MIN_N),
                key=lambda kv: st.median(kv[1]), reverse=True)
    for d, v in ok:
        print(f'  {d:<6} {st.median(v):>5.0f}만원  ({len(v):,}건)')
    print(f'  최고/최저 {st.median(ok[0][1]) / st.median(ok[-1][1]):.2f}배')

if __name__ == '__main__':
    main()
