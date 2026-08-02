param(
    [string]$RepositoryRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$OutputRoot = Join-Path $RepositoryRoot "artifacts\user-docs\v1.0"
$Documents = @(
    Get-ChildItem -LiteralPath $OutputRoot -Filter "Alavette Form V1.0 - *.docx" |
        Sort-Object -Property Name
)
if ($Documents.Count -ne 2) {
    throw "Expected 2 Alavette Form V1.0 documentation DOCX files in: $OutputRoot"
}

$Word = $null
try {
    $Word = New-Object -ComObject Word.Application
    $Word.Visible = $false
    $Word.DisplayAlerts = 0
    foreach ($SourceDocument in $Documents) {
        $DocxPath = $SourceDocument.FullName
        $PdfPath = [System.IO.Path]::ChangeExtension($DocxPath, ".pdf")
        $Document = $null
        try {
            $Document = $Word.Documents.Open($DocxPath, $false, $true)
            $Document.ExportAsFixedFormat($PdfPath, 17)
            Write-Output $PdfPath
        }
        finally {
            if ($null -ne $Document) {
                $Document.Close($false)
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Document)
            }
        }
    }
}
finally {
    if ($null -ne $Word) {
        $Word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
