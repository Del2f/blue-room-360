# 클라우드 GPU로 Blender 최종 렌더하기

시안은 집 PC(RTX 3080)로 충분하지만, 최종본(4K 영상, 8K 큐브맵, 1000샘플 이상)은 렌더 시간이 수십 시간 단위가 됩니다. 이럴 때는 GPU를 시간 단위로 빌립니다.

> 가격은 2026년 중반 기준의 대략적인 범위입니다. 자주 바뀌니 결제 전에 각 사이트에서 꼭 확인하세요.

## 1. 어떤 방식을 고를까

| 방식 | 서비스 | 장점 | 단점 | 대략 비용 |
|---|---|---|---|---|
| **렌더팜** (파일만 올리면 끝) | RebusFarm, GarageFarm, Fox Renderfarm | 수십 대가 동시에 렌더. Blender 플러그인으로 업로드. 서버 관리 불필요 | 1프레임 단가가 GPU 직접 대여보다 비쌈. 커스텀 스크립트 제약 | 영상 1편(240프레임) 수만~수십만 원 |
| **무료 커뮤니티 팜** | SheepIt | 무료(내 PC도 남의 렌더를 돌려주며 포인트 적립) | 대기열이 있고 느림. 파일 크기와 렌더 시간 제한. 미공개 작업물엔 부적합 | 0원 |
| **GPU 서버 직접 대여** | RunPod, Vast.ai, Lambda, Paperspace | 가장 저렴. 우리 Python 렌더 스크립트를 그대로 실행 | 리눅스 터미널 조작 필요. 끄는 걸 잊으면 계속 과금 | RTX 4090 시간당 약 $0.35–0.8, A100/H100 $1.5–3 |

**추천: RunPod 또는 Vast.ai의 RTX 4090 1~4대.** 이 프로젝트는 장면을 Python 스크립트(`blender/pitch_frames.py`, `render.py`)로 만들기 때문에, 서버에서 같은 명령을 그대로 실행할 수 있습니다. 4090 한 대는 3080보다 대략 2~2.5배 빠릅니다.

> 미공개 아티스트 작업물이라면 SheepIt처럼 남의 PC에서 렌더되는 곳은 피하고, 단독 서버(RunPod/Vast의 Secure Cloud 등)나 계약서가 있는 상용 렌더팜을 쓰세요.

## 2. 비용 감 잡기

| 작업 | 크기 | 4090 1대 예상 | 비용(시간당 $0.6 가정) |
|---|---|---|---|
| 스타일 프레임 6장 | 1080p · 256샘플 | 5분 미만 | 1천 원 미만 |
| 히어로 루프 영상 | 4K · 10초(240프레임) · 1024샘플 | 12–24시간 | 약 1만–2만 원 |
| 방 360° 큐브맵 | 8K × 6면 · 2048샘플 | 2–4시간 | 약 2–3천 원 |
| 문 통과 컷 | 4K · 4초(96프레임) | 5–10시간 | 약 5천–1만 원 |

4대를 빌리면 시간은 1/4로 줄고 총비용은 거의 같습니다. 정확한 수치는 아래 4단계의 "테스트 1프레임"으로 먼저 재보세요.

## 3. 준비 (내 PC에서)

1. 외부 파일을 .blend 안에 묶습니다. 스크립트가 만든 `pitch.blend`를 열고 실행:
   ```
   blender -b pitch.blend --python-expr "import bpy; bpy.ops.file.pack_all(); bpy.ops.wm.save_mainfile()"
   ```
   또는 스크립트 방식 그대로 가져가려면 `akb` 작업 폴더 전체(assets, scripts, fonts)를 zip으로 압축합니다.
2. 파일 크기 확인: 큰 나무 모델 때문에 1–2GB가 될 수 있습니다. 업로드에 시간이 걸리니 미리 압축해 두세요.

## 4. RunPod 기준 단계별

1. **가입·충전**: runpod.io에서 가입 후 크레딧을 $10–20 정도 충전합니다(결제는 직접 하세요).
2. **Pod 만들기**: Pods → Deploy → GPU에서 *RTX 4090* 선택 → 템플릿 *RunPod PyTorch*(우분투 + CUDA 포함) → 디스크 50GB → Deploy.
3. **접속**: 만들어진 Pod의 *Connect* → *Start Web Terminal* (또는 SSH).
4. **Blender 설치** (터미널에 붙여넣기):
   ```
   cd /workspace
   wget https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz
   tar -xf blender-5.2.3-linux-x64.tar.xz
   apt-get update && apt-get install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6
   ```
   (정확한 파일명은 download.blender.org/release 에서 확인)
5. **파일 올리기**: Pod 화면의 *Jupyter* 파일 브라우저로 드래그해 올리거나, 터미널에서 `runpodctl send/receive`, 또는 Google Drive 공유 링크를 `gdown`으로 받습니다.
6. **테스트 1프레임**으로 시간 재기:
   ```
   ./blender-5.2.3-linux-x64/blender -b --factory-startup -P akb/scripts/pitch_frames.py -- --work /workspace/akb --cover /workspace/akb/cover_flowering.jpg --out /workspace/out --frames F1 --samples 1024 --w 3840 --h 2160
   ```
   스크립트는 OptiX(RTX)를 자동으로 선택합니다. 나온 시간 × 프레임 수 = 전체 예상 시간.
7. **본 렌더**: 같은 명령을 `nohup ... &` 로 실행하면 브라우저를 닫아도 계속 돕니다. 영상은 `render.py --mode video`, 큐브맵은 `--mode faces`.
8. **결과 받기**: `out` 폴더를 zip으로 묶어 Jupyter에서 다운로드합니다.
9. **반드시 종료**: Pod를 *Stop*하면 GPU 과금은 멈추지만 디스크 비용은 남습니다. 다 받았으면 *Terminate*로 완전히 삭제하세요.

Vast.ai도 거의 같습니다. 차이점은 개인이 내놓은 서버를 경매식으로 빌리는 구조라 더 싸지만, 서버마다 안정성이 다르니 *Verified* 표시와 신뢰도 99% 이상인 곳을 고르세요.

## 5. 렌더팜(RebusFarm 등)을 쓸 때

1. 가입 후 전용 업로더(Blender 애드온)를 설치합니다.
2. 3단계처럼 텍스처를 모두 pack한 `.blend`를 엽니다.
3. 애드온에서 렌더 설정(Cycles, GPU, 프레임 범위, 해상도)을 확인하고 *Upload & Render*.
4. 가격 견적이 먼저 뜹니다. 확인 후 진행하면 끝난 프레임이 자동으로 내려받아집니다.

주의: 렌더팜은 우리 Python 스크립트를 직접 실행하지 않으므로, 꼭 **완성된 `.blend`**(애니메이션까지 키프레임으로 저장된 것)를 올려야 합니다.

## 6. 돈 아끼는 요령

- 최종 전에 **1/4 해상도 · 낮은 샘플**로 전 구간을 미리 렌더해 카메라·타이밍을 확정합니다(집 PC로 충분).
- Cycles **Adaptive Sampling + OIDN 디노이즈**를 켜면 샘플을 절반 이하로 줄여도 깨끗합니다(스크립트에 이미 켜져 있음).
- 영상은 **EXR 이미지 시퀀스**로 렌더합니다. 중간에 끊겨도 이어서 렌더할 수 있고, 후반 그레이딩 여유도 큽니다.
- 서버를 켜 둔 채 잠들지 않도록, 렌더 명령 뒤에 `&& runpodctl stop pod $RUNPOD_POD_ID`를 붙이면 끝나는 즉시 자동으로 멈춥니다.
