# RunPod F1 단일 프레임 벤치마크 패키지

현재 완성된 F1 낙원 장면 하나를 리눅스 GPU 서버에서 렌더해 속도를 재기 위한 최소 패키지입니다. 인물은 들어 있지 않습니다. 준비일: 2026-10-25.

## 패키지 (`package/`)

| 파일 | 크기 | SHA-256 |
|---|---|---|
| `f1_paradise.blend` | 415,259,962 bytes (약 396 MB, 압축 저장) | `176CA4417A1E074BBA5DDEC8C089EB96260ACBB9F183EC3C1FC986EC69EDE623` |
| `render_f1.py` | 2 KB | `E0224AE21C872F458A20496C44DAA703A4CD7D86EB1DD2B2CA83E28565EB39C9` |

- **자체 완결:** 텍스처·HDRI가 모두 `.blend` 안에 들어 있습니다(외부 경로 0개). 경로 문제 없이 리눅스에서 바로 열립니다.
- **들어 있는 것:**
  - `PARADISE` 장면(F1 카메라, 낮 하늘, 하늘 사진에 맞춘 햇빛)
  - 식생 산포가 참조하는 원본(`LIB` 장면)
- **빠진 것:** 방 장면, 공식 이미지 파일, `.git`, 인증정보, 렌더 결과물. F1에는 앨범 커버가 나오지 않아 포함하지 않았습니다.
- **git:** `.blend`는 용량 때문에 git에서 제외합니다(`package/.gitignore`). 이 폴더에서 직접 업로드하세요.
- **필름 톤 후처리 없음:** 할레이션·그레인 같은 후처리는 이 벤치마크에 들어 있지 않습니다. 순수 Cycles 렌더 시간만 잽니다. PNG는 16비트로 저장합니다.

## 버전

- Blender **5.2.3 LTS** (빌드 해시 e13b728c6880). 패키지를 만든 버전과 같습니다.
- 리눅스 배포본: https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz
  - 크기 385,331,224 bytes. 2026-10-25에 다운로드 가능 확인
- 렌더러: Cycles. OptiX를 먼저 시도하고, 안 되면 CUDA로 자동 전환합니다. CPU는 `--device CPU`로 지정할 때만 씁니다.

## 실행 명령 (Pod 터미널)

```
cd /workspace
wget -q https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz
tar -xf blender-5.2.3-linux-x64.tar.xz
apt-get update && apt-get install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6
mkdir -p /workspace/akmu   # 여기에 package/ 의 두 파일을 업로드
cd /workspace/akmu
sha256sum f1_paradise.blend render_f1.py   # 위 표와 비교
B=/workspace/blender-5.2.3-linux-x64/blender
```

1. **점검용 미니 렌더** (몇십 초): 장치 인식과 텍스처 누락을 확인합니다.
   ```
   $B -b f1_paradise.blend -P render_f1.py -- --out out/F1_check.png --samples 16 --w 480 --h 270
   ```
   로그에서 `DEVICES OPTIX [...]` 또는 `DEVICES CUDA [...]`와 `RENDER_SECONDS`를 확인합니다.
2. **벤치마크** (시안과 같은 조건):
   ```
   $B -b f1_paradise.blend -P render_f1.py -- --out out/F1_1080p_256.png --samples 256 --w 1920 --h 1080
   ```
3. (선택) **최종본 비용 추정용**:
   ```
   $B -b f1_paradise.blend -P render_f1.py -- --out out/F1_4k_512.png --samples 512 --w 3840 --h 2160
   ```

**OptiX가 안 잡힐 때:** 로그에 `DEVICE OPTIX unavailable`이 나오면 스크립트가 CUDA로 자동 전환합니다. OptiX를 꼭 써야 하면 Pod 템플릿 환경변수에 `NVIDIA_DRIVER_CAPABILITIES=all`을 넣어 볼 수 있습니다(템플릿마다 다름, 미검증).

## 저장공간 예상

| 항목 | 크기 |
|---|---|
| Blender 압축본 + 압축 해제본 | 약 0.4 GB + 약 1.2 GB |
| 패키지 | 약 0.4 GB |
| 렌더 결과 (PNG 16비트) | 1080p 약 10 MB, 4K 약 40 MB |
| 렌더 중 메모리 | 장면 로드 시 GPU VRAM 수 GB 예상(미측정). 24 GB급이면 충분 |

컨테이너 디스크 **10 GB**면 여유가 있습니다.

## 로컬 기준값 (비교용)

| 환경 | 조건 | 시간 |
|---|---|---|
| RTX 3080 (Windows), 동일 패키지 | 480×270, 16샘플 | 16.4초 (장면 로드 포함, 2026-10-25 실측) |
| RTX 3080, 원본 스크립트 최종 렌더 | 1920×1080, 256샘플 | 약 35초 |

로컬 1080p 렌더가 약 35초이므로, 정지 프레임 한 장은 클라우드가 꼭 필요하지 않습니다. 이 벤치마크는 4K 영상·큐브맵처럼 프레임이 많은 작업의 비용을 추정하는 데 쓰세요.

## 다시 만드는 방법

장면을 수정한 뒤 패키지를 다시 만들려면 아래 순서를 따릅니다(`<work>`는 로컬 Blender 작업 폴더).
1. 장면만 만들고 렌더하지 않은 채 `<work>/pitch.blend`로 저장합니다.
   ```
   blender -b --factory-startup -P blender/pitch_frames.py -- --work <work> --cover <cover.jpg> --out <tmp> --save 1 --frames NONE
   ```
2. F1만 남기고 모든 파일을 묶어 패키지로 저장합니다(`--out`에는 `package/f1_paradise.blend` 경로를 지정).
   ```
   blender -b <work>/pitch.blend -P blender/runpod_pack.py -- --out akmu-pitch/runpod/package/f1_paradise.blend
   ```
