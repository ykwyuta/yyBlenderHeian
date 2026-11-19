#!/bin/bash
# 軸線動画の分割レンダリング（24フレームずつ、完了済みチャンクはスキップ）
# チャンクを小さくして、中断時の再描画ロスを抑える
# 前提: setup_axis_animation.py で <WORK>/heian_daidairi_axis_anim.blend を作成済み
# 環境変数: HEIAN_WORK（既定 <リポジトリ>/output）、BLENDER（既定 blender）、HEIAN_DEVICE（既定 OPTIX）
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${HEIAN_WORK:-$REPO/output}"
BLENDER="${BLENDER:-blender}"
DEVICE="${HEIAN_DEVICE:-OPTIX}"   # GPU種別（CUDA / HIP / CPU など）
cd "$WORK" || exit 1
WORK="$(pwd)"
OUT="$WORK/axis_anim"   # 絶対パス（相対だと Blender が別の場所に書く）
mkdir -p "$OUT"
for start in 1 25 49 73 97 121 145 169 193 217 241 265; do
  end=$((start + 23))
  if [ "$end" -gt 288 ]; then end=288; fi
  last=$(printf "%s/frame_%04d.png" "$OUT" "$end")
  if [ -f "$last" ]; then
    echo "SKIP chunk $start-$end"
    continue
  fi
  echo "RENDER chunk $start-$end $(date +%H:%M:%S)"
  "$BLENDER" --background heian_daidairi_axis_anim.blend \
    --render-output "$OUT/frame_" --render-format PNG \
    -s "$start" -e "$end" --render-anim -- --cycles-device "$DEVICE" 2>&1 | grep -E "Saved:" | tail -2
done
echo "ALL_CHUNKS_DONE $(ls $OUT/frame_*.png | wc -l) frames"
