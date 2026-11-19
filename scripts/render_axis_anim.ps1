# 軸線動画の分割レンダリング（Windows PowerShell 版）
# 24フレームずつ描き、完了済みチャンクはスキップする（中断・再開に強い）
# 前提: setup_axis_animation.py で <WORK>\heian_daidairi_axis_anim.blend を作成済み
# 環境変数: HEIAN_WORK（既定 <リポジトリ>\output）、BLENDER（既定 Blender 5.0 の標準インストール先）、
#           HEIAN_DEVICE（既定 OPTIX。CUDA / HIP / CPU など）
$Repo = Split-Path -Parent $PSScriptRoot
$Work = if ($env:HEIAN_WORK) { $env:HEIAN_WORK } else { Join-Path $Repo "output" }
$Blender = if ($env:BLENDER) { $env:BLENDER } else { "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" }
$Device = if ($env:HEIAN_DEVICE) { $env:HEIAN_DEVICE } else { "OPTIX" }
Set-Location $Work
$Out = Join-Path (Resolve-Path $Work) "axis_anim"   # 絶対パス（相対だと Blender が別の場所に書く）
New-Item -ItemType Directory -Force $Out | Out-Null
for ($start = 1; $start -le 288; $start += 24) {
    $end = [Math]::Min($start + 23, 288)
    $last = "{0}\frame_{1:D4}.png" -f $Out, $end
    if (Test-Path $last) { Write-Output "SKIP chunk $start-$end"; continue }
    Write-Output ("RENDER chunk {0}-{1} {2}" -f $start, $end, (Get-Date -Format HH:mm:ss))
    & $Blender --background heian_daidairi_axis_anim.blend `
        --render-output "$Out/frame_" --render-format PNG `
        -s $start -e $end --render-anim -- --cycles-device $Device | Select-String "Saved:" | Select-Object -Last 2
}
$n = (Get-ChildItem "$Out\frame_*.png").Count
Write-Output "ALL_CHUNKS_DONE $n frames"
