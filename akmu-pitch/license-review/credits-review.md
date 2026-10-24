# Claude 통합용 크레딧 검토

확인일: 2026-10-25(KST). 담당: Codex. 메인 코드·렌더·사이트·기존 CREDITS는 수정하지 않음.

## 결과

`akb/assets`에서 HDRI 6개, 텍스처 18개, 모델 52개, 합계 76개를 확인했다. `blender/pitch_frames.py`의 문자열 리터럴과 대조하면 51개가 소스에 참조되고 25개는 보관만 확인된다. 이는 최종 프레임 안에서 모두 보인다는 뜻은 아니다. Poly Haven 공식 라이브 API의 `/assets` 응답에서 75개의 ID·저자를 대조했다. `sky_4k.hdr`는 원래 ID가 미확인이며 현재 소스에는 참조되지 않는다.

공식 메타데이터: https://api.polyhaven.com/assets — 2026-10-25 직접 조회. 본 목록의 메타데이터는 Poly Haven에서 제공했다. 개별 페이지 URL과 저자·로컬 이미지 해상도는 `asset-manifest.csv`에 있다. 취득일은 다운로드 영수증/기록을 확보하지 못해 전부 미확인이다. 파일 생성·수정일을 취득일로 간주하지 않았다.

## Claude가 반영할 수정

| 우선순위 | 발견 | 권장 반영 |
|---|---|---|
| 높음 | CREDITS의 ‘아래 에셋 모두 CC0’ 표현에 공식 이미지·폰트·향후 후보가 섞일 수 있음 | CC0 범위를 Poly Haven 표로 한정 |
| 보통 | `wood_planks` 누락 | 축음기 목재 재질. `blender/pitch_frames.py:1057`에 참조됨. Poly Haven 표에 추가 |
| 높음 | 앨범 커버가 레코드 라벨과 첫 LP 커버에 적용됨 | `pitch_frames.py:1079`, `:1088`. 공개 시 허락 또는 대체 이미지로 재렌더. refs 파일 삭제로 기존 JPG의 내용은 없어지지 않음 |
| 높음 | ‘내부 검토용’만으로 이용허락이 확보되지는 않음 | 내부 배포 범위·레퍼런스 목적을 관리하고 공개 전 별도 승인. `rights-checklist.md` 참조 |
| 보통 | 에셋의 저자·원문 링크가 생략됨 | 자율 CC0 크레딧 초안을 통합하거나 CSV를 제작 기록으로 보관 |
| 보통 | 다운로드 보관분이 모두 사용분처럼 보일 수 있음 | ‘소스 참조’와 ‘보관만 확인’을 유지. Sketchfab 후보는 실제 사용분에 합치지 않기 |
| 보통 | HDRI 현재 로컬본은 8K | 공식 카탈로그의 16K/24K 제공과 로컬 8K 사용을 구별. 확대 배경용 추가 다운로드는 Claude가 결정 |

## 웹 의존성 확인

`akmu-pitch/site/index.html`과 `akmu-pitch/index.html`에서 외부 폰트 CSS 두 가지를 확인했다. 외부 JS 라이브러리 로드는 해당 두 파일에서 발견되지 않았다. 프로젝트 전체 의존성 감사는 아니다.

| 구성요소 | 판정 및 납품 메모 | 공식 출처 / 확인일 |
|---|---|---|
| Pretendard 1.3.9 / jsDelivr | SIL OFL 1.1. 상업 웹 사용 가능. 폰트 파일을 묶어 납품·자체 호스팅하면 저작권·라이선스 고지 보존. 수정본 Reserved Font Name 조건 확인 | https://github.com/orioncactus/pretendard/blob/v1.3.9/LICENSE / 2026-10-25 |
| Special Elite / Google Fonts | Apache 2.0. 상업 사용 가능. 폰트 재배포 시 라이선스 사본 및 해당 고지 보존; 변경·NOTICE 조건 적용 여부 확인 | https://github.com/google/fonts/blob/main/apache/specialelite/LICENSE.txt / 2026-10-25 |
| Google Drive 썸네일 | 레퍼런스 페이지에 외부 링크가 있음. 사진 권리자·허용 범위 미확인. 링크 접근 가능 여부와 재사용 권리는 별개 | 로컬 `akmu-pitch/index.html:126–128,249` / 2026-10-25 |
| 플레이어 UI | 검사한 `site/index.html`에는 재생 아이콘 상태 전환이 있으나 실제 음원 URL·audio 요소는 발견되지 않음 | 로컬 `site/index.html:374` / 2026-10-25 |

## Poly Haven API 조건

에셋 자체는 CC0이며 상업 렌더·클라이언트 납품에 필수 크레딧이 없다. https://polyhaven.com/license (2026-10-25).

라이브 API로 콘텐츠를 제공하는 도구/서비스는 출처를 명확히 표시하고 고유 User-Agent 또는 Referer를 사용해야 한다. 이 조건을 이미 다운로드한 에셋의 렌더 결과물에 대한 의무로 확대해서는 안 된다. 기존 `akb/tools/ph_dl.py`는 `akmu-pitch/1.0` User-Agent와 Poly Haven 이름이 담긴 설명을 가진다. 향후 도구를 배포한다면 사용자에게 보이는 출처 고지를 유지한다. 공식 원문: https://github.com/Poly-Haven/Public-API/blob/master/ToS.md §2.4–2.5 (2026-10-25).

## 검증 범위

메인 스크립트와 `akb/scripts/pitch_frames.py` 실행 사본의 SHA-256은 감사 시점에 동일했다: `3a6169fe01d917105b22ff0bbd4f7d795cea95ab613605b484e4fb77f0398177`.
에셋 바이트를 공식 다운로드 해시와 전수 비교하거나 최종 렌더 가시성을 확인하지는 않았다. 소스 변경·추가 다운로드 시 목록을 다시 대조해야 한다. 본 자료는 법률 자문이 아니며 최종 공개 전 원문과 개별 허락 범위를 확인해야 한다.
