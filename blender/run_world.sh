#!/usr/bin/env bash
# Renders the 360 world (panoramas, close-ups, click masks, depth) on a Linux GPU pod.
#   bash run_world.sh [samples] [pano_width]
#   EXTRA="--time night --views D0,R0 --nomask 1" NAME=night_out bash run_world.sh 512 6144   (night panoramas only)
# Expects world_job.zip unpacked next to this script (akb/...). Output: /workspace/world_out.tar.gz
set -euo pipefail
cd "$(dirname "$0")"
SAMPLES="${1:-512}"
PANO="${2:-6144}"
BL=/workspace/blender-5.2.3-linux-x64/blender
if [ ! -x "$BL" ]; then
  (cd /workspace && wget -q https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz && tar -xf blender-5.2.3-linux-x64.tar.xz)
  apt-get update -qq && apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 >/dev/null
fi
WORK="$(pwd)/akb"
OUT="$(pwd)/out"
mkdir -p "$OUT" "$WORK/renders"
start=$(date +%s)
"$BL" -b --factory-startup -P "$WORK/scripts/pitch_frames.py" -- --work "$WORK" --cover "$WORK/refs/cover_flowering.jpg" \
  --out "$OUT" --samples "$SAMPLES" --w 1920 --h 1080 --world 1 --pano "$PANO" ${EXTRA:-} 2>&1 | tee render.log | grep -E "DEVICE|NIGHT|WROTE|MASK|DEPTH|WORLD DONE|Error|Traceback"
echo "RENDER_SECONDS $(( $(date +%s) - start ))"
NAME="${NAME:-world_out}"
tar -czf "/workspace/$NAME.tar.gz" -C "$OUT/world" .
ls -la "/workspace/$NAME.tar.gz"
# safety net: stop the pod (GPU billing ends; /workspace is kept) after KEEP_MIN minutes for downloading
KEEP_MIN="${KEEP_MIN:-20}"
if command -v runpodctl >/dev/null 2>&1 && [ -n "${RUNPOD_POD_ID:-}" ]; then
  echo "AUTO-STOP in ${KEEP_MIN} min — download /workspace/$NAME.tar.gz before then (KEEP_MIN=0 to disable)"
  if [ "$KEEP_MIN" != "0" ]; then nohup bash -c "sleep $((KEEP_MIN * 60)); runpodctl stop pod $RUNPOD_POD_ID" >/dev/null 2>&1 & fi
fi
