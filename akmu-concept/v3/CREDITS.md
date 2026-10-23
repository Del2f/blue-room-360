# v3 (Blender Cycles) 제작 메모와 출처

## 만드는 방법
장면은 `blender/` 폴더의 스크립트로 Blender 5.2에서 직접 만들고 렌더합니다.

| 스크립트 | 하는 일 |
|---|---|
| `blender/build_scenes.py` | 무이네 모래언덕과 이찬혁의 방을 코드로 구성해 `akmu.blend` 저장 |
| `blender/render.py` | 360° 큐브 면(4096px), 호버 마스크, 문 너머 이미지, 문 통과 영상 렌더 |
| `blender/render_all.ps1` | 위 과정을 순서대로 한 번에 실행 |
| `blender/package.py` | 렌더 결과를 WebP(4096/2048)로 바꿔 `v3/media/`에 정리 |

`akmu.blend`를 Blender에서 열면 장면을 직접 보고 고칠 수 있습니다. 씬은 `DUNES`, `ROOM` 두 개입니다.

## 에셋 출처
- 3D 모델·텍스처·HDRI: [Poly Haven](https://polyhaven.com), **CC0**
  - HDRI: qwantani_late_afternoon_puresky (4K)
  - 텍스처: red_sand, old_wooden_floor_01, painted_plaster_wall, blue_painted_planks, weathered_planks, rough_linen, wood_planks
  - 모델: wooden_table_02, painted_wooden_chair_01, desk_lamp_arm_01, tea_set_01, Television_01, wooden_crate_02, wooden_bookshelf_worn, book_encyclopedia_set_01, vintage_cabinet_01, vintage_day_bed, Rockingchair_01, potted_plant_02, hanging_picture_frame_01, round_wooden_table_01, flower_gazania, flower_ursinia, wild_rooibos_bush
- 렌더 속 글자 폰트: Pretendard (SIL Open Font License), Special Elite (Apache License 2.0)
- 코드로 직접 만든 것: 모래언덕 지형과 모래 재질, 문, 이정표, 축제 가판대, 텐트, 바구니 배(thúng chai), 타자기, 턴테이블, 러그 무늬, 벽·창문·천장 구조
