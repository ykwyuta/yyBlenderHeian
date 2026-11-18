#!/bin/bash
# 軸線動画の分割レンダリング（48フレームずつ、完了済みチャンクはスキップ）
cd ~/workspace/heiankyo-blender || exit 1
OUT=output/axis_anim
mkdir -p "$OUT"
for start in 1 49 97 145 193 241; do
  end=$((start + 47))
  last=$(printf "%s/frame_%04d.png" "$OUT" "$end")
  if [ -f "$last" ]; then
    echo "SKIP chunk $start-$end"
    continue
  fi
  echo "RENDER chunk $start-$end $(date +%H:%M:%S)"
  blender --background heian_daidairi_axis_anim.blend \
    --render-output "$OUT/frame_" --render-format PNG \
    -s "$start" -e "$end" --render-anim 2>&1 | grep -E "Saved:" | tail -2
done
echo "ALL_CHUNKS_DONE $(ls $OUT/frame_*.png | wc -l) frames"
