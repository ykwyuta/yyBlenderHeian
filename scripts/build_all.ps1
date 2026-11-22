# 平安京モデルを配置CSVから最新版まで一括生成する（Windows PowerShell）。
#   powershell -ExecutionPolicy Bypass -File scripts/build_all.ps1 [-From <段階>]
# 段階: detail → city → interior → refine1 → refine2 → refine3 → interior2 → refine4 → env → life
#   detail   : build_chodoin_detailed.py  → v10（大内裏・部品v3＋推定レイヤー）
#   city     : build_city_layer.py        → v15（市街レイヤーv6。v10を開く）
#   interior : build_interior.py          → v11（内裏の内部。v15を開く）
#   ※ 内部は市街レイヤーが作る材質（MAT_WoodLight）を使うため、市街を先に作る。
#     各スクリプトの保存名は固定（v15・v11）なので、ここでは v10→v15→v11→v16 の順に
#     ファイルが渡る。v18 は市街v6・内部・外観精密化（部品v6まで）をすべて含む。
#   refine1-3: build_exterior_refine*.py  → v16 / v17 / v18（外観精密化 部品v4〜v6）
#   interior2: build_interior2.py         → v19（後宮の内部）
#   refine4  : build_exterior_refine4.py  → v20（外観精密化 部品v7：組物・礎石・扁額）
#   env      : build_environment.py       → v21（環境レイヤー：遠景の山・大気・河川）
#   life     : build_life_layer.py        → v22（植生と生活の気配：柳・梅・橘、炊煙・灯り・轍など）
# 各段階は前段の .blend を開いて次の版を保存する。-From で途中から再開できる。
# 環境変数: HEIAN_WORK（既定 <リポジトリ>\output）、BLENDER（既定 Blender 5.0 の標準インストール先）、
#           HEIAN_DEVICE（既定 GPU 自動選択、CPU で固定）
param([string]$From = "detail")

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Work = if ($env:HEIAN_WORK) { $env:HEIAN_WORK } else { Join-Path $Repo "output" }
$Blender = if ($env:BLENDER) { $env:BLENDER } else { "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" }
New-Item -ItemType Directory -Force $Work | Out-Null
$S = Join-Path $Repo "scripts"
function V($n) { Join-Path $Work ("heian_daidairi_detail_v{0}.blend" -f $n) }

$steps = @(
    @{ name = "detail";   args = @("--background", "--python", "$S\build_chodoin_detailed.py", "--",
                                   "$Repo\data\daidairi_layout_v3_1.csv", (V 10), (Join-Path $Work "view_v10"),
                                   "$Repo\data\daidairi_conjectural_v1.csv") },
    @{ name = "city";     args = @("--background", (V 10), "--python", "$S\build_city_layer.py") },
    @{ name = "interior"; args = @("--background", (V 15), "--python", "$S\build_interior.py") },
    @{ name = "refine1";  args = @("--background", (V 11), "--python", "$S\build_exterior_refine.py") },
    @{ name = "refine2";  args = @("--background", (V 16), "--python", "$S\build_exterior_refine2.py") },
    @{ name = "refine3";  args = @("--background", (V 17), "--python", "$S\build_exterior_refine3.py") },
    @{ name = "interior2"; args = @("--background", (V 18), "--python", "$S\build_interior2.py") },
    @{ name = "refine4";  args = @("--background", (V 19), "--python", "$S\build_exterior_refine4.py") },
    @{ name = "env";      args = @("--background", (V 20), "--python", "$S\build_environment.py", "--", (V 21)) },
    @{ name = "life";     args = @("--background", (V 21), "--python", "$S\build_life_layer.py", "--", (V 22)) }
)

$started = $false
foreach ($st in $steps) {
    if ($st.name -eq $From) { $started = $true }
    if (-not $started) { continue }
    $log = Join-Path $Work ("log_build_{0}.txt" -f $st.name)
    Write-Host ("STEP {0} {1}" -f $st.name, (Get-Date -Format HH:mm:ss))
    # --python-exit-code: スクリプトの例外を終了コードに反映させる（既定では 0 のまま終わる）
    # Start-Process を使うのは、Windows PowerShell 5.1 が Blender の stderr（非推奨の警告など）を
    # エラーとして扱って止まるのを避けるため。stderr は別ファイル（*_err.txt）に残す。
    $argList = @("--python-exit-code", "1") + $st.args | ForEach-Object { '"{0}"' -f $_ }
    $p = Start-Process -FilePath $Blender -ArgumentList $argList -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError ($log -replace "\.txt$", "_err.txt")
    if ($p.ExitCode -ne 0) { throw ("step {0} failed (exit {1}), see {2}" -f $st.name, $p.ExitCode, $log) }
    Get-Content $log -Tail 3 | ForEach-Object { Write-Host "  $_" }
}
Write-Host ("ALL_DONE {0}" -f (Get-Date -Format HH:mm:ss))
