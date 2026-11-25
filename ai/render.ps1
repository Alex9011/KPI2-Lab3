$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sourceDir = Join-Path $root 'sequence'
$outputDir = Join-Path $root 'render'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$cli = Get-Command mmdc -ErrorAction SilentlyContinue
if (-not $cli) {
    throw 'Mermaid CLI not found. Install with: npm install --global @mermaid-js/mermaid-cli@12.2.0'
}
foreach ($source in Get-ChildItem -Path $sourceDir -Filter 'S-*.mmd' | Sort-Object Name) {
    $output = Join-Path $outputDir ($source.BaseName + '.svg')
    $arguments = @('-i', $source.FullName, '-o', $output)
    if ($env:PUPPETEER_CONFIG) { $arguments += @('-p', $env:PUPPETEER_CONFIG) }
    & $cli.Source @arguments
    if ($LASTEXITCODE -ne 0) { throw "Mermaid CLI failed for $($source.Name) with exit code $LASTEXITCODE" }
    Write-Output "Rendered $($source.Name) -> $(Split-Path $output -Leaf)"
}
