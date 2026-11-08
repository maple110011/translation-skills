# Undo link.ps1: remove junctions (link only, repo content untouched)
# and restore the pre-junction backup folders.

$ErrorActionPreference = 'Stop'
$skillsRoot = Join-Path $env:USERPROFILE '.workbuddy\skills'
$parentOfSkills = Split-Path -Parent $skillsRoot
$names = @('political-economy-translation', 'ml-math-stats-translation')

foreach ($n in $names) {
    $link = Join-Path $skillsRoot $n
    $backup = Join-Path $parentOfSkills "$n.pre-junction-backup"

    $item = Get-Item -LiteralPath $link -ErrorAction SilentlyContinue
    if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        (Get-Item -LiteralPath $link).Delete()   # deletes the junction only
        Write-Host "removed junction: $link"
    }
    elseif ($item) {
        Write-Host "not a junction, left untouched: $link"
        continue
    }
    if (Test-Path -LiteralPath $backup) {
        Move-Item -LiteralPath $backup -Destination $link
        Write-Host "restored: $link"
    }
}

Write-Host "Done. The repo content is unchanged."
