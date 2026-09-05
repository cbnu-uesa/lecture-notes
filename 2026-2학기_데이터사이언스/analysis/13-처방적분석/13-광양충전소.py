#!/usr/bin/env python3
"""13강(처방적 분석) — 광양 전기차 충전소를 어디에 더 놓을 것인가.

최대커버 문제를 탐욕 알고리즘으로 푼다.
입력: ~/data/compas/gwangyang-ev/  (COMPAS 「전기자동차 충전소 최적입지 선정」
      광양시, SBJ_2009_001 공개 데이터)
로직: 13-광양충전소-로직.md 를 먼저 읽는다.
"""
import csv, json, math, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / 'data'      # 원자료는 주차 폴더 밖, analysis/data/ 에 함께 둔다
# 없으면 내려받아 둔 곳(~/data/compas)을 본다.
BASE = (DATA if (DATA / '01.광양시_충전기설치현황.csv').exists()
        else pathlib.Path.home() / 'data/compas/gwangyang-ev')
RADIUS_KM = 0.5      # 걸어서 갈 만한 거리로 잡은 기준. 바꾸면 답이 달라진다
K = 8                # 추가로 놓을 개수

def centroid(g):
    pts = []
    for poly in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]):
        pts += poly[0]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

def km(ax, ay, bx, by):
    """위도 35도 부근의 도(度) → km 근사. 광양 정도의 범위에서는 충분하다."""
    return math.hypot((ax - bx) * 88.9, (ay - by) * 111.0)

def read_csv(name):
    with open(BASE / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def lonlat(r):
    try:
        return float(r['lon']), float(r['lat'])
    except (TypeError, ValueError, KeyError):
        return None

def main():
    if not BASE.exists():
        sys.exit(f'원본이 없습니다: {BASE}')

    grid = []
    with open(BASE / '08.광양시_격자별인구현황(100X100).geojson', encoding='utf-8') as f:
        for feat in json.load(f)['features']:
            v = feat['properties'].get('val')
            if not v:
                continue
            x, y = centroid(feat['geometry'])
            grid.append((x, y, float(v)))
    total = sum(g[2] for g in grid)
    print(f'수요 격자 {len(grid):,}개 · 총인구 {total:,.0f}명')

    exist = [p for p in (lonlat(r) for r in read_csv('01.광양시_충전기설치현황.csv')) if p]
    cands = [(lonlat(r), r['주차장명칭']) for r in read_csv('02.광양시_주차장_공간정보.csv')]
    cands = [(p, n) for p, n in cands if p]
    print(f'기존 충전기 {len(exist)}기 · 후보 주차장 {len(cands)}곳\n')

    covered = [any(km(gx, gy, ex, ey) <= RADIUS_KM for ex, ey in exist)
               for gx, gy, _ in grid]
    base = sum(g[2] for i, g in enumerate(grid) if covered[i])
    print(f'기존 충전기의 반경 {RADIUS_KM*1000:.0f}m 커버 '
          f'{base:,.0f}명 ({base/total*100:.1f}%)\n')

    reach = [[i for i, (gx, gy, _) in enumerate(grid) if km(gx, gy, px, py) <= RADIUS_KM]
             for (px, py), _ in cands]

    chosen, cov, table = [], covered[:], []
    print(f"{'순서':<4}{'후보지':<26}{'새로 덮는 인구':>14}{'누적 커버':>12}")
    for step in range(1, K + 1):
        gains = [(sum(grid[i][2] for i in reach[j] if not cov[i]), j)
                 for j in range(len(cands)) if j not in chosen]
        gain, best = max(gains)
        if gain <= 0:
            break
        chosen.append(best)
        for i in reach[best]:
            cov[i] = True
        now = sum(g[2] for i, g in enumerate(grid) if cov[i])
        print(f'{step:<4}{cands[best][1][:24]:<26}{gain:>13,.0f}명'
              f'{now/total*100:>11.1f}%')
        table.append([step, cands[best][1], round(cands[best][0][0], 6),
                      round(cands[best][0][1], 6), round(gain), round(now / total * 100, 1)])

    path = HERE / '13-광양충전소-선정지.csv'
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['순서', '후보지', '경도', '위도', '새로덮는인구', '누적커버(%)'])
        w.writerows(table)
        w.writerow([])
        w.writerow(['반경(m)', RADIUS_KM * 1000, '총인구', round(total),
                    '기존 커버(%)', round(base / total * 100, 1)])
    print(f'\n요약표 저장\n  → {path.name}')

if __name__ == '__main__':
    main()
