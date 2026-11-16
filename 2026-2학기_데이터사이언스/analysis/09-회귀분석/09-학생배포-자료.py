#!/usr/bin/env python3
"""9강 학생 배포 자료를 만든다 (2026-11-14).

09-세종회귀진단.py 의 load() 로 거른 15,486건에서 회귀에 쓰는 열만 남겨,
학생이 가공 없이 곧바로 분석 프롬프트부터 넣을 수 있게 한다. 계약년월 · 계약일 순으로 정렬한다
(더빈-왓슨을 시간순으로 읽기 위해).
실행: ~/.venvs/osmnx/bin/python 09-학생배포-자료.py
"""
import importlib.util, pathlib
HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('base', HERE / '09-세종회귀진단.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
d, _ = base.load()
d = d.sort_values(['계약년월', '계약일']).reset_index(drop=True)
out = d[['complex', '계약년월', '계약일', 'per', 'new', 'age', 'area', 'floor', 't', 'high']].copy()
out['per'] = out['per'].round(2)
dst = HERE.parent / 'data' / '학생배포' / '09강-세종아파트회귀'
dst.mkdir(parents=True, exist_ok=True)
out.to_csv(dst / '세종_아파트_회귀자료.csv', index=False, encoding='utf-8-sig')
print(len(out), dst)
