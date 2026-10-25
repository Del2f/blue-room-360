# Blue Room 360 / 소문의 낙원 360

인터랙티브 360° 아티스트 사이트 실험 저장소입니다. 지금 중심 작업은 AKMU 「소문의 낙원」 콘셉트 시안이며, 처음 만든 하늘색 방 프로토타입(Blue Room)도 그대로 남아 있습니다.

> 이 저장소는 공개 상태이고, 시안 사이트에는 권리 검토가 끝나지 않은 AKMU 공식 이미지가 들어 있습니다. 외부 공유 전 아래 [권리와 크레딧](#권리와-크레딧)을 확인하세요.

## 라이브 시안

- **소문의 낙원 360:** https://del2f.github.io/blue-room-360/
  - `gh-pages` 브랜치에서 GitHub Pages로 배포합니다.
  - 검색엔진에는 잡히지 않게(`noindex`) 설정했고, 링크를 공유하면 무대 장면 썸네일이 미리보기로 뜹니다.
  - 주소를 아는 사람은 누구나 볼 수 있습니다(비공개 장치는 아님).

## 소문의 낙원 360 (`akmu-pitch/pano/world/`)

MV와 무이네(Mũi Né) 사진을 바탕으로 Blender로 만든 360° 장면 두 곳을 둘러보는 사이트입니다.

- **낙원:** 무대 언덕 위 초원, 호수와 작은 만, 황금빛 덤불, 무대 뒤 큰 흰 사구, 지평선의 풍력발전기, 맑은 골든아워 하늘
- **방:** 축음기·TV·액자·침대가 있는 방. 창밖으로 낙원의 사구와 덤불이 보입니다
- 물건에 마우스를 올리면 테두리가 켜지고, 누르면 4K 클로즈업과 콘텐츠 카드(공연, M/V, 앨범, 소문, 굿즈, 플레이리스트, 편지)가 열립니다
- '언덕 위의 문'과 방의 '창문'으로 두 장소를 오갑니다
- 애플 스타일 UI: Liquid Glass 패널, 다이내믹 아일랜드, 나침반, 장소 목록, 커서, 스크롤 인트로
- 브라우저 움직임: 호수 물결과 반짝임, 풀 흔들림, 떠다니는 먼지, 합성 앰비언스(바람·물·방 소리)
- 폰트: Pretendard, Special Elite / 라이브러리: three.js 0.170 (CDN)

### 파일

| 파일 | 내용 |
|---|---|
| `index.html` | 사이트 전체 (빌드 없음). 콘텐츠는 `CONTENT` 객체, 캐시 태그는 `const V` |
| `D0.jpg`, `R0.jpg` | 낙원·방 360 파노라마 4096×2048 (데스크톱) |
| `D0_3k.jpg`, `R0_3k.jpg` | 3072×1536 경량본 (먼저 로드, 모바일) |
| `D0_mask.png`, `R0_mask.png`, `ids.json` | 클릭 영역 색 마스크와 색 ↔ 물건 표 |
| `D0_depth.png`, `R0_depth.png` | 16비트 깊이 맵 (풀 흔들림 등 효과용) |
| `D_*.jpg`, `R_*.jpg` | 물건별 클로즈업 1920×1080 |
| `og.jpg` | 공유 미리보기 1200×630 |

공식 참고 이미지는 `akmu-pitch/refs/official/`에서 읽습니다.

### 로컬에서 보기

저장소 루트에서:

```bash
python -m http.server 8766
```

http://localhost:8766/akmu-pitch/pano/world/ 를 엽니다.

## 장면 만들기 (Blender)

Blender 5.2 Cycles(OptiX, RTX 3080 기준)로 렌더합니다. 장면은 모두 코드로 만들어지고, 배치는 `layout.json`이 덮어씁니다.

| 파일 | 역할 |
|---|---|
| `blender/pitch_frames.py` | 장면 생성·렌더 (낙원, 방, 클로즈업, 마스크, 깊이 맵) |
| `blender/terrain.py` | 지형 (초원, 무대 언덕, 호수와 작은 만, 섬, 사구, 둔덕, 바다), 식생 마스크, 나무 군락. 순수 numpy라 렌더와 Blender 패널이 같은 땅을 씁니다 |
| `blender/layout.json` | 배치의 기준 파일: 시점, 하늘, 안개, 지형·나무·풀 밀도, 물건 이동 |
| `blender/layout_tools.py` | Blender 사이드바 패널 'N > 낙원 배치' (슬라이더, 손잡이, 저장, 실시간 연결) |
| `blender/open_layout.cmd` | 배치용 `.blend`를 패널과 함께 엽니다 |

### 렌더 명령

```bash
blender -b --factory-startup -P blender/pitch_frames.py -- --work %TEMP%\akb --cover akmu-pitch/refs/official/cover_flowering.jpg --out <출력 폴더> --samples 512 --w 1920 --h 1080 --world 1 --pano 4096
```

- `--views D0,D_boat` 처럼 일부만 렌더할 수 있습니다. `--nomask 1`은 마스크·깊이 맵을 건너뜁니다.
- `--layout <파일>`로 다른 배치를 쓰고, `--layout-blend <파일.blend>`는 렌더 대신 배치용 `.blend`를 만듭니다.
- 결과는 `<출력 폴더>/world/`에 생깁니다. 3K 경량본을 만든 뒤 `akmu-pitch/pano/world/`로 복사하고 `index.html`의 `V`를 올립니다.
- 4K 전체 세트(파노라마 2장, 클로즈업 17장, 마스크, 깊이 맵)는 약 35분, 최대 메모리 약 14GB입니다.

에셋(Poly Haven CC0 텍스처·모델·HDRI, Sketchfab CC BY 모델)은 `%TEMP%\akb\assets`에 두고 씁니다. 저장소에는 들어 있지 않습니다. 다운로드 스크립트(`ph_dl.py`)도 `%TEMP%\akb\tools`에만 있으니, 다른 PC에서 재현하려면 이 폴더를 함께 옮겨야 합니다.

### Blender 협업 (배치 먼저, 렌더는 마지막)

1. `blender/open_layout.cmd`로 `%TEMP%\akb\layout\paradise_layout_v3.blend`를 엽니다.
2. 사이드바 '낙원 배치'에서 물건을 옮기거나(G/R), 호수·작은 만·무대 언덕·캠프 모래·바다 슬라이더와 사구·나무 군락 손잡이를 조정합니다.
3. '배치 저장'을 누르면 `layout.json`에 저장되고, 다음 렌더가 그대로 따릅니다.
4. 실시간 연결: `blender/live/inbox/`에 넣은 명령을 열린 Blender가 실행하고, 결과와 화면 캡처를 `blender/live/outbox/`에 돌려줍니다. Claude와 대화로 함께 수정할 때 씁니다.

장면 코드가 바뀌면 `.blend`를 다시 만듭니다 (`--layout-blend`, 명령은 `open_layout.cmd` 주석 참고).

### 최적화

- **풀 패치:** 풀 77포기를 미리 한 메시로 합친 '패치' 4종을 뿌립니다. Cycles 인스턴스는 개당 약 10KB가 들어서, 이것만으로 최대 메모리 24.5GB → 9.6GB, 2K 미리보기 93초 → 53초로 줄었습니다.
- **거리별 밀도:** 멀수록 개수를 줄이고 남은 풀을 키워 덮이는 면적은 유지합니다 (게임 LOD 방식).
- **하늘:** 맑은 HDRI(syferfontein)로 조명하고, 카메라에 보이는 하늘만 MV 색(밝은 청록)으로 보정합니다. 해 주변은 보정하지 않아 번짐을 막습니다.
- **기타:**
  - 안개는 낮은 균일 볼륨 한 겹으로 둡니다.
  - 쓰지 않는 8K 하늘은 필요할 때만 불러옵니다.
  - 라이트 트리와 GPU OIDN(알베도·노멀 입력)을 씁니다.
  - 렌더 로그에 단계별 메모리(`RAM ...`)가 찍힙니다.

## 배포

`gh-pages` 브랜치에는 사이트에 필요한 파일만 들어 있습니다: `akmu-pitch/pano/world/`, `akmu-pitch/refs/official/`, `akmu-pitch/CREDITS.md`, 그리고 사이트로 넘기는 루트 `index.html`과 `.nojekyll`. 갱신하려면 바뀐 파일을 이 구성 그대로 복사해 `gh-pages`에 커밋·푸시합니다. 보통 1~2분 안에 반영됩니다.

## 권리와 크레딧

- 에셋 출처와 라이선스: [`akmu-pitch/CREDITS.md`](akmu-pitch/CREDITS.md). 사이트 오른쪽 아래 '에셋 크레딧' 링크로도 열립니다.
- Sketchfab 모델 4개(드럼 세트, 1970 픽업트럭, 마이크 스탠드, 어쿠스틱 기타)는 CC BY 4.0이라 출처 표시가 필요합니다.
- AKMU 공식 이미지(앨범 커버, 공연 사진, MV 스틸)와 M/V 임베드는 권리 검토가 보류된 상태로 공개 시안에 들어 있습니다.

## 그 밖의 폴더

| 폴더 | 내용 |
|---|---|
| `index.html` (루트) | 첫 프로토타입 Blue Room: 하늘색 방 360°, 툰 셰이딩(three.js r128, GSAP 3). 콘텐츠는 `DATA` 객체 |
| `akmu-concept/` | 소문의 낙원 초기 콘셉트 시안 (v2, v3) |
| `akmu-pitch/frames/`, `site/`, `world/` | 이전 스타일 프레임과 이전 버전 사이트 |
| `akmu-pitch/viewer3d/` | 실시간 3D 뷰어 실험 |
| `akmu-pitch/runpod/` | 클라우드 GPU 렌더 패키지 ([README](akmu-pitch/runpod/README.md)) |
| `akmu-pitch/license-review/` | 에셋 라이선스 검토 자료 |
| `akmu-pitch/IMPROVEMENT_PLAN.md` | 이전 개선안 (2026-10-25, 강·구름 장면 기준) |

## 다음 후보

- 휴대폰을 기울여 둘러보기, 자동 회전 중 클릭 보완, 이미지 WebP 경량화
- 문 ↔ 방 전환 연출
- 황금 덤불·사구 색·풀 밀도를 MV에 더 가깝게, 노을 버전 추가
