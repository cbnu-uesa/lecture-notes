#!/usr/bin/env python3
"""13강(공간최적화)의 나머지 다섯 방법 사례를 만든다.

  1 집합덮개 LSCP    모두를 덮는 최소 개수
  3 p-중앙값         총 이동거리 합을 최소로
  4 p-센터           가장 먼 사람의 거리를 최소로
  5 입지-배분        시설을 놓고 수요를 배정까지
  6 다목적 가중합    커버와 거리를 가중치로 합친다

13-광양충전소.py 가 2번(최대커버 MCLP)을 맡고, 이 스크립트가 나머지를 맡는다.
자료·반경·후보지가 모두 같아 여섯 방법을 나란히 견줄 수 있다.

외부 라이브러리를 쓰지 않는다. 정수계획 solver 가 없으므로 **탐욕 휴리스틱**으로 푼다.
최적해가 아니며 얼마나 못 미치는지는 알 수 없다 — 로직 문서에 적었다.
난수를 쓰지 않는다.

    python3 13-광양입지최적화.py

로직: 13-광양입지최적화-로직.md 를 먼저 읽는다.
"""
import csv, importlib.util, math, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
P = 8                 # 놓을 시설 개수. 13-광양충전소.py 의 K 와 맞춘다

spec = importlib.util.spec_from_file_location('base', HERE / '13-광양충전소.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def load():
    import json
    grid = []
    with open(base.BASE / '08.광양시_격자별인구현황(100X100).geojson', encoding='utf-8') as f:
        for feat in json.load(f)['features']:
            v = feat['properties'].get('val')
            if not v: continue
            x, y = base.centroid(feat['geometry'])
            grid.append((x, y, float(v)))
    cands = [(p, n) for p, n in ((base.lonlat(r), r['주차장명칭'])
             for r in base.read_csv('02.광양시_주차장_공간정보.csv')) if p]
    return grid, cands

def save(name, header, rows):
    p = HERE / name
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f'  → {p.name}')

def main():
    grid, cands = load()
    total = sum(g[2] for g in grid)
    R = base.RADIUS_KM
    print(f'수요 격자 {len(grid):,}개 · 총인구 {total:,.0f}명 · 후보 {len(cands)}곳 · 반경 {R*1000:.0f}m\n')

    # 거리행렬 (km). 후보 × 수요
    D = [[base.km(gx, gy, px, py) for gx, gy, _ in grid] for (px, py), _ in cands]
    reach = [[i for i, d in enumerate(row) if d <= R] for row in D]
    w = [g[2] for g in grid]
    name = [n for _, n in cands]

    # ── 1. 집합덮개 LSCP ─────────────────────────────────────
    coverable = set()
    for r in reach: coverable |= set(r)
    print(f'집합덮개 LSCP — 반경 {R*1000:.0f}m 로 덮을 수 있는 격자 '
          f'{len(coverable):,}/{len(grid):,}개 ({sum(w[i] for i in coverable)/total*100:.1f}%)')
    left = set(coverable); pick = []
    while left:
        b = max(range(len(cands)), key=lambda c: len(left & set(reach[c])))
        if not (left & set(reach[b])): break
        pick.append(b); left -= set(reach[b])
    print(f'  덮을 수 있는 것을 모두 덮는 데 필요한 최소 개수 ≈ {len(pick)}곳 (탐욕해)')
    print(f'  → 덮을 수 없는 격자 {len(grid)-len(coverable):,}개는 어떤 후보로도 닿지 않는다')
    save('13-광양최적화-LSCP.csv', ['순서', '후보지'],
         [[i + 1, name[c]] for i, c in enumerate(pick)])

    # ── 3. p-중앙값 ──────────────────────────────────────────
    def total_dist(sel):
        return sum(w[i] * min(D[c][i] for c in sel) for i in range(len(grid)))
    sel = []
    for _ in range(P):
        b = min((c for c in range(len(cands)) if c not in sel),
                key=lambda c: total_dist(sel + [c]))
        sel.append(b)
    for _ in range(30):                     # 교환 개선 (Teitz-Bart)
        best = (total_dist(sel), None)
        for i in range(len(sel)):
            for c in range(len(cands)):
                if c in sel: continue
                trial = sel[:i] + [c] + sel[i+1:]
                v = total_dist(trial)
                if v < best[0]: best = (v, trial)
        if best[1] is None: break
        sel = best[1]
    med_d = total_dist(sel) / total
    print(f'\np-중앙값 (p={P}) — 인구가중 평균거리 {med_d*1000:.0f}m')
    print('  ' + ' · '.join(name[c] for c in sel[:4]) + ' …')
    save('13-광양최적화-p중앙값.csv', ['후보지'], [[name[c]] for c in sel])

    # ── 4. p-센터 ────────────────────────────────────────────
    def worst(sel):
        return max(min(D[c][i] for c in sel) for i in range(len(grid)))
    cen = []
    for _ in range(P):
        b = min((c for c in range(len(cands)) if c not in cen),
                key=lambda c: worst(cen + [c]))
        cen.append(b)
    for _ in range(20):
        best = (worst(cen), None)
        for i in range(len(cen)):
            for c in range(len(cands)):
                if c in cen: continue
                trial = cen[:i] + [c] + cen[i+1:]
                v = worst(trial)
                if v < best[0]: best = (v, trial)
        if best[1] is None: break
        cen = best[1]
    print(f'\np-센터 (p={P}) — 가장 먼 격자까지 {worst(cen)*1000:.0f}m '
          f'(p-중앙값 해로는 {worst(sel)*1000:.0f}m)')
    print(f'  같은 해의 인구가중 평균거리는 {total_dist(cen)/total*1000:.0f}m '
          f'— p-중앙값보다 {(total_dist(cen)/total - med_d)*1000:+.0f}m')
    save('13-광양최적화-p센터.csv', ['후보지'], [[name[c]] for c in cen])

    # ── 5. 입지-배분 ─────────────────────────────────────────
    assign = [min(sel, key=lambda c: D[c][i]) for i in range(len(grid))]
    served = {c: 0.0 for c in sel}
    far = {c: 0.0 for c in sel}
    for i, c in enumerate(assign):
        served[c] += w[i]; far[c] = max(far[c], D[c][i])
    print(f'\n입지-배분 — p-중앙값 해에 수요를 가장 가까운 시설로 배정')
    print(f"  {'시설':<24}{'배정 인구':>10}{'몫':>7}{'최원거리':>10}")
    for c in sorted(sel, key=lambda c: -served[c]):
        print(f'  {name[c][:22]:<24}{served[c]:>9,.0f}{served[c]/total*100:>6.1f}%{far[c]*1000:>9.0f}m')
    print(f'  가장 무거운 곳이 가장 가벼운 곳의 '
          f'{max(served.values())/max(min(served.values()), 1):.1f}배')
    save('13-광양최적화-입지배분.csv', ['시설', '배정인구', '몫(%)', '최원거리(m)'],
         [[name[c], round(served[c]), round(served[c]/total*100, 1), round(far[c]*1000)]
          for c in sorted(sel, key=lambda c: -served[c])])

    # ── 6. 다목적 가중합 ─────────────────────────────────────
    print(f'\n다목적 가중합 — 커버(최대화)와 평균거리(최소화)를 가중치로 합친다')
    print(f"  {'가중치 α':>9}{'커버':>10}{'평균거리':>10}   선택이 바뀐 곳")
    rows = []
    prev = None
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        # 목적함수를 0~1 로 맞춘 뒤 α 로 섞는다
        pickm = []
        for _ in range(P):
            def score(c):
                s = pickm + [c]
                cov = sum(w[i] for i in set().union(*[set(reach[x]) for x in s])) / total
                dis = sum(w[i] * min(D[x][i] for x in s) for i in range(len(grid))) / total
                return a * cov - (1 - a) * (dis / 5.0)      # 5km 로 정규화
            b = max((c for c in range(len(cands)) if c not in pickm), key=score)
            pickm.append(b)
        cov = sum(w[i] for i in set().union(*[set(reach[x]) for x in pickm])) / total
        dis = sum(w[i] * min(D[x][i] for x in pickm) for i in range(len(grid))) / total
        chg = '—' if prev is None else f'{len(set(pickm) - set(prev))}곳'
        print(f'  {a:>9.2f}{cov*100:>9.1f}%{dis*1000:>9.0f}m   {chg}')
        rows.append([a, round(cov*100, 1), round(dis*1000), ' · '.join(name[c] for c in pickm)])
        prev = pickm
    print('  → α 는 자료가 정해 주지 않는다. 무엇을 더 중히 볼지는 사람이 정한다')
    save('13-광양최적화-다목적.csv', ['α(커버 가중치)', '커버(%)', '평균거리(m)', '선택'], rows)

if __name__ == '__main__':
    main()
