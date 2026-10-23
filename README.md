# Blue Room 360

하늘색 방을 360°로 둘러보며 음악·영상·공연·연락처·스토어로 이동하는 인터랙티브 아티스트 사이트 프로토타입입니다.
balmingtiger.com의 구조(360° 방 + 클릭 가능한 오브젝트 + 유리 패널)를 참고했고, 에셋과 콘텐츠는 모두 새로 만든 샘플입니다.

## 기능

- 로딩 → `CLICK TO ENTER` → 넓은 시야에서 방 안으로 들어가는 인트로
- 드래그로 360° 둘러보기, 휠로 확대/축소
- 오브젝트 클릭 시 카메라 이동 + 메뉴 패널
  - 턴테이블 → MUSIC / TV → VIDEO (방 안 TV에서 재생) / 티켓 → TOUR / 전화기 → CONTACT / 쇼핑백 → SHOP
- 이스터에그: 스탠드 조명(밤 모드), 지구본(랜덤 여행지), 쿠션
- 루프형 상단 메뉴, 모바일에서는 하단 메뉴 + 바텀시트
- Web Audio로 만든 배경음악·효과음, 음소거 버튼

## 기술

- 단일 `index.html` (빌드 과정 없음)
- [Three.js r128](https://threejs.org/) — 3D 방, 툰 셰이딩, 외곽선
- [GSAP 3](https://gsap.com/) — 카메라·UI 애니메이션
- 폰트: Bagel Fat One, IBM Plex Sans KR, IBM Plex Mono (Google Fonts)

## 로컬에서 보기

```bash
python -m http.server 8000
```

브라우저에서 http://localhost:8000 을 엽니다.

## 콘텐츠 바꾸기

`index.html` 안의 `DATA` 객체(앨범, 영상, 투어, 연락처, 상품)를 수정하면 됩니다.
