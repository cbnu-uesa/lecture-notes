#!/usr/bin/env python3
"""8강 실습: 아산시 격자 인구 · 의과 기관 · COMPAS 표준노드링크로 2SFCA 를 계산한다.

    ~/.venvs/osmnx/bin/python 08-아산2SFCA.py           결과 CSV 를 만들고 숫자를 찍는다
    ~/.venvs/osmnx/bin/python 08-아산2SFCA.py --slide   슬라이드 head 에 넣을 window.ASAN_RAW 를 찍는다

학생이 클로드에게 시키는 방식(geopandas · networkx)과 같은 도구로 계산한다. 그래야 프롬프트 실험의 값과 맞는다.
길이와 최근접 노드는 EPSG:5179 에서 구한다. 과제(OSM)의 기준값은 08-아산OSM-과제.py.
판단 근거는 08-아산2SFCA-로직.md.
"""
import csv
import json
import math
import os
import statistics as st
import sys
import unicodedata as U
from collections import Counter, defaultdict

import geopandas as gpd
import networkx as nx
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
YEAR = '2023'
TS = (5, 10, 15, 20, 30)
BASE_T = 10
MEDICAL = {'의원', '병원', '종합병원', '보건소', '보건지소', '보건진료소'}
LAT0 = 36.8                      # 슬라이드 지도 좌표(등거리 근사)용
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110940


def path(prefix):
    for f in os.listdir(DATA):
        if U.normalize('NFC', f).startswith(prefix):
            return os.path.join(DATA, f)
    raise FileNotFoundError(prefix)


def load_demand():
    rows = list(csv.DictReader(open(path('1.아산시_거주인구'), encoding='utf-8-sig')))
    cols = [c for c in rows[0] if c.endswith('_pop')]
    pop = Counter()
    for r in rows:
        if r['year'] == YEAR:
            for c in cols:
                if r[c]:
                    pop[r['gid']] += float(r[c])
    g = gpd.read_file(path('12.아산시_격자')).to_crs(5179)
    c = g.set_index('gid').geometry.centroid
    ll = gpd.GeoSeries(c, crs=5179).to_crs(4326)
    keep = sorted(k for k in pop if pop[k] > 0)
    return {k: ((c[k].x, c[k].y), pop[k], (ll[k].x, ll[k].y)) for k in keep}, {k: (p.x, p.y) for k, p in ll.items()}


def load_supply():
    rows = list(csv.DictReader(open(path('21.아산시_병원정보'), encoding='utf-8-sig')))
    keep = [h for h in rows if h['mdcl_gbn'] in MEDICAL and float(h['doc_cnt'] or 0) > 0]
    pts = gpd.GeoSeries(gpd.points_from_xy([float(h['lon']) for h in keep], [float(h['lat']) for h in keep]), crs=4326).to_crs(5179)
    return rows, keep, [(p.x, p.y) for p in pts]


def load_graph():
    nodes = gpd.read_file(path('14.아산시_표준노드')).to_crs(5179)
    links = gpd.read_file(path('15.아산시_표준링크'))
    ids = set(nodes['NODE_ID'])
    ok = links['F_NODE'].isin(ids) & links['T_NODE'].isin(ids)
    missing = int((~ok).sum())
    links = links[ok].copy()
    links['len_m'] = links.to_crs(5179).length
    links['time_min'] = links['len_m'] / (links['MAX_SPD'] * 1000 / 60)
    G = nx.DiGraph()                 # 같은 방향의 링크가 겹치면 짧은 쪽만 남긴다
    for f, t, m in zip(links['F_NODE'], links['T_NODE'], links['time_min']):
        if not G.has_edge(f, t) or m < G[f][t]['time']:
            G.add_edge(f, t, time=m)
    # 어느 노드에서든 서로 오갈 수 있는 가장 큰 덩어리(강연결). 일방통행 때문에 들어가기만 하고 못 나오는 노드를 뺀다
    comp = max(nx.strongly_connected_components(G), key=len)
    links = links[links['F_NODE'].isin(comp)].copy()          # 큰 덩어리에 남은 링크 행
    et = [d['time'] * 60 for _, _, d in G.subgraph(comp).edges(data=True)]
    info = {'missing': missing, 'comp_nodes': len(comp), 'graph_edges': len(et), 'link_rows': len(links),
            'time_s_median': st.median(et), 'time_s_max': max(et),
            'speed': sorted(Counter(int(s) for s in links['MAX_SPD']).items())}
    G = G.subgraph(comp).copy()
    xy = {n: (p.x, p.y) for n, p in zip(nodes['NODE_ID'], nodes.geometry) if n in comp}
    return G, xy, links, info


def tsfca(T, demand, supply, od):
    R, A = [], Counter()
    for j, h in enumerate(supply):
        catch = [k for k, t in od[j].items() if t <= T]
        dem = sum(demand[k][1] for k in catch)
        r = float(h['doc_cnt']) / dem if dem else 0.0
        R.append((r, dem))
        for k in catch:
            A[k] += r
    return A, R


def hand_check():
    dem = {'A': (None, 10), 'B': (None, 20)}
    sup = [{'doc_cnt': v} for v in (4, 2, 4, 1)]
    od = [{'A': a, 'B': b} for a, b in zip((14, 10, 12, 15), (10, 7, 8, 40))]
    a10, _ = tsfca(10, dem, sup, od)
    a15, _ = tsfca(15, dem, sup, od)
    for v, w in ((a10['A'], 2 / 30), (a10['B'], 7 / 15), (a15['A'], 13 / 30), (a15['B'], 1 / 3)):
        assert abs(v - w) < 1e-9, (v, w)


def gini(A, demand):
    a = sorted((A.get(k, 0), demand[k][1]) for k in demand)
    W, S = sum(w for _, w in a), sum(v * w for v, w in a)
    c = area = 0.0
    for v, w in a:
        area += w * (2 * c + v * w) / 2
        c += v * w
    return 1 - 2 * area / (W * S)


def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r, i = [0.0] * len(v), 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for x in range(i, j + 1):
            r[o[x]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def pct(v, q):
    v = sorted(v)
    k = (len(v) - 1) * q
    f = math.floor(k)
    return v[f] + (v[min(f + 1, len(v) - 1)] - v[f]) * (k - f)


def main():
    hand_check()
    demand, cen = load_demand()
    allh, supply, sxy = load_supply()
    G, nxy, links, info = load_graph()
    names = list(nxy)
    tree = cKDTree([nxy[n] for n in names])
    ks = list(demand)
    gd, gi = tree.query([demand[k][0] for k in ks])
    hd, hi = tree.query(sxy)
    gnode = [names[i] for i in gi]
    Gr = G.reverse(copy=False)
    od = []
    for i in hi:
        D = nx.single_source_dijkstra_path_length(Gr, names[i], weight='time')
        od.append({k: D[g] for k, g in zip(ks, gnode) if g in D})
    res = {T: tsfca(T, demand, supply, od) for T in TS}
    TOT, DOC = sum(v[1] for v in demand.values()), sum(float(h['doc_cnt']) for h in supply)
    times = [t for o in od for t in o.values()]
    near = {k: min((o[k] for o in od if k in o), default=None) for k in ks}
    table = []
    for T in TS:
        A = res[T][0]
        v = [A.get(k, 0) * 1000 for k in ks]
        table.append({'T': T, '평균': sum(A.get(k, 0) * demand[k][1] for k in ks) / TOT * 1000, '격자평균': st.mean(v), '중앙값': st.median(v), '최댓값': max(v),
                      '지니': gini(A, demand), 'A0인구비율': sum(demand[k][1] for k in ks if A.get(k, 0) == 0) / TOT * 100,
                      '수요없는병원': sum(r[1] == 0 for r in res[T][1])})
    rho = spearmanr([res[10][0].get(k, 0) for k in ks], [res[15][0].get(k, 0) for k in ks]).statistic   # 학생이 쓰는 scipy 와 같은 값
    A10, R10 = res[BASE_T]
    stats = {'pairs_total': len(ks) * len(supply), 'pairs': len(times), 'unreached_pairs': len(ks) * len(supply) - len(times),
             'unreached_grids': sum(v is None for v in near.values()),
             'mean': st.mean(times), 'median': st.median(times), 'min': min(times), 'max': max(times), 'sd': st.pstdev(times),
             'p25': pct(times, .25), 'p75': pct(times, .75), 'le10': sum(t <= 10 for t in times) / len(times) * 100,
             'snap_g_median': float(st.median(gd)), 'snap_g_max': float(max(gd)), 'snap_h_median': float(st.median(hd)), 'snap_h_max': float(max(hd))}
    if '--slide' in sys.argv:
        return slide(demand, cen, supply, A10, R10, table, rho, stats, od, ks, allh, links)
    with open(os.path.join(HERE, '08-아산2SFCA-격자.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['gid', 'lon', 'lat', '인구', '최단시간분'] + [f'A{T}_천명당' for T in TS])
        for k in ks:
            w.writerow([k, round(demand[k][2][0], 6), round(demand[k][2][1], 6), int(demand[k][1]),
                        None if near[k] is None else round(near[k], 2)] + [round(res[T][0].get(k, 0) * 1000, 4) for T in TS])
    with open(os.path.join(HERE, '08-아산2SFCA-병원.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['기관', '종별', '의사', 'lon', 'lat', f'T{BASE_T}수요', f'T{BASE_T}R_천명당'])
        for h, (r, dem) in zip(supply, R10):
            w.writerow([h['mdcl_inst'], h['mdcl_gbn'], int(float(h['doc_cnt'])), h['lon'], h['lat'], int(dem), round(r * 1000, 3)])
    with open(os.path.join(HERE, '08-아산2SFCA-T민감도.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(table[0].keys())
        for r in table:
            w.writerow([round(x, 4) if isinstance(x, float) else x for x in r.values()])
    print('수요', len(demand), '칸', int(TOT), '명 · 공급', len(supply), '곳', int(DOC), '명')
    print('도로', info)
    print('시간거리', stats)
    for r in table:
        print(r)
    print('보존 %.6f · 순위상관 T10~T15 %.6f' % (DOC / TOT * 1000, rho))
    print('R 상위', [(h['mdcl_inst'], h['doc_cnt'], int(d), r * 1000) for h, (r, d) in sorted(zip(supply, R10), key=lambda x: -x[1][0])[:5]])


def slide(demand, cen, supply, A10, R10, table, rho, stats, od, ks, allh, links):
    lon0, lat0 = min(c[0] for c in cen.values()), min(c[1] for c in cen.values())
    to = lambda lon, lat: (round((lon - lon0) * KX / 10), round((lat - lat0) * KY / 10))
    bg = sorted({(to(*c)[0] // 50, to(*c)[1] // 50) for c in cen.values()})
    cells = [(*to(*demand[k][2]), int(demand[k][1]), round(A10.get(k, 0) * 1000, 2)) for k in ks]
    hosp = [(*to(float(h['lon']), float(h['lat'])), int(float(h['doc_cnt'])), round(r * 1000, 3)) for h, (r, _) in zip(supply, R10)]
    label = defaultdict(list)
    for h in allh:
        label['온양' if h['emd_nm'] == '온천동' else h['emd_nm']].append(to(float(h['lon']), float(h['lat'])))
    names = {n: (round(st.median(p[0] for p in label[n])), round(st.median(p[1] for p in label[n])))
             for n in ('온양', '배방읍', '탕정면', '둔포면', '음봉면', '신창면', '도고면', '선장면', '송악면', '인주면')}
    # 링크: 소요시간(초) | 좌표 (50m 보다 가까운 꼭짓점은 건너뛴다)
    lk = []
    for geom, tm in zip(links.geometry, links['time_min']):
        pts = list(geom.coords) if geom.geom_type == 'LineString' else [p for g in geom.geoms for p in g.coords]
        q = [to(*pts[0])]
        for p in pts[1:-1]:
            x = to(*p)
            if abs(x[0] - q[-1][0]) + abs(x[1] - q[-1][1]) >= 5:
                q.append(x)
        q.append(to(*pts[-1]))
        lk.append(f"{round(tm * 60)}|" + ' '.join(f'{a},{b}' for a, b in q))
    big = sorted(ks, key=lambda k: -demand[k][1])[:3]
    hs = sorted(range(len(supply)), key=lambda j: -float(supply[j]['doc_cnt']))[:3]
    sample = [[k, int(demand[k][1]), supply[j]['mdcl_inst'], int(float(supply[j]['doc_cnt'])), round(od[j][k], 1)] for k in big for j in hs if k in od[j]]
    print('window.ASAN_RAW = ' + json.dumps({
        'lon0': lon0, 'lat0': lat0, 'bg': ';'.join(f'{a},{b}' for a, b in bg),
        'cells': ';'.join(','.join(map(str, c)) for c in cells), 'hosp': ';'.join(','.join(map(str, c)) for c in hosp),
        'links': '#'.join(lk), 'names': names,
        'table': [{k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()} for r in table],
        'rho': round(rho, 3), 'stats': {k: round(v, 2) if isinstance(v, float) else v for k, v in stats.items()}, 'sample': sample,
        'kinds': [[k, sum(1 for h in supply if h['mdcl_gbn'] == k), sum(int(float(h['doc_cnt'])) for h in supply if h['mdcl_gbn'] == k)]
                  for k in ('의원', '병원', '종합병원', '보건소', '보건지소')],
        'r_top': [[h['mdcl_inst'], h['mdcl_gbn'], int(float(h['doc_cnt'])), int(d), round(r * 1000, 3)]
                  for h, (r, d) in sorted(zip(supply, R10), key=lambda x: -x[1][0])[:5]],
    }, ensure_ascii=False, separators=(',', ':')) + ';')


if __name__ == '__main__':
    main()
