#!/usr/bin/env python3
"""7강 서울 사례의 원자료를 받아 analysis/data/ 에 작은 파일 셋으로 줄인다.

원자료 (2026-10-30 내려받음, 크기가 커서 Drive 에 두지 않는다)
  HangJeongDong_ver20161231.geojson   vuski/admdongkor · CC BY 4.0 · 원자료 SGIS(공공누리 1유형)
  LOCAL_PEOPLE_DONG_202607.zip        서울 열린데이터광장 OA-14991 「서울 생활인구(내국인)」
  공공자전거 대여소 정보(26.6월 기준).xlsx  서울 열린데이터광장 OA-13252

경계를 2016년 판으로 쓰는 이유: 생활인구는 자료 일관성을 위해 2016년 행정동 코드를 쓴다
(열린데이터광장 문답). 2026년 판은 424동 중 415동만 맞고, 2016년 판은 424동이 모두 맞는다.

만드는 것
  data/서울_행정동경계_2016.geojson      서울 424동만. 좌표는 소수 다섯째 자리(약 1m)
  data/서울_생활인구_202607_평일.csv     동별 평일 14시 · 03시 평균 (2026년 7월 평일 23일)
  data/서울_따릉이대여소_2606.csv        대여소 번호 · 이름 · 자치구 · 주소 · 위경도 · 거치대수

    python3 07-서울자료준비.py <원자료 폴더>
"""
import csv, datetime, io, json, pathlib, re, sys, zipfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'

def xlsx_rows(path):
    """표준 라이브러리만으로 첫 시트를 읽는다."""
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    t = '{%s}t' % ns['m']
    z = zipfile.ZipFile(path)
    ss = [''.join(x.text or '' for x in si.iter(t))
          for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns)]
    out = []
    for r in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter('{%s}row' % ns['m']):
        cells = {}
        for c in r.findall('m:c', ns):
            col = 0
            for ch in re.match(r'[A-Z]+', c.get('r')).group():
                col = col * 26 + ord(ch) - 64
            v = c.find('m:v', ns)
            if c.get('t') == 'inlineStr': val = ''.join(x.text or '' for x in c.iter(t))
            elif v is None:               val = ''
            elif c.get('t') == 's':       val = ss[int(v.text)]
            else:                         val = v.text
            cells[col - 1] = val
        if cells:
            out.append([cells.get(i, '') for i in range(max(cells) + 1)])
    return out

def main():
    raw = pathlib.Path(sys.argv[1])

    # ── 경계 ──
    g = json.load(open(raw / 'HangJeongDong_ver20161231.geojson', encoding='utf-8'))
    feats = [f for f in g['features'] if f['properties']['sido_nm'] == '서울특별시']
    def rnd(o):
        return [rnd(x) for x in o] if isinstance(o[0], list) else [round(o[0], 5), round(o[1], 5)]
    out = []
    for f in feats:
        p = f['properties']
        out.append({'type': 'Feature',
                    'properties': {'adm_cd': p['adm_cd'][:8], 'gu': p['gu_nm'].split()[-1],
                                   'dong': p['adm_nm'].split()[-1]},
                    'geometry': {'type': f['geometry']['type'], 'coordinates': rnd(f['geometry']['coordinates'])}})
    json.dump({'type': 'FeatureCollection', 'features': out},
              open(DATA / '서울_행정동경계_2016.geojson', 'w', encoding='utf-8'), ensure_ascii=False)
    names = {f['properties']['adm_cd']: f['properties'] for f in out}
    print(f'경계  서울 {len(out)}동')

    # ── 생활인구: 평일만, 14시와 03시 ──
    z = zipfile.ZipFile(raw / 'LOCAL_PEOPLE_DONG_202607.zip')
    acc = {}
    days = set()
    with io.TextIOWrapper(z.open('LOCAL_PEOPLE_DONG_202607.csv'), encoding='utf-8-sig') as f:
        r = csv.reader(f); next(r)
        for row in r:
            d = datetime.date(int(row[0][:4]), int(row[0][4:6]), int(row[0][6:]))
            if d.weekday() >= 5: continue          # 토 · 일 제외. 7월에는 공휴일이 없다
            hr = int(row[1])
            if hr not in (3, 14): continue
            days.add(row[0])
            a = acc.setdefault(row[2], {3: [0.0, 0], 14: [0.0, 0]})
            a[hr][0] += float(row[3] or 0); a[hr][1] += 1
    miss = set(acc) ^ set(names)
    if miss: sys.exit(f'경계와 맞지 않는 코드: {sorted(miss)}')
    with open(DATA / '서울_생활인구_202607_평일.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['adm_cd', '자치구', '행정동', '평일14시_생활인구', '평일03시_생활인구', '평일수'])
        for c in sorted(acc):
            a = acc[c]
            w.writerow([c, names[c]['gu'], names[c]['dong'],
                        round(a[14][0] / a[14][1]), round(a[3][0] / a[3][1]), a[14][1]])
    print(f'생활인구  {len(acc)}동 · 평일 {len(days)}일')

    # ── 따릉이: 머리 다섯 줄이 병합 셀이라 여섯째 줄부터 ──
    xl = next(raw.glob('*대여소*.xlsx'))
    rows = xlsx_rows(xl)[5:]
    n = 0
    with open(DATA / '서울_따릉이대여소_2606.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['대여소번호', '대여소명', '자치구', '주소', 'lat', 'lon', '거치대수'])
        for r in rows:
            r += [''] * (10 - len(r))
            try: lat, lon = float(r[4]), float(r[5])
            except ValueError: continue
            if not lat or not lon: continue
            w.writerow([r[0], r[1].strip(), r[2], r[3], round(lat, 6), round(lon, 6), r[7] or r[8]])
            n += 1
    print(f'따릉이  {n}곳 (좌표 없는 행 {len(rows) - n} 제외)')

if __name__ == '__main__':
    main()
