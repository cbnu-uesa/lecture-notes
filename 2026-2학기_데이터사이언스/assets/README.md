# assets — 이 과목 전용 이미지

파일 이름 앞머리로 출처와 취급 방법을 구분한다.

| 접두사 | 뜻 | 배포 |
|---|---|---|
| `cc-` | 외부에서 가져온 자유 라이선스 자료 | 가능. **슬라이드에 저작자·라이선스를 반드시 표기** |
| `tb-` | 교재 스캔에서 잘라 온 것 | 대외 배포 전 저작권 판단 대상 |
| (접두사 없음) | 직접 만든 것 | 자유 |

## 파일 목록

### cc-karpathy.png
- 인물: Andrej Karpathy
- 출처: Wikimedia Commons, `File:Andrej Karpathy, OpenAI (cropped).png`
- 저작자: Gladwin Analytics (원본은 2019-12-16 YouTube 영상)
- 라이선스: **CC BY 3.0** — 저작자 표시와 라이선스 링크가 필요하다
- 쓰는 곳: **2주차** (카파시의 램블링 방식 소개). 1주차에는 쓰지 않는다
- 크기: 240×320. 원본이 영상 캡처라 해상도가 낮다. 슬라이드에서 150px 높이 이하로만 쓴다

### cc-cheongju-oldtown.jpg
- 청주 원도심 야경. 앞쪽 저층 주택가는 어둡고 뒤쪽 신시가지는 밝다
- 출처: Wikimedia Commons, `File:Cheongju Old Town at Night.jpg`
- 저작자: Minseong Kim (Wikimedia 사용자 IMKSv), 2019-02-25 촬영
- 라이선스: **CC BY-SA 4.0** — 저작자 표시가 필요하다. 1강 2쪽 캡션과 출처 장에 적었다
- 원본 5184×3388 을 1200px 로 줄여 두었다 (Drive 용량)
- 쓰는 곳: 1강 2쪽 발문. 2주차 원도심 공동화 시연과도 이어진다

### cc-compas-list.png
- COMPAS 아이디어 공모전 목록 화면의 과제 카드 첫 줄
- 출처: compas.lh.or.kr/subj/competition/list · 2026-08-26 갈무리
- 만든 법: `check-figures.sh` 가 쓰는 헤드리스 크롬(puppeteer)으로 직접 캡처했다.
  좌측 내비게이션이 hover 로 펼쳐져 본문을 덮으므로 포인터를 본문으로 옮긴 뒤 찍는다
- 쓰는 곳: 1강 19쪽

**갈무리를 다시 만들려면** 아래를 쓴다 (스크립트는 임시 디렉터리에 만든다).
puppeteer 경로는 `find ~/.npm/_npx -maxdepth 4 -type d -name puppeteer` 로 찾는다.

## 인라인 SVG 로고 (파일 없음)

R · Python · Gemini · Claude 로고는 [Simple Icons](https://simpleicons.org) (CC0 1.0) 의
단색 경로를 1강 슬라이드 SVG 안에 직접 적어 넣었다. 파일을 늘리지 않으려는 것이다
(CLAUDE.md §2 — Drive 동기화 폴더라 파일 수를 억제한다).
색은 테마 토큰으로 준다 — 지난 도구는 `--muted`, 2026 은 `--brand-crimson`.

CC0 라 표시 의무는 없지만 1강 마지막 '자료 출처' 장에 적어 두었다.
상표권은 각 기업에 있으며, 제품을 가리키는 용도로만 쓴다.
