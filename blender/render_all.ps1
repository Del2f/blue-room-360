# Full render batch for the v3 viewer. Resumable: finished outputs are skipped, so it can be
# stopped at any time and started again with the same command.
#   powershell -File render_all.ps1 -Work <dir> [-Blender <exe>] [-Rebuild]
param(
  [Parameter(Mandatory = $true)][string]$Work,
  [string]$Blender = "C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
  [switch]$Rebuild
)
$ErrorActionPreference = "Continue"
$scripts = Join-Path $Work "scripts"
$blend = Join-Path $Work "akmu.blend"
$out = Join-Path $Work "out"
$log = Join-Path $Work "render_all.log"
"start $(Get-Date -Format s)" | Add-Content $log

function Run($label, [string[]]$a) {
  $t0 = Get-Date
  "[$label] ..." | Add-Content $log
  & $Blender @a *> (Join-Path $Work "step_$label.log")
  $ok = Select-String -Path (Join-Path $Work "step_$label.log") -Pattern "RENDER DONE|BUILD OK" -Quiet
  $err = Select-String -Path (Join-Path $Work "step_$label.log") -Pattern "Traceback" -Quiet
  "[$label] {0} in {1:N0}s" -f $(if ($ok -and -not $err) { "ok" } else { "FAILED" }), ((Get-Date) - $t0).TotalSeconds | Add-Content $log
}
function Missing($folder, [string[]]$want) {
  $have = if (Test-Path $folder) { Get-ChildItem $folder -Filter *.jpg | ForEach-Object BaseName } else { @() }
  @($want | Where-Object { $have -notcontains $_ })
}
$R = @("-b", $blend, "-P", (Join-Path $scripts "render.py"), "--", "--work", $Work)
$all = "px", "nx", "py", "ny", "pz", "nz"

if ($Rebuild -or -not (Test-Path $blend)) { Run "build" @("-b", "--factory-startup", "-P", (Join-Path $scripts "build_scenes.py"), "--", "--work", $Work) }
$pre = "pre_window_view", "pre_dunes_from_door", "pre_room_from_door" | ForEach-Object { Join-Path $Work "renders\$_.exr" }
if ($Rebuild -or ($pre | Where-Object { -not (Test-Path $_) })) { Run "pre" ($R + @("--mode", "pre", "--samples", "512")) }

$m = Missing (Join-Path $out "faces\dunes\4096") $all
if ($m.Count) { Run "faces_dunes" ($R + @("--mode", "faces", "--space", "dunes", "--size", "4096", "--samples", "512", "--only", ($m -join ","))) }
$m = Missing (Join-Path $out "faces\room\4096") $all
if ($m.Count) { Run "faces_room" ($R + @("--mode", "faces", "--space", "room", "--size", "4096", "--samples", "768", "--only", ($m -join ","))) }
$m = Missing (Join-Path $out "faces\dunes_bloom\4096") @("px", "nx", "pz", "nz", "ny")
if ($m.Count) { Run "faces_bloom" ($R + @("--mode", "faces", "--space", "dunes", "--bloom", "1", "--size", "4096", "--samples", "512", "--only", ($m -join ","))) }
foreach ($sp in "dunes", "room") {
  if (-not (Test-Path (Join-Path $out "masks\$sp\ids.json"))) { Run "masks_$sp" ($R + @("--mode", "masks", "--space", $sp, "--size", "1024")) }
}
$clipsJson = Join-Path $out "video\clips.json"
foreach ($c in "d2r_a", "d2r_b", "r2d_a", "r2d_b") {
  $done = (Test-Path (Join-Path $out "video\$c.mp4")) -and (Test-Path $clipsJson) -and ((Get-Content $clipsJson -Raw) -match "`"$c`"")
  if (-not $done) { Run "video_$c" ($R + @("--mode", "video", "--clip", $c, "--samples", "160")) }
}
"end $(Get-Date -Format s)" | Add-Content $log
