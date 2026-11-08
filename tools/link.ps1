# Link WorkBuddy skill folders to this repo using NTFS junctions.
# No hardcoded absolute paths: repo root is derived from $PSScriptRoot,
# local skill root is derived from $env:USERPROFILE.
# Reversible: the original folder is renamed to a backup OUTSIDE skills/
# (so WorkBuddy will not scan it as a second skill). Run unlink.ps1 to undo.

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$skillsRoot = Join-Path $env:USERPROFILE '.workbuddy\skills'
$parentOfSkills = Split-Path -Parent $skillsRoot
$names = @('political-economy-translation', 'ml-math-stats-translation')

foreach ($n in $names) {
    $target = Join-Path $repo "skills\$n"
    $link = Join-Path $skillsRoot $n
    $backup = Join-Path $parentOfSkills "$n.pre-junction-backup"

    if (-not (Test-Path -LiteralPath $target)) {
        throw "Missing repo skill: $target"
    }
    $item = Get-Item -LiteralPath $link -ErrorAction SilentlyContinue
    if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Write-Host "already linked: $n"
        continue
    }
    if (Test-Path -LiteralPath $backup) {
        throw "Backup already exists, refusing to overwrite: $backup"
    }
    if ($item) {
        # Same-volume move = atomic rename; one step keeps the original out of skills/.
        Move-Item -LiteralPath $link -Destination $backup
        Write-Host "backed up: $backup"
    }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "linked: $link -> $target"
}

Write-Host "Done. Verify with: Get-Item <skillsRoot>\<name> | Select-Object LinkType,Target"
