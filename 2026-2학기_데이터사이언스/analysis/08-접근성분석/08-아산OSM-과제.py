#!/usr/bin/env python3
"""8강 과제의 기준값: 실습과 같은 2SFCA 를 OSM 도로망으로 다시 계산한다. 실습(표준노드링크)은 08-아산2SFCA.py.

    ~/.venvs/osmnx/bin/python 08-아산OSM-과제.py           결과 CSV 와 링크 지도 PNG 를 만들고 숫자를 찍는다
    ~/.venvs/osmnx/bin/python 08-아산OSM-과제.py --slide   슬라이드 head 에 넣을 window.ASAN_RAW 를 찍는다

다른 주차와 달리 osmnx 가 필요하다 (pip install osmnx scikit-learn matplotlib). 학생 실습과 같은 도구를 쓰기 위해서다.
도로망은 처음 한 번 OSM 에서 내려받아 data/ 에 graphml 로 남기고, 그다음부터는 그 파일을 읽는다.
OSM 은 수시로 고쳐지므로 내려받은 날짜가 다르면 값이 조금 달라진다. 판단 근거는 08-아산2SFCA-로직.md.
"""
import csv
import json
import math
import os
import statistics as st
import sys
import unicodedata as U
from collections import Counter, defaultdict

import networkx as nx
import osmnx as ox

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
GRAPH = os.path.join(DATA, '아산_osm_drive.graphml')
YEAR = '2023'
PAD = 0.05                       # 격자 경위도 범위 바깥으로 둔 여유(도). 약 4.5~5.6km. 경계 너머로 돌아가는 길을 살린다
TS = (5, 10, 15, 20, 30)
BASE_T = 10
MEDICAL = {'의원', '병원', '종합병원', '보건소', '보건지소', '보건진료소'}
LAT0 = 36.8
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110940
ox.settings.cache_folder = os.path.expanduser('~/.cache/osmnx')   # Drive 밖


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
    cen = {}
    for f in json.load(open(path('12.아산시_격자')))['features']:
        ring = f['geometry']['coordinates'][0][:-1]
        cen[f['properties']['gid']] = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    return {k: (cen[k], pop[k]) for k in sorted(pop) if pop[k] > 0}, cen


def load_supply():
    rows = list(csv.DictReader(open(path('21.아산시_병원정보'), encoding='utf-8-sig')))
    return rows, [h for h in rows if h['mdcl_gbn'] in MEDICAL and float(h['doc_cnt'] or 0) > 0]


def load_graph(cen):
    if os.path.exists(GRAPH):
        return ox.load_graphml(GRAPH)
    # 격자 경계(폴리곤)의 경위도 범위. 중심점의 범위보다 반 칸씩 넓다
    pts = [p for f in json.load(open(path('12.아산시_격자')))['features'] for p in f['geometry']['coordinates'][0]]
    lon = [p[0] for p in pts]
    lat = [p[1] for p in pts]
    G = ox.graph_from_bbox((min(lon) - PAD, min(lat) - PAD, max(lon) + PAD, max(lat) + PAD), network_type='drive')
    # 단순화로 합쳐진 링크는 highway · maxspeed 가 목록으로 남고, 그 순서가 실행마다 바뀐다.
    # osmnx 는 목록의 첫 값으로 속도를 채우므로 정렬하지 않으면 실행마다 값이 달라진다
    for _, _, d in G.edges(data=True):
        for k in ('highway', 'maxspeed'):
            if isinstance(d.get(k), list):
                d[k] = sorted(d[k])
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    ox.save_graphml(G, GRAPH)
    return G


def tsfca(T, demand, supply, od):
    """od[j] = {격자: 분}. R_j = 의사 ÷ T 안 인구, A_i = T 안 R_j 합."""
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
    allh, supply = load_supply()
    G = load_graph(cen)
    ks = list(demand)
    gnode = ox.distance.nearest_nodes(G, [demand[k][0][0] for k in ks], [demand[k][0][1] for k in ks])
    hnode = ox.distance.nearest_nodes(G, [float(h['lon']) for h in supply], [float(h['lat']) for h in supply])
    # 격자 → 병원 방향의 최단 통행시간. 병원을 출발점으로 삼되 뒤집은 그래프에서 구하면 같은 값이다
    Gr = G.reverse(copy=False)
    od = []
    for n in hnode:
        D = nx.single_source_dijkstra_path_length(Gr, n, weight='travel_time')
        od.append({k: D[g] / 60 for k, g in zip(ks, gnode) if g in D})
    res = {T: tsfca(T, demand, supply, od) for T in TS}
    TOT, DOC = sum(v[1] for v in demand.values()), sum(float(h['doc_cnt']) for h in supply)
    times = [t for o in od for t in o.values()]
    near = {k: min((o[k] for o in od if k in o), default=None) for k in ks}
    table = []
    for T in TS:
        A = res[T][0]
        v = [A.get(k, 0) * 1000 for k in ks]
        table.append({'T': T, '평균': sum(A.get(k, 0) * demand[k][1] for k in ks) / TOT * 1000, '중앙값': st.median(v), '최댓값': max(v),
                      '지니': gini(A, demand), 'A0인구비율': sum(demand[k][1] for k in ks if A.get(k, 0) == 0) / TOT * 100,
                      '수요없는병원': sum(r[1] == 0 for r in res[T][1])})
    rho = pearson(ranks([res[10][0].get(k, 0) for k in ks]), ranks([res[15][0].get(k, 0) for k in ks]))
    A10, R10 = res[BASE_T]
    et = [d['travel_time'] for _, _, d in G.edges(data=True)]
    info = {'nodes': G.number_of_nodes(), 'edges': G.number_of_edges(), 'km': float(sum(d['length'] for _, _, d in G.edges(data=True)) / 1000 / 2),
            'edge_s_median': st.median(et), 'edge_s_max': max(et),
            'speed': Counter(round(d['speed_kph']) for _, _, d in G.edges(data=True)).most_common(8)}
    stats = {'pairs_total': len(ks) * len(supply), 'pairs': len(times), 'unreached_pairs': len(ks) * len(supply) - len(times),
             'mean': st.mean(times), 'median': st.median(times), 'min': min(times), 'max': max(times), 'sd': st.pstdev(times),
             'p25': pct(times, .25), 'p75': pct(times, .75), 'le10': sum(t <= 10 for t in times) / len(times) * 100,
             'near_mean': sum(near[k] * demand[k][1] for k in ks if near[k] is not None) / TOT,
             'near_max': max(v for v in near.values() if v is not None), 'near_unreached': sum(v is None for v in near.values())}
    if '--slide' in sys.argv:
        return slide(demand, cen, supply, A10, R10, near, table, rho, stats, od, ks, allh)
    with open(os.path.join(HERE, '08-아산OSM-격자.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['gid', 'lon', 'lat', '인구', '최단시간분'] + [f'A{T}_천명당' for T in TS])
        for k in ks:
            w.writerow([k, round(demand[k][0][0], 6), round(demand[k][0][1], 6), int(demand[k][1]),
                        None if near[k] is None else round(near[k], 2)] + [round(res[T][0].get(k, 0) * 1000, 4) for T in TS])
    with open(os.path.join(HERE, '08-아산OSM-병원.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['기관', '종별', '의사', 'lon', 'lat', f'T{BASE_T}수요', f'T{BASE_T}R_천명당'])
        for h, (r, dem) in zip(supply, R10):
            w.writerow([h['mdcl_inst'], h['mdcl_gbn'], int(float(h['doc_cnt'])), h['lon'], h['lat'], int(dem), round(r * 1000, 3)])
    with open(os.path.join(HERE, '08-아산OSM-T민감도.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(table[0].keys())
        for r in table:
            w.writerow([round(x, 4) if isinstance(x, float) else x for x in r.values()])
    link_map(G, cen)
    print('수요', len(demand), '칸', int(TOT), '명 · 공급', len(supply), '곳', int(DOC), '명')
    print('도로', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in info.items()})
    print('시간거리', {k: round(v, 2) if isinstance(v, float) else v for k, v in stats.items()})
    for r in table:
        print({a: round(b, 3) if isinstance(b, float) else b for a, b in r.items()})
    print('보존 %.3f · 순위상관 T10~T15 %.3f' % (DOC / TOT * 1000, rho))
    top = sorted(zip(supply, R10), key=lambda x: -x[1][0])[:5]
    print('R 상위', [(h['mdcl_inst'], h['doc_cnt'], int(d), round(r * 1000, 2)) for h, (r, d) in top])


def link_map(G, cen):
    """링크마다 소요시간(초)으로 칠한 지도. 슬라이드 assets 로 쓴다."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ('AppleSDGothicNeo', 'Apple SD Gothic Neo'):
        try:
            font_manager.findfont(f, fallback_to_default=False)
            plt.rcParams['font.family'] = f
        except Exception:
            pass
    B = [10, 20, 40, 80]
    COL = ['#D3DFEA', '#8FB0CE', '#4F7FAE', '#A8455C', '#6E1A31']
    lon0, lat0 = min(c[0] for c in cen.values()), min(c[1] for c in cen.values())
    fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=200)
    for a, b in {(int((c[0] - lon0) * KX // 500), int((c[1] - lat0) * KY // 500)) for c in cen.values()}:
        ax.add_patch(plt.Rectangle((a * .5, b * .5), .5, .5, color='#EDE9E3', lw=0, zorder=0))
    segs = defaultdict(list)
    for u, v, d in G.edges(data=True):
        if 'geometry' in d:
            xs, ys = d['geometry'].xy
        else:
            xs, ys = [G.nodes[u]['x'], G.nodes[v]['x']], [G.nodes[u]['y'], G.nodes[v]['y']]
        c = sum(d['travel_time'] > b for b in B)
        segs[c].append(([(x - lon0) * KX / 1000 for x in xs], [(y - lat0) * KY / 1000 for y in ys]))
    n = Counter({c: len(s) for c, s in segs.items()})
    for c in range(5):
        for xs, ys in segs[c]:
            ax.plot(xs, ys, color=COL[c], lw=.25 + .12 * c, solid_capstyle='round', zorder=1 + c)
    xs = [(c[0] - lon0) * KX / 1000 for c in cen.values()]
    ys = [(c[1] - lat0) * KY / 1000 for c in cen.values()]
    ax.set_xlim(min(xs) - 1, max(xs) + 1)
    ax.set_ylim(min(ys) - 1, max(ys) + 1)
    ax.set_aspect('equal')
    ax.axis('off')
    lab = ['~ 10초', '10 ~ 20초', '20 ~ 40초', '40 ~ 80초', '80초 ~']
    for c in range(5):
        ax.plot([], [], color=COL[c], lw=2.5, label=f'{lab[c]} ({n[c]:,})')
    ax.legend(loc='center left', bbox_to_anchor=(1.01, .55), fontsize=8, frameon=False, title='링크 소요시간 (링크 수)', title_fontsize=8, alignment='left')
    ax.annotate('N', xy=(.05, .97), xytext=(.05, .88), xycoords='axes fraction', ha='center', fontsize=8, fontweight='bold',
                arrowprops=dict(facecolor='#4A4741', width=2.5, headwidth=8, lw=0))
    fx = 5 / (max(xs) - min(xs) + 2)                  # 5km 를 축 비율로. 축척은 범례 아래 빈자리에 둔다
    ax.plot([1.03, 1.03 + fx], [.2, .2], color='#4A4741', lw=2, transform=ax.transAxes, clip_on=False)
    ax.text(1.05 + fx, .2, '5km', fontsize=7.5, va='center', color='#6E6A63', transform=ax.transAxes)
    ax.text(1.03, .27, '회색 바탕: 아산 격자 범위', fontsize=7.5, color='#6E6A63', transform=ax.transAxes)
    ax.text(1.02, .02, '© OpenStreetMap contributors', transform=ax.transAxes, ha='left', va='bottom', fontsize=6.5, color='#8F8A82')
    out = os.path.join(HERE, '..', '..', 'assets', 'osm-asan-link-time.png')
    fig.savefig(out, bbox_inches='tight', pad_inches=.02, facecolor='white')
    print('링크 지도', out, dict(sorted(n.items())))


def slide(demand, cen, supply, A10, R10, near, table, rho, stats, od, ks, allh):
    lon0, lat0 = min(c[0] for c in cen.values()), min(c[1] for c in cen.values())
    to = lambda lon, lat: (round((lon - lon0) * KX / 10), round((lat - lat0) * KY / 10))
    bg = sorted({(to(*c)[0] // 50, to(*c)[1] // 50) for c in cen.values()})
    cells = [(*to(*demand[k][0]), int(demand[k][1]), round(A10.get(k, 0) * 1000, 2)) for k in ks]
    hosp = [(*to(float(h['lon']), float(h['lat'])), int(float(h['doc_cnt'])), round(r * 1000, 2)) for h, (r, _) in zip(supply, R10)]
    label = defaultdict(list)
    for h in allh:
        label['온양' if h['emd_nm'] == '온천동' else h['emd_nm']].append(to(float(h['lon']), float(h['lat'])))
    names = {n: (round(st.median(p[0] for p in label[n])), round(st.median(p[1] for p in label[n])))
             for n in ('온양', '배방읍', '탕정면', '둔포면', '음봉면', '신창면', '도고면', '선장면', '송악면', '인주면')}
    # 표에 보일 시간거리 표본: 인구가 가장 많은 격자 셋 × 의사가 가장 많은 기관 셋
    big = sorted(ks, key=lambda k: -demand[k][1])[:3]
    hs = sorted(range(len(supply)), key=lambda j: -float(supply[j]['doc_cnt']))[:3]
    sample = [[k, int(demand[k][1]), supply[j]['mdcl_inst'], int(float(supply[j]['doc_cnt'])), round(od[j][k], 1)] for k in big for j in hs if k in od[j]]
    hist = Counter(min(int(t // 5), 12) for o in od for t in o.values())
    print('window.ASAN_RAW = ' + json.dumps({
        'lon0': lon0, 'lat0': lat0, 'bg': ';'.join(f'{a},{b}' for a, b in bg),
        'cells': ';'.join(','.join(map(str, c)) for c in cells), 'hosp': ';'.join(','.join(map(str, c)) for c in hosp),
        'names': names, 'table': [{k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()} for r in table],
        'rho': round(rho, 3), 'stats': {k: round(v, 2) if isinstance(v, float) else v for k, v in stats.items()},
        'sample': sample, 'hist': [hist.get(i, 0) for i in range(13)],
        'kinds': [[k, sum(1 for h in supply if h['mdcl_gbn'] == k), sum(int(float(h['doc_cnt'])) for h in supply if h['mdcl_gbn'] == k)]
                  for k in ('의원', '병원', '종합병원', '보건소', '보건지소')],
        'r_top': [[h['mdcl_inst'], h['mdcl_gbn'], int(float(h['doc_cnt'])), int(d), round(r * 1000, 3)]
                  for h, (r, d) in sorted(zip(supply, R10), key=lambda x: -x[1][0])[:5]],
    }, ensure_ascii=False, separators=(',', ':')) + ';')


if __name__ == '__main__':
    main()
