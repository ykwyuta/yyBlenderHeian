#!/bin/bash
# 軸線動画の分割レンダリング（24フレームずつ、完了済みチャンクはスキップ）
# チャンクを小さくして、VM入れ替え時の再描画ロスを抑える
cd ~/workspace/heiankyo-blender || exit 1
OUT=output/axis_anim
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
  blender --background heian_daidairi_axis_anim.blend \
    --render-output "$OUT/frame_" --render-format PNG \
    -s "$start" -e "$end" --render-anim 2>&1 | grep -E "Saved:" | tail -2
done
echo "ALL_CHUNKS_DONE $(ls $OUT/frame_*.png | wc -l) frames"
