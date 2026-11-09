#!/usr/bin/env python3
"""경계 효과 확인: 아산 인구 격자에서 직선 5km 안에 있는 시 밖의 의과 의사를 센다.

    python3 08-경계확인.py <1.병원정보서비스 2025.3.csv>

입력은 GIS 기초 및 실습 10주차 자료다 (건강보험심사평가원 전국 병의원 현황, 2025년 3월).
실습 자료가 아니므로 data/ 에 두지 않는다. 격자와 T=10 접근성은 08-아산2SFCA.py 가 만든 08-아산2SFCA-격자.csv 를 읽는다.
결과 08-경계확인-시밖기관.csv 를 슬라이드 지도가 쓴다. 표준 라이브러리만 쓴다.
"""
import collections as C
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KX, KY = 111320 * math.cos(math.radians(36.8)), 110940
LIM = 5000
xy = lambda lon, lat: (lon * KX, lat * KY)

grid = list(csv.DictReader(open(os.path.join(HERE, '08-아산2SFCA-격자.csv'), encoding='utf-8-sig')))
pts = {g['gid']: xy(float(g['lon']), float(g['lat'])) for g in grid}
pop = {g['gid']: float(g['인구']) for g in grid}
a10 = {g['gid']: float(g['A10_천명당']) for g in grid}
xs, ys = [p[0] for p in pts.values()], [p[1] for p in pts.values()]
cell = C.defaultdict(list)
for k, (x, y) in pts.items():
    cell[(int(x // LIM), int(y // LIM))].append(k)
out, near = [], set()
for r in csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')):
    if r['시군구코드명'] == '아산시' or not r['좌표(X)']:
        continue
    if r['종별코드명'] not in ('의원', '병원', '종합병원', '상급종합', '보건소', '보건지소', '보건진료소'):
        continue
    doc = sum(float(r[c] or 0) for c in ('의과일반의 인원수', '의과인턴 인원수', '의과레지던트 인원수', '의과전문의 인원수'))
    if doc <= 0:
        continue
    x, y = xy(float(r['좌표(X)']), float(r['좌표(Y)']))
    if not (min(xs) - LIM <= x <= max(xs) + LIM and min(ys) - LIM <= y <= max(ys) + LIM):
        continue
    cx, cy = int(x // LIM), int(y // LIM)
    hit = [k for a in (cx - 1, cx, cx + 1) for b in (cy - 1, cy, cy + 1) for k in cell.get((a, b), ())
           if math.hypot(pts[k][0] - x, pts[k][1] - y) <= LIM]
    if hit:
        near.update(hit)
        out.append((r['요양기관명'], r['종별코드명'], r['시군구코드명'], int(doc), r['좌표(X)'], r['좌표(Y)']))
with open(os.path.join(HERE, '08-경계확인-시밖기관.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['기관', '종별', '시군구', '의과의사', 'lon', 'lat'])
    w.writerows(sorted(out, key=lambda t: -t[3]))
by = C.Counter()
for t in out:
    by[t[2]] += t[3]
print('5km 안 시 밖 기관', len(out), '곳 · 의과의사', sum(t[3] for t in out), by.most_common())
ks = sorted(pts, key=lambda k: a10[k])
low = ks[:len(ks) // 10]
print('5km 안 격자 %.1f%% · 인구 %.1f%%' % (len(near) / len(ks) * 100, sum(pop[k] for k in near) / sum(pop.values()) * 100))
print('T10 하위 10%% 격자 %d칸 중 경계 5km 안 %.1f%%' % (len(low), sum(k in near for k in low) / len(low) * 100))
