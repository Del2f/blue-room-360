# 소문의 낙원 360

AKMU 「소문의 낙원」(Paradise of Rumors) 360° 인터랙티브 콘셉트 시안 저장소입니다.

> 이 저장소는 공개 상태이고, 시안 사이트에는 권리 검토가 끝나지 않은 AKMU 공식 이미지가 들어 있습니다. 외부 공유 전 아래 [권리와 크레딧](#권리와-크레딧)을 확인하세요.

## 라이브 시안

- **소문의 낙원 360:** https://del2f.github.io/blue-room-360/akmu-pitch/pano/world/
  - 첫 주소 https://del2f.github.io/blue-room-360/ 도 같은 사이트로 넘어갑니다.
  - `gh-pages` 브랜치에서 GitHub Pages로 배포합니다. `main`과 같은 사이트 파일을 씁니다.
  - 검색엔진에는 잡히지 않게(`noindex`) 설정했고, 링크를 공유하면 무대 장면 썸네일이 미리보기로 뜹니다.
  - 주소를 아는 사람은 누구나 볼 수 있습니다(비공개 장치는 아님).

## 소문의 낙원 360 (`akmu-pitch/pano/world/`)

MV와 무이네(Mũi Né) 사진을 바탕으로 Blender로 만든 360° 장면 두 곳을 둘러보는 사이트입니다.

- **낙원:** 무대 언덕 위 초원, 호수와 작은 만(배·피크닉), 황금빛 덤불, 무대 뒤 큰 흰 사구, 지평선의 풍력발전기, 맑은 골든아워 하늘
- **방:** 축음기·TV·액자·침대가 있는 방. 창밖으로 낙원의 사구와 덤불이 보입니다
- 물건에 마우스를 올리면 라벨이 켜지고, 누르면 4K 클로즈업과 콘텐츠 카드(공연, M/V, 앨범, 소문, 굿즈, 플레이리스트, 편지)가 열립니다
- '언덕 위의 문'과 방의 '창문'으로 두 장소를 오갑니다
- **창가의 체스:** 방의 '체스판'을 누르면 방의 체스 세트로 '방의 주인'(컴퓨터)과 둘 수 있습니다. 쉬움·보통·어려움 3단계, 무르기, 새 판, 승진 선택, 이어 두기(브라우저에 저장)
  - 방의 주인이 생각하는 동안 시계 소리가 납니다
  - 이기면 숨은 소문 쪽지와 '축음기로 가 보기'가 열립니다 (미공개 트랙·공연 힌트 자리)
- 「소문의 낙원」은 앨범 『개화 (FLOWERING)』의 선공개곡으로 표기합니다(PRE-RELEASE)
- 브라우저 움직임: 호수 물결과 반짝임, 풀 흔들림, 떠다니는 먼지, 합성 앰비언스(바람·물·방 소리)
- 라이브러리: three.js 0.170 (CDN), 빌드 과정 없음

### 지금 모습 (기본값)

- **UI:** 시안 7. 위쪽 방위 눈금자와 '각도 · 방위' 표시, 어두운 유리 알약 라벨에 금색 마름모. 장소 목록과 '낙원/방' 전환 버튼은 없습니다
- **폰트:** 영어 Special Elite, 한글 Gowun Batang(고운바탕)
- **입장:** 검은 로딩 화면 → 'AKMU — Paradise of Rumors · 360' → 소리와 함께/조용히 입장 → 하늘에서 내려오는 스크롤 인트로

### 시안 바꿔 보기 (주소 뒤에 붙이기)

| 주소 | 내용 | 비교 페이지 |
|---|---|---|
| `?ui=0` ~ `?ui=7` | UI 시안. 0 이전 모습, 1 ZERO RULER, 2 VIEWFINDER, 3 EDITORIAL, 4 RADAR, 5 TICKER, 6 시안 1 라벨 + 시안 2 방위 띠, 7 시안 6에서 상단 상태 표시를 뺀 기본값 | `ui-drafts/` |
| `?intro=1` ~ `?intro=4` | 입장 화면 시안. 1 작은 행성, 2 시네마스코프, 3 포스터, 4 지금 입장 화면을 넓힌 버전. 없으면 지금 입장 화면 | `intro-drafts/` |
| `?ko=<이름>` | 한글 폰트 미리보기 (`grandiflora`, `gowun-batang`, `hahmlet`, `song-myung`, `diphylleia`, `gaegu`, `gamja`, `nanum-pen`) | `fonts.html` |

여러 개를 함께 쓸 수 있습니다. 예: `?ui=3&intro=2&ko=hahmlet`

### 파일

| 파일 | 내용 |
|---|---|
| `index.html` | 사이트 전체. 콘텐츠는 `CONTENT` 객체, 이미지 캐시 태그는 `const V` |
| `ko-fonts.js` | `?ko=` 한글 폰트 목록 |
| `chess.js`, `chess-engine.js`, `chess-worker.js` | 체스 화면, 규칙과 컴퓨터 상대(외부 라이브러리 없음, 생각은 Web Worker에서), 표준 perft 검증 통과 |
| `chess/` | 체스판과 말 이미지. 방의 체스 세트(Poly Haven `chess_set`)를 Blender로 렌더 (`pitch/akmu-paradise-moodboard` 브랜치의 `blender/chess_sprites.py`) |
| `D0.webp`, `R0.webp` | 낙원·방 360 파노라마 4096×2048 (데스크톱) |
| `D0_3k.webp`, `R0_3k.webp` | 3072×1536 경량본 (먼저 로드, 모바일) |
| `D0_mask.png`, `R0_mask.png`, `ids.json` | 클릭 영역 색 마스크와 색 ↔ 물건 표 |
| `D0_depth.png`, `R0_depth.png` | 16비트 깊이 맵 (풀 흔들림 등 효과용) |
| `D_*.webp`, `R_*.webp` | 물건별 클로즈업 1920×1080 (낙원 8, 방 10) |
| `og.jpg` | 공유 미리보기 1200×630 (메신저 호환을 위해 JPEG 유지) |

사진 이미지는 모두 WebP입니다(같은 화질에서 JPEG의 약 1/3 크기). 클릭 마스크와 깊이 맵은 색과 값이 정확해야 해서 PNG로 둡니다.
| `ui-drafts/`, `intro-drafts/`, `fonts.html` | 시안 비교 페이지 |

공식 참고 이미지는 `akmu-pitch/refs/official/`에서 읽습니다.

### 로컬에서 보기

저장소 루트에서:

```bash
python -m http.server 8766
```

http://localhost:8766/akmu-pitch/pano/world/ 를 엽니다.

## 렌더와 Blender 작업

장면 렌더 코드와 Blender 협업 도구는 `main`이 아니라 **`pitch/akmu-paradise-moodboard`** 브랜치에 있습니다 (`blender/pitch_frames.py`, `terrain.py`, `layout_tools.py`, `layout.json`). 그 브랜치의 README에 렌더 명령, 배치 협업 방법, 최적화 내용이 정리돼 있습니다.

- Blender 5.2 Cycles로 렌더하고, 4K 전체 세트(파노라마 2장, 클로즈업 17장, 마스크, 깊이 맵)는 약 35분 걸립니다.
- 렌더가 바뀌면 결과를 `akmu-pitch/pano/world/`에 넣고 `index.html`의 `V`를 올려 브라우저 캐시를 갱신합니다.

## 배포

- `main`의 `akmu-pitch/`와 `gh-pages`의 사이트 파일은 같습니다. 사이트를 바꾸면 두 브랜치에 같은 파일을 반영합니다.
- `gh-pages`에는 사이트에 필요한 파일만 있습니다: `akmu-pitch/pano/world/`, `akmu-pitch/refs/official/`, `akmu-pitch/CREDITS.md`, 사이트로 넘기는 루트 `index.html`, `.nojekyll`.
- 푸시 후 보통 1~2분 안에 라이브에 반영됩니다. 주소는 바뀌지 않습니다.

## 권리와 크레딧

- 에셋 출처와 라이선스: [`akmu-pitch/CREDITS.md`](akmu-pitch/CREDITS.md). 사이트 오른쪽 아래 '에셋 크레딧' 링크로도 열립니다.
- Sketchfab 모델 4개(드럼 세트, 1970 픽업트럭, 마이크 스탠드, 어쿠스틱 기타)는 CC BY 4.0이라 출처 표시가 필요합니다.
- AKMU 공식 이미지(앨범 커버, 공연 사진, MV 스틸)와 M/V 임베드는 권리 검토가 보류된 상태로 공개 시안에 들어 있습니다.
- 폰트(Special Elite, Gowun Batang, `?ko=` 미리보기 폰트)는 모두 Google Fonts의 SIL OFL 폰트입니다.

## 그 밖의 폴더

| 폴더 | 내용 |
|---|---|
| `index.html` (루트) | 사이트(`akmu-pitch/pano/world/`)로 바로 넘기는 안내 페이지. 공유 미리보기와 `noindex` 포함 |
| `akmu-concept/` | 소문의 낙원 초기 콘셉트 시안 (v1, v2) |

## 다음 후보

- UI 시안·입장 화면 시안 중 최종안 확정
- 휴대폰을 기울여 둘러보기, 자동 회전 중 클릭 보완, 이미지 WebP 경량화
- 황금 덤불·사구 색·풀 밀도를 MV에 더 가깝게, 노을 버전 추가
