#!/usr/bin/env python3
"""macOS Vision 프레임워크로 스캔 쪽을 한국어 OCR — ocr.py <이미지> [<이미지>...]"""
import sys, Vision, Quartz
from Foundation import NSURL

def ocr(path):
    url = NSURL.fileURLWithPath_(path)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["ko-KR", "en-US"])
    req.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    handler.performRequests_error_([req], None)
    out = []
    for o in req.results() or []:
        t = o.topCandidates_(1)
        if t and len(t): out.append(str(t[0].string()))
    return "\n".join(out)

for p in sys.argv[1:]:
    print(f"===== {p} =====")
    print(ocr(p))
