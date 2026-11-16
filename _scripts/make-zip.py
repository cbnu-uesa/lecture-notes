#!/usr/bin/env python3
"""학생 배포용 zip 을 만든다 — 윈도우 · LMS 업로드에서 한글 파일명이 깨지지 않게.

맥의 Finder 「압축」이나 zip 명령은 한글 파일명을 UTF-8 표시(플래그) 없이 넣고,
이름을 자모 분리형(NFD)으로 넣으며, __MACOSX · .DS_Store 를 끼워 넣는다.
윈도우와 업로드 사이트는 이를 CP949 로 읽어 이름이 깨지거나 압축 해제에 실패한다 (2026-11-14 확인).
이 스크립트는 이름을 NFC 로 바꾸고 UTF-8 플래그를 켜며 숨김 파일을 뺀다.

사용: python3 _scripts/make-zip.py <폴더> [<폴더> …]   → 폴더 옆에 같은 이름의 .zip
"""
import sys, os, zipfile, unicodedata, pathlib

def make(folder):
    src = pathlib.Path(folder).resolve()
    dst = src.with_name(src.name + '.zip')
    base = unicodedata.normalize('NFC', src.name)
    n = 0
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d != '__MACOSX')
            for f in sorted(files):
                if f.startswith('.'):
                    continue
                p = pathlib.Path(root) / f
                rel = unicodedata.normalize('NFC', str(p.relative_to(src)))
                zi = zipfile.ZipInfo.from_file(p, f'{base}/{rel}')
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.flag_bits |= 0x800                      # 파일명이 UTF-8 임을 표시
                with open(p, 'rb') as fh:
                    z.writestr(zi, fh.read())
                n += 1
    print(f'{unicodedata.normalize("NFC", dst.name)}: {n}개 파일')

for a in sys.argv[1:]:
    make(a)
