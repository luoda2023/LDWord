param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [string]$DestinationRoot
)

$ErrorActionPreference = "Stop"

$SourceRoot = Join-Path $RepositoryRoot "artifacts\user-docs\v1.0"
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    throw "User-documentation output directory is missing: $SourceRoot"
}
if (-not (Test-Path -LiteralPath $DestinationRoot -PathType Container)) {
    throw "Release destination directory is missing: $DestinationRoot"
}

$PdfFiles = @(
    Get-ChildItem -LiteralPath $SourceRoot -Filter "Alavette Form V1.0 - *.pdf" |
        Where-Object { $_.Length -gt 0 } |
        Sort-Object -Property Name
)
if ($PdfFiles.Count -ne 2) {
    throw "Expected exactly 2 non-empty V1.0 user-documentation PDFs in: $SourceRoot"
}

$SampleFiles = @(
    Get-ChildItem -LiteralPath $SourceRoot -Filter "*.docx" |
        Where-Object {
            $_.Length -gt 0 -and $_.Name -notlike "Alavette Form V1.0 - *"
        }
)
if ($SampleFiles.Count -ne 1) {
    throw "Expected exactly 1 non-empty quick-start sample DOCX in: $SourceRoot"
}

foreach ($File in @($PdfFiles) + @($SampleFiles)) {
    Copy-Item -LiteralPath $File.FullName -Destination $DestinationRoot -Force
    Write-Output (Join-Path $DestinationRoot $File.Name)
}

$ObsidianBundles = @(
    Get-ChildItem -LiteralPath $SourceRoot -Directory |
        Where-Object { $_.Name -like "*Obsidian*" }
)
if ($ObsidianBundles.Count -ne 1) {
    throw "Expected exactly 1 Obsidian user-documentation directory in: $SourceRoot"
}
$ObsidianDestination = Join-Path $DestinationRoot $ObsidianBundles[0].Name
New-Item -ItemType Directory -Force -Path $ObsidianDestination | Out-Null
foreach ($Item in Get-ChildItem -LiteralPath $ObsidianBundles[0].FullName -Force) {
    Copy-Item -LiteralPath $Item.FullName -Destination $ObsidianDestination -Recurse -Force
}
Write-Output $ObsidianDestination
