param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$ArchiveRoot = ""
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$outer = Split-Path -Parent $repo
$runTimestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

if ([string]::IsNullOrWhiteSpace($ArchiveRoot)) {
    $archiveRoot = Join-Path $outer ("worldweaver_artifacts\batch_a_" + $runTimestamp)
} else {
    $resolvedArchiveRoot = Resolve-Path -LiteralPath $ArchiveRoot -ErrorAction SilentlyContinue
    if ($null -eq $resolvedArchiveRoot) {
        $archiveRoot = $ArchiveRoot
    } else {
        $archiveRoot = $resolvedArchiveRoot.Path
    }
}

New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null

$manifestRows = New-Object System.Collections.Generic.List[object]

function Add-ManifestRow {
    param(
        [string]$RelativePath,
        [string]$ArchiveRelativePath,
        [string]$ItemType,
        [Int64]$SizeBytes,
        [string]$Action,
        [string]$Status,
        [string]$Note
    )

    $manifestRows.Add(
        [PSCustomObject]@{
            run_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
            relative_path = $RelativePath
            archive_relative_path = $ArchiveRelativePath
            item_type = $ItemType
            size_bytes = $SizeBytes
            action = $Action
            status = $Status
            note = $Note
            archive_root = $archiveRoot
        }
    ) | Out-Null
}

function Get-RelativePath {
    param([string]$AbsolutePath)

    $resolved = (Resolve-Path -LiteralPath $AbsolutePath).Path
    if (-not $resolved.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path '$resolved' is outside repo root '$repo'"
    }
    return $resolved.Substring($repo.Length).TrimStart('\', '/').Replace('\', '/')
}

function Move-IntoArchive {
    param([string]$SourcePath)

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
    }

    $item = Get-Item -LiteralPath $SourcePath -Force
    $relative = Get-RelativePath -AbsolutePath $item.FullName
    $destinationBase = Join-Path $archiveRoot $relative
    $destination = $destinationBase
    if (Test-Path -LiteralPath $destination) {
        $destination = $destinationBase + ".dup_" + $runTimestamp
    }

    $archiveRelative = $destination.Substring($archiveRoot.Length).TrimStart('\', '/').Replace('\', '/')
    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null

    $itemType = if ($item.PSIsContainer) { "directory" } else { "file" }
    $sizeBytes = if ($item.PSIsContainer) { 0 } else { [Int64]$item.Length }

    try {
        Move-Item -LiteralPath $item.FullName -Destination $destination -Force
        Add-ManifestRow -RelativePath $relative -ArchiveRelativePath $archiveRelative -ItemType $itemType -SizeBytes $sizeBytes -Action "move" -Status "moved" -Note ""
        return
    } catch {
        $moveError = $_.Exception.Message
    }

    try {
        if ($item.PSIsContainer) {
            Copy-Item -LiteralPath $item.FullName -Destination $destination -Recurse -Force
            Remove-Item -LiteralPath $item.FullName -Recurse -Force
            Add-ManifestRow -RelativePath $relative -ArchiveRelativePath $archiveRelative -ItemType $itemType -SizeBytes $sizeBytes -Action "copy_then_remove" -Status "moved" -Note $moveError
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $destination -Force
            try {
                Remove-Item -LiteralPath $item.FullName -Force
                Add-ManifestRow -RelativePath $relative -ArchiveRelativePath $archiveRelative -ItemType $itemType -SizeBytes $sizeBytes -Action "copy_then_remove" -Status "moved" -Note $moveError
            } catch {
                Add-ManifestRow -RelativePath $relative -ArchiveRelativePath $archiveRelative -ItemType $itemType -SizeBytes $sizeBytes -Action "copy_only" -Status "source_retained_locked" -Note $_.Exception.Message
            }
        }
    } catch {
        Add-ManifestRow -RelativePath $relative -ArchiveRelativePath $archiveRelative -ItemType $itemType -SizeBytes $sizeBytes -Action "failed" -Status "failed" -Note $_.Exception.Message
    }
}

# 1) Move generated directories.
$directoryTargets = @(
    "client/dist",
    "playtests/agent_runs",
    "playtests/long_runs",
    "playtests/sweeps",
    ".pytest_cache",
    ".ruff_cache"
)

foreach ($relative in $directoryTargets) {
    Move-IntoArchive -SourcePath (Join-Path $repo $relative)
}

# 2) Move all generated report outputs while keeping reports/ root available.
$reportsRoot = Join-Path $repo "reports"
if (Test-Path -LiteralPath $reportsRoot) {
    Get-ChildItem -LiteralPath $reportsRoot -Force | ForEach-Object {
        Move-IntoArchive -SourcePath $_.FullName
    }
}

# 3) Move top-level generated playtest markdown/log files only (keep authored analyze_run.py).
$playtestsRoot = Join-Path $repo "playtests"
if (Test-Path -LiteralPath $playtestsRoot) {
    Get-ChildItem -LiteralPath $playtestsRoot -File -Force | Where-Object {
        $_.Extension -in @(".md", ".log")
    } | ForEach-Object {
        Move-IntoArchive -SourcePath $_.FullName
    }
}

# 4) Move local database snapshots and root logs.
Get-ChildItem -LiteralPath $repo -File -Force | Where-Object {
    $_.Extension -eq ".db" -or $_.Extension -eq ".log"
} | ForEach-Object {
    Move-IntoArchive -SourcePath $_.FullName
}

# 5) Move __pycache__ directories after broader directory moves.
Get-ChildItem -LiteralPath $repo -Recurse -Directory -Filter "__pycache__" -Force | Where-Object {
    $_.FullName -notlike "*\.git\*"
} | ForEach-Object {
    Move-IntoArchive -SourcePath $_.FullName
}

$manifestSorted = $manifestRows | Sort-Object relative_path

# Emit manifest into repo and archive for auditability.
$manifestPath = Join-Path $repo "improvements/pruning/BATCH_A_RELOCATION_MANIFEST.csv"
$manifestSorted | Export-Csv -Path $manifestPath -NoTypeInformation -Encoding UTF8
$archiveManifestPath = Join-Path $archiveRoot "BATCH_A_RELOCATION_MANIFEST.csv"
$manifestSorted | Export-Csv -Path $archiveManifestPath -NoTypeInformation -Encoding UTF8

$movedCount = ($manifestRows | Where-Object { $_.status -eq "moved" }).Count
$retainedCount = ($manifestRows | Where-Object { $_.status -eq "source_retained_locked" }).Count
$failedCount = ($manifestRows | Where-Object { $_.status -eq "failed" }).Count
$totalCount = $manifestRows.Count

$summaryPath = Join-Path $repo "improvements/pruning/BATCH_A_RELOCATION_SUMMARY.md"
$summaryLines = @(
    "# Batch A Relocation Summary",
    "",
    "Date (UTC): ``" + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") + "``",
    "Archive root: ``" + $archiveRoot.Replace('\', '/') + "``",
    "Rows recorded this run: ``" + $totalCount + "``",
    "Moved items: ``" + $movedCount + "``",
    "Retained at source (locked): ``" + $retainedCount + "``",
    "Failed items: ``" + $failedCount + "``",
    "",
    "Manifest:",
    "- ``improvements/pruning/BATCH_A_RELOCATION_MANIFEST.csv``",
    "- ``" + $archiveManifestPath.Replace('\', '/') + "``"
)
$summaryLines | Set-Content -Path $summaryPath -Encoding UTF8

Write-Output ("ARCHIVE_ROOT=" + $archiveRoot)
Write-Output ("ROWS_RECORDED=" + $totalCount)
Write-Output ("MOVED_ITEMS=" + $movedCount)
Write-Output ("SOURCE_RETAINED_LOCKED=" + $retainedCount)
Write-Output ("FAILED_ITEMS=" + $failedCount)
Write-Output ("MANIFEST=" + $manifestPath)
